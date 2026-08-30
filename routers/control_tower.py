from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timezone

import models
from database import get_db
from core.security import require_role, get_current_user

router = APIRouter(
    prefix="/control-tower",
    tags=["Control Tower Operations"],
    # Protect all control tower endpoints—only admins and dispatchers are permitted
    dependencies=[Depends(require_role(["admin", "dispatcher"]))]
)


# --- Request Models ---
class ReassignOrderRequest(BaseModel):
    order_id: int
    new_driver_id: int
    reason: str

class ForceCancelOrderRequest(BaseModel):
    order_id: int
    reason: str


# --- Endpoints ---

@router.get("/live-fleet")
def get_live_fleet_overview(db: Session = Depends(get_db)):
    """
    Returns all active online drivers with their current coordinates, 
    status, and assigned orders for map plotting.
    """
    drivers = db.query(models.User).filter(
        models.User.role == "driver",
        models.User.status.in_(["online", "busy", "delivering"])
    ).all()

    fleet_data = []
    for d in drivers:
        # Fetch current active order if delivering
        active_order = db.query(models.Order).filter(
            models.Order.driver_id == d.id,
            models.Order.status.in_(["assigned", "picked_up", "in_transit"])
        ).first()

        fleet_data.append({
            "driver_id": d.id,
            "username": d.username,
            "status": d.status,
            "latitude": getattr(d, "latitude", None),
            "longitude": getattr(d, "longitude", None),
            "current_order_id": active_order.id if active_order else None
        })

    return {
        "success": True,
        "total_active_drivers": len(fleet_data),
        "drivers": fleet_data
    }


@router.get("/active-orders")
def get_active_orders_map(db: Session = Depends(get_db)):
    """
    Returns all active orders in the system (pending, assigned, in-transit) 
    to place delivery markers on the GIS Control Tower map.
    """
    active_orders = db.query(models.Order).filter(
        models.Order.status.in_(["pending", "assigned", "picked_up", "in_transit"])
    ).all()

    return {
        "success": True,
        "active_orders_count": len(active_orders),
        "orders": active_orders
    }


@router.post("/reassign-order")
def reassign_order(
    payload: ReassignOrderRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Force-reassigns a stuck or delayed order to a new driver and logs the action in AuditLog.
    """
    order = db.query(models.Order).filter(models.Order.id == payload.order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    new_driver = db.query(models.User).filter(
        models.User.id == payload.new_driver_id,
        models.User.role == "driver"
    ).first()
    if not new_driver:
        raise HTTPException(status_code=404, detail="Target driver not found or user is not a driver")

    old_driver_id = order.driver_id

    # Update Order
    order.driver_id = new_driver.id
    order.status = "assigned"

    # Create Audit Log record
    audit_entry = models.AuditLog(
        user_id=current_user.id,
        action=f"REASSIGN_ORDER: Reassigned Order #{order.id} from Driver ID {old_driver_id} to Driver ID {new_driver.id}. Reason: {payload.reason}",
        timestamp=datetime.now(timezone.utc)
    )
    db.add(audit_entry)
    db.commit()

    return {
        "success": True,
        "detail": f"Order #{order.id} reassigned to driver {new_driver.username}",
        "previous_driver_id": old_driver_id,
        "new_driver_id": new_driver.id
    }


@router.post("/force-cancel")
def force_cancel_order(
    payload: ForceCancelOrderRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Emergency cancellation override for stuck or disputed orders.
    """
    order = db.query(models.Order).filter(models.Order.id == payload.order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    order.status = "cancelled"

    audit_entry = models.AuditLog(
        user_id=current_user.id,
        action=f"FORCE_CANCEL_ORDER: Order #{order.id} cancelled by dispatch. Reason: {payload.reason}",
        timestamp=datetime.now(timezone.utc)
    )
    db.add(audit_entry)
    db.commit()

    return {
        "success": True,
        "detail": f"Order #{order.id} force-cancelled by operations."
    }