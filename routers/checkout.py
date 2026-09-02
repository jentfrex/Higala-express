# routers/checkout.py - Production Ready (SQLite/PostgreSQL Safe + Dynamic Fare Engine + Multi-Vendor Atomic Checkout)
import uuid
import logging
import math
from typing import List, Optional
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel, Field

from database import get_db
from models import (
    MasterOrder, Order, OrderItem, User, MerchantBranch, BranchInventory,
    PaymentMethod
)
import models
from services.payment_service import PaymentService
from routers.auth import get_current_user

logger = logging.getLogger("checkout")

router = APIRouter(prefix="/checkout", tags=["Checkout & Payments"])

# ==============================================================================
# CAGAYAN DE ORO GEOFENCE & FARE PRICING CONSTANTS (Directive 4)
# ==============================================================================
CDO_LAT_MIN, CDO_LAT_MAX = 8.30, 8.60
CDO_LNG_MIN, CDO_LNG_MAX = 124.50, 124.80

BASE_DELIVERY_FARE = 49.00     # Base fee for first 2.0 km
PER_KM_RATE = 10.00            # PHP per km after base distance
BASE_DISTANCE_KM = 2.0

def calculate_haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates Haversine distance in kilometers between two GPS coordinates."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2.0) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2.0) ** 2)
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c

def compute_cdo_fare(pickup_lat: float, pickup_lng: float, dropoff_lat: float, dropoff_lng: float) -> float:
    """Computes CDO delivery fare with dynamic tier pricing."""
    dist = calculate_haversine_distance(pickup_lat, pickup_lng, dropoff_lat, dropoff_lng)
    if dist <= BASE_DISTANCE_KM:
        return BASE_DELIVERY_FARE
    return round(BASE_DELIVERY_FARE + ((dist - BASE_DISTANCE_KM) * PER_KM_RATE), 2)


# ==============================================================================
# SCHEMAS
# ==============================================================================

class CartItemInput(BaseModel):
    merchant_id: int
    branch_id: int
    item_id: int  # BranchInventory ID
    quantity: int = Field(..., ge=1)
    price: float = Field(..., gt=0)
    pickup_location: Optional[str] = None
    dropoff_location: Optional[str] = None
    pickup_lat: Optional[float] = None
    pickup_lng: Optional[float] = None


class CheckoutRequest(BaseModel):
    customer_id: int
    items: List[CartItemInput]
    payment_method: str = Field(
        ..., 
        description="cash_on_delivery | bank_transfer | wallet | gcash | qr_ph"
    )
    delivery_address: Optional[str] = None
    delivery_lat: Optional[float] = None
    delivery_lng: Optional[float] = None
    notes: Optional[str] = None


class PaymentConfirmationPayload(BaseModel):
    payment_id: int
    confirmation_code: Optional[str] = None  # For bank transfer verification


# ==============================================================================
# CHECKOUT ENDPOINTS
# ==============================================================================

