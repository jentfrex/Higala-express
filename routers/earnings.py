from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import models
from database import get_db
from core.security import get_current_user  # Siguruha nga naka-import kini sakto

router = APIRouter(prefix="/earnings", tags=["Driver Earnings"])

@router.get("/driver/{driver_id}")
def get_driver_earnings_summary(driver_id: int, db: Session = Depends(get_db)):
    """Get total completed deliveries, current commission tier, total earned fees, and payout history for a driver."""
    driver = db.query(models.User.id, models.User.total_completed_deliveries).filter(models.User.id == driver_id).first()
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")

    completed_orders = db.query(models.Order).filter(
        models.Order.driver_id == driver_id,
        models.Order.status == "completed"
    ).all()

    total_deliveries = driver.total_completed_deliveries or len(completed_orders)
    total_earned = sum(order.delivery_fee for order in completed_orders if order.delivery_fee)
    payouts = db.query(models.DriverPayout).filter(models.DriverPayout.driver_id == driver_id).all()

    # Determine current tier status
    if total_deliveries >= 10:
        current_tier = "Loyalty Tier"
        active_commission_rate = "6%"
        rides_remaining_for_discount = 0
    else:
        current_tier = "Standard Tier"
        active_commission_rate = "15%"
        rides_remaining_for_discount = max(0, 10 - total_deliveries)

    return {
        "success": True,
        "driver_id": driver_id,
        "total_deliveries": total_deliveries,
        "commission_tier_status": {
            "current_tier": current_tier,
            "active_platform_commission": active_commission_rate,
            "rides_completed": total_deliveries,
            "rides_remaining_until_6_percent": rides_remaining_for_discount,
            "incentive_description": "Enjoy 15% commission on your first 10 successful rides, dropping automatically to 6% for all subsequent rides!"
        },
        "total_earned": total_earned,
        "payouts": [
            {"id": p.id, "amount": p.amount, "status": p.status, "created_at": p.created_at}
            for p in payouts
        ]
    }

@router.post("/request-payout/{driver_id}")
def request_payout(
    driver_id: int, 
    amount: float, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Allow a driver to securely request a cash-out payout of their earnings with strict authorization and locks."""
    
    # 1. Strict Authorization: Only the driver themselves or an admin can request payout
    if current_user.id != driver_id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Not authorized to request payout for this account."
        )

    if amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Payout amount must be greater than zero."
        )

    # 2. Row-level locking to prevent race conditions & double-spending
    driver = db.query(models.User).filter(models.User.id == driver_id).with_for_update().first()
    if not driver:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Driver not found")

    current_balance = driver.wallet_balance or 0.0
    if amount > current_balance:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=f"Invalid payout amount. Available wallet balance is only ₱{current_balance}."
        )

    # 3. Deduct amount from user wallet and create pending payout record
    driver.wallet_balance = current_balance - amount

    new_payout = models.DriverPayout(
        driver_id=driver_id,
        amount=amount,
        status="pending"
    )
    db.add(new_payout)
    db.commit()
    db.refresh(new_payout)
    db.refresh(driver)

    return {
        "success": True,
        "message": "Payout request submitted successfully!",
        "payout_id": new_payout.id,
        "amount": amount,
        "remaining_wallet_balance": driver.wallet_balance
    }