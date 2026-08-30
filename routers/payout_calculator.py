from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import models
from database import get_db

router = APIRouter(prefix="/payouts", tags=["Automated Payout Calculations"])

@router.post("/calculate-batch-payout/{driver_id}")
def calculate_batch_payout(driver_id: int, db: Session = Depends(get_db)):
    """
    Calculate tiered commissions and multi-stop bonuses for a driver's completed batch orders.
    Base rate per order + bonus multiplier for multi-stop efficiency.
    """
    driver = db.query(models.User).filter(models.User.id == driver_id, models.User.role == "driver").first()
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found.")

    # Fetch completed or delivered orders assigned to this driver that haven't been processed yet
    batch_orders = db.query(models.Order).filter(
        models.Order.driver_id == driver_id,
        models.Order.status == "delivered"
    ).all()

    if not batch_orders:
        raise HTTPException(status_code=400, detail="No completed/delivered orders found for payout calculation.")

    base_rate_per_order = 50.0  # Base delivery commission in local currency units
    multi_stop_bonus_flat = 30.0 # Extra bonus for handling multi-stop batches

    total_orders = len(batch_orders)
    calculated_base_total = total_orders * base_rate_per_order
    
    # Apply multi-stop tier bonus if they handled more than 1 stop in a batch run
    bonus = multi_stop_bonus_flat if total_orders > 1 else 0.0
    total_payout = calculated_base_total + bonus

    return {
        "success": True,
        "driver_id": driver_id,
        "driver_name": driver.username,
        "completed_deliveries": total_orders,
        "base_earnings": calculated_base_total,
        "multi_stop_bonus": bonus,
        "total_calculated_payout": total_payout,
        "currency": "PHP"
    }