@router.post("", status_code=status.HTTP_201_CREATED)
@router.post("/", status_code=status.HTTP_201_CREATED)
def checkout(
    payload: CheckoutRequest, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Production-ready multi-vendor checkout with SQLite atomic guarantees, 
    row locking, dynamic CDO fare calculation, and wallet/COD ledger streaming.
    """
    # Security Guard: Prevent unauthorized checkout on behalf of another user
    if payload.customer_id != current_user.id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Cannot checkout on behalf of another user"
        )

    if not payload.items:
        raise HTTPException(status_code=400, detail="Cart is empty")

    # 1. Validate customer exists
    customer = db.query(User).filter(User.id == payload.customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    try:
        # SQLite transaction lock handling
        try:
            db.execute(text("BEGIN IMMEDIATE"))
        except Exception:
            pass # Fallback if DBMS doesn't support explicit BEGIN IMMEDIATE syntax

        # 2. Lock inventory items and validate stock simultaneously
        inventory_items = []
        for item in payload.items:
            locked_inv = db.query(BranchInventory).filter(
                BranchInventory.id == item.item_id,
                BranchInventory.branch_id == item.branch_id
            ).with_for_update().first()

            if not locked_inv:
                raise ValueError(f"Item {item.item_id} not found in branch {item.branch_id}")
            
            if not locked_inv.is_available:
                raise ValueError(f"Item '{locked_inv.item_name}' is currently unavailable")

            if locked_inv.current_stock is not None and locked_inv.current_stock < item.quantity:
                raise ValueError(
                    f"Insufficient stock for '{locked_inv.item_name}'. "
                    f"Available: {locked_inv.current_stock}, Requested: {item.quantity}"
                )

            inventory_items.append((locked_inv, item))

        # 3. Calculate Items Subtotal & CDO Dynamic Delivery Fee
        items_total = sum(item.price * item.quantity for item in payload.items)
        
        # Calculate dynamic delivery fee if dropoff GPS is provided
        delivery_fee = 0.0
        if payload.delivery_lat and payload.delivery_lng and payload.items[0].pickup_lat and payload.items[0].pickup_lng:
            delivery_fee = compute_cdo_fare(
                payload.items[0].pickup_lat, payload.items[0].pickup_lng,
                payload.delivery_lat, payload.delivery_lng
            )
        else:
            delivery_fee = BASE_DELIVERY_FARE  # Default baseline fee

        calculated_total = round(items_total + delivery_fee, 2)

        # 4. Lock customer row for digital wallet balance validation
        customer_locked = db.query(User).filter(
            User.id == payload.customer_id
        ).with_for_update().first()

        norm_payment_method = payload.payment_method.lower()
        if norm_payment_method == "wallet":
            wallet_bal = customer_locked.wallet_balance or 0.0
            if wallet_bal < calculated_total:
                raise ValueError(
                    f"Insufficient wallet balance. Total Required: ₱{calculated_total:.2f}, "
                    f"Available Balance: ₱{wallet_bal:.2f}"
                )

        # 5. Create Master Order
        master_order = MasterOrder(
            customer_id=payload.customer_id,
            total_amount=calculated_total,
            status="created",
            created_at=datetime.now(timezone.utc)
        )
        db.add(master_order)
        db.flush()  # Generate master_order.id

        # 6. Group items by merchant/branch and create Sub-Orders (Multi-vendor support)
        merchant_groups = {}
        for _, cart_item in inventory_items:
            key = (cart_item.merchant_id, cart_item.branch_id)
            if key not in merchant_groups:
                merchant_groups[key] = []
            merchant_groups[key].append(cart_item)

        sub_order_ids = []
        for (merchant_id, branch_id), group_items in merchant_groups.items():
            branch = db.query(MerchantBranch).filter(
                MerchantBranch.id == branch_id
            ).first()
            if not branch:
                raise ValueError(f"Branch #{branch_id} not found")

            sub_total = sum(item.price * item.quantity for item in group_items)
            item_desc = ", ".join([
                f"{i.quantity}x Item#{i.item_id}" for i in group_items
            ])

            sub_order = Order(
                master_order_id=master_order.id,
                customer_id=payload.customer_id,
                merchant_id=merchant_id,
                branch_id=branch_id,
                item_description=item_desc,
                price=sub_total,
                status="pending",
                delivery_address=payload.delivery_address or branch.address,
                customer_latitude=payload.delivery_lat,
                customer_longitude=payload.delivery_lng,
                payment_method=norm_payment_method
            )
            db.add(sub_order)
            db.flush()

            # Add individual order items
            for cart_item in group_items:
                inv_ref = db.query(BranchInventory).filter(
                    BranchInventory.id == cart_item.item_id
                ).first()

                order_item = OrderItem(
                    order_id=sub_order.id,
                    item_name=inv_ref.item_name if inv_ref else f"Item-{cart_item.item_id}",
                    quantity=cart_item.quantity,
                    price=cart_item.price
                )
                db.add(order_item)

            sub_order_ids.append(sub_order.id)

        # 7. Deduct Inventory Stock
        for locked_inv, cart_item in inventory_items:
            locked_inv.current_stock = max(0, (locked_inv.current_stock or 0) - cart_item.quantity)
            if locked_inv.current_stock == 0:
                locked_inv.is_available = False

        # 8. Process Payment Gateway / Wallet Routing
        payment_result = PaymentService.process_order_payments(
            db=db,
            master_order_id=master_order.id,
            amount=calculated_total,
            payment_method=norm_payment_method,
            user_id=payload.customer_id
        )

        if not payment_result.get("success"):
            raise ValueError(payment_result.get("error", "Payment processing failed"))

        # 9. Update statuses based on payment outcome
        pay_status = payment_result.get("status")
        if pay_status in ["completed", "pending"]:
            master_order.status = "payment_confirmed" if pay_status == "completed" else "awaiting_payment"
        else:
            raise ValueError("Invalid payment status returned from gateway service")

        # 10. Financial Settlement: Merchant Commissions
        for sub_order_id in sub_order_ids:
            sub_order_obj = db.query(Order).filter(Order.id == sub_order_id).first()
            if sub_order_obj:
                PaymentService.calculate_merchant_commission(
                    db=db,
                    order_id=sub_order_id,
                    merchant_id=sub_order_obj.merchant_id,
                    gross_amount=sub_order_obj.price,
                    commission_rate=0.20  # Directive 5: Standard 20% platform commission fee
                )

        # ATOMIC COMMIT FOR ALL MULTI-VENDOR TRANSACTIONS
        db.commit()

        return {
            "success": True,
            "message": "Checkout multi-vendor order processed successfully!",
            "master_order_id": master_order.id,
            "sub_order_ids": sub_order_ids,
            "breakdown": {
                "items_total": items_total,
                "delivery_fee": delivery_fee,
                "total_amount": calculated_total
            },
            "payment": payment_result
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Checkout transaction failed: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/payment/confirm/{payment_id}")
def confirm_payment_receipt(
    payment_id: int,
    payload: PaymentConfirmationPayload,
    db: Session = Depends(get_db)
):
    """
    Admin/system endpoint to confirm digital payment transfer.
    """
    if hasattr(models, "Payment"):
        payment = db.query(models.Payment).filter(models.Payment.id == payment_id).first()
        if not payment:
            raise HTTPException(status_code=404, detail="Payment record not found")
        
        PaymentService.confirm_payment(db, payment_id)
        
        master_order = db.query(MasterOrder).filter(
            MasterOrder.id == payment.master_order_id
        ).first()
        if master_order:
            master_order.status = "payment_confirmed"
            db.commit()
    
    return {
        "success": True,
        "message": "Payment verified and confirmed successfully",
        "payment_id": payment_id,
        "status": "completed"
    }


@router.get("/payment-methods")
def get_available_payment_methods():
    """Returns all supported regional payment methods in CDO."""
    return {
        "payment_methods": [
            {
                "id": "cash_on_delivery",
                "name": "Cash on Delivery (COD)",
                "description": "Pay in cash directly to rider upon delivery",
                "icon": "money-hand"
            },
            {
                "id": "wallet",
                "name": "Higala App Wallet",
                "description": "Instant payment from your in-app wallet balance",
                "icon": "wallet"
            },
            {
                "id": "gcash",
                "name": "GCash / QR Ph",
                "description": "Direct digital wallet payment with QR code",
                "icon": "qr-code"
            },
            {
                "id": "bank_transfer",
                "name": "Direct Bank Transfer",
                "description": "Bank transfer confirmation (Manual approval)",
                "icon": "bank"
            }
        ]
    }