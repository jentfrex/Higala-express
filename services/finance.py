from sqlalchemy.orm import Session
from models import MasterOrder, Order, User, Merchant, WalletTransaction
from services.webhook import trigger_merchant_webhook

def get_driver_completed_count(db: Session, driver_id: int) -> int:
    """
    Counts total completed deliveries for a driver directly from the Order table.
    """
    count = db.query(Order).filter(Order.driver_id == driver_id, Order.status == "completed").count()
    return count

def process_split_checkout_finances(db: Session, master_order_id: int, platform_commission_rate: float = 0.15):
    """
    Deducts payment from customer, calculates merchant revenue minus 15% platform commission,
    handles driver delivery fee payout with a sliding scale (15% down to 5% after 10 completed transactions),
    updates wallet balances, and triggers real-time merchant webhooks.
    """
    master_order = db.query(MasterOrder).filter(MasterOrder.id == master_order_id).first()
    if not master_order:
        return False

    customer = db.query(User).filter(User.id == master_order.customer_id).first()
    if not customer:
        return False

    if customer.wallet_balance < master_order.total_amount:
        raise ValueError(
            f"Insufficient wallet balance. Available: ₱{customer.wallet_balance:.2f}, "
            f"Required: ₱{master_order.total_amount:.2f}"
        )

    # Deduct total from customer
    customer.wallet_balance -= master_order.total_amount
    
    db.add(WalletTransaction(
        user_id=customer.id,
        amount=-master_order.total_amount,
        transaction_type="order_payment",
        reference_id=master_order.id,
        description=f"Payment for Master Order #{master_order.id}"
    ))

    # Process each sub-order for merchants & handle driver delivery payouts
    for sub_order in master_order.sub_orders:
        # 1. Process Merchant Payout (15% commission)
        merchant = db.query(Merchant).filter(Merchant.id == sub_order.merchant_id).first()
        if merchant and merchant.owner_id:
            merchant_owner = db.query(User).filter(User.id == merchant.owner_id).first()
            if merchant_owner:
                commission = sub_order.price * platform_commission_rate
                merchant_payout = sub_order.price - commission

                merchant_owner.wallet_balance += merchant_payout

                db.add(WalletTransaction(
                    user_id=merchant_owner.id,
                    amount=merchant_payout,
                    transaction_type="merchant_payout",
                    reference_id=sub_order.id,
                    description=f"Payout for Sub-Order #{sub_order.id} (Net of {platform_commission_rate*100}% commission)"
                ))

        # 2. Process Driver Delivery Fee Payout (Sliding Scale)
        if getattr(sub_order, "driver_id", None) and getattr(sub_order, "delivery_fee", 0) > 0:
            driver = db.query(User).filter(User.id == sub_order.driver_id).first()
            if driver:
                # Count driver's historical completed deliveries from the Order table
                completed_deliveries = get_driver_completed_count(db, driver.id)

                # Sliding scale: 15% platform cut for first 10 transactions, 5% for 11+
                if completed_deliveries <= 10:
                    driver_platform_commission = 0.15
                else:
                    driver_platform_commission = 0.05

                delivery_fee = sub_order.delivery_fee
                driver_commission_cut = delivery_fee * driver_platform_commission
                driver_payout = delivery_fee - driver_commission_cut

                driver.wallet_balance += driver_payout

                db.add(WalletTransaction(
                    user_id=driver.id,
                    amount=driver_payout,
                    transaction_type="driver_payout",
                    reference_id=sub_order.id,
                    description=f"Delivery payout for Order #{sub_order.id} (Tier: {int(driver_platform_commission*100)}% platform fee)"
                ))

        # Trigger real-time merchant webhook notification
        trigger_merchant_webhook(db, sub_order.id)

    db.commit()
    return True