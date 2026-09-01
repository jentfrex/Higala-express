# routers/checkout.py - Production Ready (SQLite Safe + Multi-Vendor Atomic Checkout)
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from database import get_db
from models import (
    MasterOrder, Order, OrderItem, User, MerchantBranch, BranchInventory,
    PaymentMethod
)
from services.payment_service import PaymentService
import uuid
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/checkout", tags=["Checkout & Payments"])

# ==========================================
# SCHEMAS
# ==========================================

class CartItemInput(BaseModel):
    merchant_id: int
    branch_id: int
    item_id: int  # BranchInventory ID
    quantity: int
    price: float = Field(..., gt=0)
    pickup_location: Optional[str] = None
    dropoff_location: Optional[str] = None

class CheckoutRequest(BaseModel):
    customer_id: int
    items: List[CartItemInput]
    payment_method: str = Field(
        ..., 
        description="cash_on_delivery | bank_transfer | wallet"
    )
    delivery_address: Optional[str] = None
    notes: Optional[str] = None

class PaymentConfirmationPayload(BaseModel):
    payment_id: int
    confirmation_code: Optional[str] = None  # For bank transfer verification

# ==========================================
# CHECKOUT ENDPOINTS
# ==========================================

@router.post("/checkout", status_code=status.HTTP_201_CREATED)
def checkout(payload: CheckoutRequest, db: Session = Depends(get_db)):
    """
    Production-ready multi-vendor checkout with SQLite atomic guarantees and row locking.
    """
    if not payload.items:
        raise HTTPException(status_code=400, detail="Cart is empty")

    # 1. Validate customer exists first
    customer = db.query(User).filter(User.id == payload.customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    try:
        # BEGIN IMMEDIATE prevents SQLite deadlock/locked errors during concurrent writes
        db.execute(text("BEGIN IMMEDIATE"))

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
                raise ValueError(f"Item '{locked_inv.item_name}' is unavailable")

            if locked_inv.current_stock is not None and locked_inv.current_stock < item.quantity:
                raise ValueError(
                    f"Insufficient stock for '{locked_inv.item_name}'. "
                    f"Available: {locked_inv.current_stock}, Requested: {item.quantity}"
                )

            inventory_items.append((locked_inv, item))

        # 3. Calculate total and lock customer row for wallet validation
        calculated_total = sum(item.price * item.quantity for item in payload.items)

        customer_locked = db.query(User).filter(
            User.id == payload.customer_id
        ).with_for_update().first()

        if payload.payment_method == PaymentMethod.WALLET:
            if customer_locked.wallet_balance is None or customer_locked.wallet_balance < calculated_total:
                raise ValueError(
                    f"Insufficient wallet balance. Need: ₱{calculated_total:.2f}, "
                    f"Have: ₱{customer_locked.wallet_balance or 0:.2f}"
                )

        # 4. Create Master Order
        master_order = MasterOrder(
            customer_id=payload.customer_id,
            total_amount=calculated_total,
            status="created",
            created_at=datetime.utcnow()
        )
        db.add(master_order)
        db.flush()  # Get master_order.id without final commit

        # 5. Group items by merchant/branch and create Sub-Orders (Multi-vendor support)
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
                raise ValueError(f"Branch {branch_id} not found")

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
                delivery_address=payload.delivery_address or branch.address
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

        # 6. Deduct inventory while holding locks
        for locked_inv, cart_item in inventory_items:
            locked_inv.current_stock = max(0, locked_inv.current_stock - cart_item.quantity)
            if locked_inv.current_stock == 0:
                locked_inv.is_available = False

        # 7. Process Payment
        payment_result = PaymentService.process_order_payments(
            db=db,
            master_order_id=master_order.id,
            amount=calculated_total,
            payment_method=payload.payment_method,
            user_id=payload.customer_id
        )

        if not payment_result["success"]:
            raise ValueError(payment_result.get("error", "Payment processing failed"))

        # 8. Update statuses based on payment outcome
        pay_status = payment_result.get("status")
        if pay_status in ["completed", "pending"]:
            master_order.status = "payment_confirmed" if pay_status == "completed" else "awaiting_payment"
        else:
            raise ValueError("Invalid payment status returned")

        # 9. Calculate merchant commissions for sub-orders
        for sub_order_id in sub_order_ids:
            sub_order_obj = db.query(Order).filter(Order.id == sub_order_id).first()
            if sub_order_obj:
                PaymentService.calculate_merchant_commission(
                    db=db,
                    order_id=sub_order_id,
                    merchant_id=sub_order_obj.merchant_id,
                    gross_amount=sub_order_obj.price,
                    commission_rate=0.10  # 10% platform fee
                )

        # SINGLE ATOMIC COMMIT FOR EVERYTHING
        db.commit()

        return {
            "success": True,
            "message": "Checkout successful!",
            "master_order_id": master_order.id,
            "total_amount": calculated_total,
            "sub_order_ids": sub_order_ids,
            "payment": payment_result
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Checkout failed: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/payment/confirm/{payment_id}")
def confirm_payment_receipt(
    payment_id: int,
    payload: PaymentConfirmationPayload,
    db: Session = Depends(get_db)
):
    """
    Admin/system endpoint to confirm bank transfer payment.
    """
    from models import Payment
    
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    
    PaymentService.confirm_payment(db, payment_id)
    
    master_order = db.query(MasterOrder).filter(
        MasterOrder.id == payment.master_order_id
    ).first()
    if master_order:
        master_order.status = "payment_confirmed"
        db.commit()
    
    return {
        "success": True,
        "message": "Payment confirmed",
        "payment_id": payment_id,
        "status": "completed"
    }

@router.get("/payment-methods")
def get_available_payment_methods():
    """List all available payment methods"""
    return {
        "payment_methods": [
            {
                "id": "cash_on_delivery",
                "name": "Cash on Delivery",
                "description": "Pay when order is delivered",
                "icon": "money-hand"
            },
            {
                "id": "bank_transfer",
                "name": "Bank Transfer",
                "description": "Transfer to merchant account (24-hour deadline)",
                "icon": "bank"
            },
            {
                "id": "wallet",
                "name": "Higala Wallet",
                "description": "Instant payment from wallet balance",
                "icon": "wallet"
            }
        ]
    }