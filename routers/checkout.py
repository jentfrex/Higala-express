from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List
from database import get_db
from models import MasterOrder, Order, OrderItem, User, Merchant
from services.finance import process_split_checkout_finances

router = APIRouter(prefix="/checkout", tags=["Split Checkout"])

class CartItemInput(BaseModel):
    merchant_id: int
    item_name: str
    quantity: int
    price: float
    pickup_location: str
    dropoff_location: str

class SplitCheckoutRequest(BaseModel):
    customer_id: int
    items: List[CartItemInput]

@router.post("/split")
def split_checkout(payload: SplitCheckoutRequest, db: Session = Depends(get_db)):
    """
    Handles a multi-vendor cart checkout by creating a MasterOrder,
    splitting the cart items into individual sub-orders per merchant,
    and triggering automated wallet payments and commission payouts.
    """
    # 1. Verify customer exists
    customer = db.query(User).filter(User.id == payload.customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    if not payload.items:
        raise HTTPException(status_code=400, detail="Cart is empty")

    # 2. Calculate grand total upfront to check wallet balance
    calculated_grand_total = sum(item.price * item.quantity for item in payload.items)

    # --- STRICT WALLET BALANCE VALIDATION ---
    if customer.wallet_balance is None or customer.wallet_balance < calculated_grand_total:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Insufficient wallet balance for this transaction"
        )
    # -----------------------------------------------

    # 3. Group items by merchant_id
    merchant_groups = {}
    for item in payload.items:
        if item.merchant_id not in merchant_groups:
            merchant_groups[item.merchant_id] = []
        merchant_groups[item.merchant_id].append(item)

    # 4. Create Master Order
    master_order = MasterOrder(
        customer_id=payload.customer_id,
        total_amount=0.0,
        status="pending"
    )
    db.add(master_order)
    db.commit()
    db.refresh(master_order)

    grand_total = 0.0
    created_sub_orders = []

    # 5. Create child Orders and OrderItems per merchant group
    for merchant_id, group_items in merchant_groups.items():
        # Verify merchant exists
        merchant = db.query(Merchant).filter(Merchant.id == merchant_id).first()
        if not merchant:
            raise HTTPException(status_code=404, detail=f"Merchant ID {merchant_id} not found")

        sub_order_total = sum(item.price * item.quantity for item in group_items)
        grand_total += sub_order_total

        # Use the first item's locations or default merchant location
        pickup = group_items[0].pickup_location
        dropoff = group_items[0].dropoff_location
        item_summary = ", ".join([f"{i.quantity}x {i.item_name}" for i in group_items])

        sub_order = Order(
            master_order_id=master_order.id,
            customer_id=payload.customer_id,
            merchant_id=merchant_id,
            item_description=item_summary,
            pickup_location=pickup,
            dropoff_location=dropoff,
            price=sub_order_total,
            status="pending"
        )
        db.add(sub_order)
        db.commit()
        db.refresh(sub_order)

        # Add individual line items
        for item in group_items:
            order_item = OrderItem(
                order_id=sub_order.id,
                item_name=item.item_name,
                quantity=item.quantity,
                price=item.price
            )
            db.add(order_item)

        created_sub_orders.append(sub_order.id)

    # Update master order total amount & mark as paid
    master_order.total_amount = grand_total
    master_order.status = "paid"
    
    # Deduct wallet balance
    customer.wallet_balance -= grand_total
    
    db.commit()
    db.refresh(master_order)

    # 6. Automatically process commission splits and wallet payouts
    process_split_checkout_finances(db, master_order.id, platform_commission_rate=0.10)

    return {
        "success": True,
        "message": "Split checkout and automated financial settlement successful!",
        "master_order_id": master_order.id,
        "total_amount": grand_total,
        "sub_order_ids": created_sub_orders
    }