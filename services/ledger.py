from decimal import Decimal
from sqlalchemy.orm import Session

PLATFORM_COMMISSION_RATE = Decimal("0.15") # 15% platform cut
BASE_DELIVERY_FEE = Decimal("50.00")      # Base PHP delivery fee

def process_order_financials(db: Session, order_id: int, order_subtotal: Decimal, delivery_distance_km: Decimal):
    from models import FinancialLedgerEntry
    
    platform_fee = order_subtotal * PLATFORM_COMMISSION_RATE
    merchant_payout = order_subtotal - platform_fee
    
    # Scale delivery fee by distance beyond 2km
    driver_earnings = BASE_DELIVERY_FEE + (max(Decimal("0.0"), delivery_distance_km - Decimal("2.0")) * Decimal("10.0"))
    
    ledger_entry = FinancialLedgerEntry(
        order_id=order_id,
        subtotal=order_subtotal,
        platform_commission=platform_fee,
        merchant_payout=merchant_payout,
        driver_earnings=driver_earnings
    )
    
    db.add(ledger_entry)
    db.commit()
    db.refresh(ledger_entry)
    
    return ledger_entry