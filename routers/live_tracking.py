from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
import models
from database import get_db

router = APIRouter(prefix="/tracking", tags=["Live Tracking & ETA"])

class LocationUpdate(BaseModel):
    driver_id: int
    latitude: float
    longitude: float

# In-memory store for quick GPS lookups (can also be saved to DB if persistence is needed)
active_driver_locations = {}

@router.post("/update-location")
def update_driver_location(data: LocationUpdate, db: Session = Depends(get_db)):
    """Allows a driver to broadcast their real-time coordinates."""
    driver = db.query(models.User).filter(models.User.id == data.driver_id, models.User.role == "driver").first()
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found.")

    # Store latest location
    active_driver_locations[data.driver_id] = {
        "latitude": data.latitude,
        "longitude": data.longitude
    }

    return {
        "success": True,
        "message": "Location updated successfully.",
        "driver_id": data.driver_id,
        "coordinates": {"latitude": data.latitude, "longitude": data.longitude}
    }

@router.get("/driver-location/{driver_id}")
def get_driver_location(driver_id: int):
    """Fetch the latest real-time location of a specific driver for customer mapping."""
    location = active_driver_locations.get(driver_id)
    if not location:
        raise HTTPException(status_code=404, detail="Live location not found or driver is offline.")

    return {
        "success": True,
        "driver_id": driver_id,
        "coordinates": location
    }