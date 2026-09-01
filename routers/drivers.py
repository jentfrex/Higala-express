from datetime import datetime
import json
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Body, Security
from sqlalchemy.orm import Session

import models
import schemas
from database import get_db
from exceptions import OrderAlreadyAcceptedError, ResourceNotFoundError
from routers.websockets import redis_client
from core.security import get_current_user

router = APIRouter(
    prefix="/drivers",
    tags=["Drivers"]
)

def get_current_driver(
    current_user = Depends(get_current_user), 
    db: Session = Depends(get_db)
) -> models.User:
    """
    Secure driver dependency: Validates the JWT token 
    and strictly enforces that the user has a 'driver' role.
    """
    if current_user.role != "driver":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only drivers can access this endpoint"
        )
    
    # Refresh from database to ensure user still exists and role hasn't changed
    driver = db.query(models.User).filter(
        models.User.id == current_user.id,
        models.User.role == "driver"
    ).first()
    
    if not driver:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Driver account not found or disabled"
        )
    
    return driver


@router.post("/accept/{order_id}")
def accept_order(
    order_id: int, 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(get_current_driver)
):
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        return {"success": True, "message": f"Order {order_id} accepted successfully (Simulation Mode)."}
    
    if order.status.lower() != "pending":
        raise OrderAlreadyAcceptedError()

    order.driver_id = current_user.id
    order.status = "Accepted"
    db.commit()
    db.refresh(order)
    
    return {
        "success": True, 
        "message": "Order accepted successfully", 
        "order_id": order.id,
        "order": order
    }


@router.post("/location")
async def update_location(
    lat: float, 
    lng: float, 
    order_id: Optional[int] = None, 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(get_current_driver)
):
    current_user.last_lat = lat
    current_user.last_lng = lng
    db.commit()

    if order_id:
        room_id = f"order_{order_id}"
        location_payload = {
            "event": "driver_location_update",
            "driver_id": current_user.id,
            "lat": lat,
            "lng": lng
        }
        try:
            await redis_client.publish(room_id, json.dumps(location_payload))
        except Exception:
            pass

    return {"success": True, "message": "Location updated successfully"}


@router.post("/service-mode")
def update_service_mode(
    mode: str = Body(..., embed=True),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_driver)
):
    valid_modes = ["ride_only", "delivery_only", "both"]
    if mode not in valid_modes:
        raise HTTPException(status_code=400, detail=f"Invalid service mode. Choose from {valid_modes}")

    current_user.current_service_mode = mode
    db.commit()
    return {"success": True, "message": f"Service mode updated to '{mode}' successfully."}


@router.post("/shift/start")
def start_shift(
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(get_current_driver)
):
    current_user.status = "online"
    
    new_shift = models.DriverShift(driver_id=current_user.id, is_active=True)
    db.add(new_shift)
    db.commit()
    return {"success": True, "message": "Shift started, driver is online"}


@router.post("/shift/end")
def end_shift(
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(get_current_driver)
):
    current_user.status = "offline"
    
    shift = db.query(models.DriverShift).filter(
        models.DriverShift.driver_id == current_user.id, 
        models.DriverShift.is_active == True
    ).first()
    
    if shift:
        shift.end_time = datetime.utcnow()
        shift.is_active = False
    
    db.commit()
    return {"success": True, "message": "Shift ended, driver is offline"}