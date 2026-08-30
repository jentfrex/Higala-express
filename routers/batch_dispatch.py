from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import models
from database import get_db

router = APIRouter(prefix="/batch-dispatch", tags=["Batch Dispatch & Multi-Stop"])

@router.post("/create-batch")
def create_order_batch(driver_id: int, order_ids: list[int], db: Session = Depends(get_db)):
    """Group multiple pending orders into a single batch and assign them to one driver."""
    driver = db.query(models.User).filter(models.User.id == driver_id, models.User.role == "driver").first()
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found.")

    orders = db.query(models.Order).filter(models.Order.id.in_(order_ids)).all()
    if not orders:
        raise HTTPException(status_code=404, detail="No valid orders found for the given IDs.")

    assigned_orders = []
    for order in orders:
        if order.status != "pending":
            continue
        
        order.driver_id = driver_id
        order.status = "assigned_batch"
        assigned_orders.append(order.id)

    db.commit()

    return {
        "success": True,
        "message": f"Successfully batched {len(assigned_orders)} orders to driver {driver.username}.",
        "driver_id": driver_id,
        "batched_order_ids": assigned_orders
    }

@router.get("/driver-batch/{driver_id}")
def get_driver_active_batch(driver_id: int, db: Session = Depends(get_db)):
    """Get all active/assigned orders for a driver's multi-stop route."""
    batch_orders = db.query(models.Order).filter(
        models.Order.driver_id == driver_id,
        models.Order.status.in_(["assigned_batch", "picked_up"])
    ).all()

    return {
        "success": True,
        "driver_id": driver_id,
        "active_stops_count": len(batch_orders),
        "stops": [
            {
                "order_id": o.id,
                "item": o.item_description,
                "pickup": o.pickup_location,
                "dropoff": o.dropoff_location,
                "status": o.status,
                "price": o.price
            }
            for o in batch_orders
        ]
    }