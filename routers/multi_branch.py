from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
import math

import models
from database import get_db

router = APIRouter(prefix="/branches", tags=["Multi-Branch Management"])

# --- Pydantic Schemas ---
class NearestBranchRequest(BaseModel):
    brand_id: int
    latitude: float
    longitude: float


# Helper function: Haversine formula to calculate distance in KM between user and branch
def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0  # Radius of the earth in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


# 1. Find the Nearest Branch based on Customer GPS coordinates
@router.post("/nearest")
def find_nearest_branch(payload: NearestBranchRequest, db: Session = Depends(get_db)):
    branches = db.query(models.MerchantBranch).filter(
        models.MerchantBranch.brand_id == payload.brand_id,
        models.MerchantBranch.is_active == True
    ).all()

    if not branches:
        raise HTTPException(status_code=404, detail="No active branches found for this brand.")

    nearest_branch = None
    min_distance = float('inf')

    for branch in branches:
        distance = calculate_distance(payload.latitude, payload.longitude, branch.latitude, branch.longitude)
        if distance <= branch.geofence_radius_km and distance < min_distance:
            min_distance = distance
            nearest_branch = branch

    if not nearest_branch:
        raise HTTPException(status_code=400, detail="You are outside the delivery geofence for all branches of this brand.")

    return {
        "success": True,
        "nearest_branch_id": nearest_branch.id,
        "branch_name": nearest_branch.branch_name,
        "address": nearest_branch.address,
        "distance_km": round(min_distance, 2)
    }


# 2. Toggle item stock availability for a specific branch
@router.patch("/{branch_id}/inventory/{item_id}")
def update_branch_inventory_status(branch_id: int, item_id: int, is_available: bool, db: Session = Depends(get_db)):
    item = db.query(models.BranchInventory).filter(
        models.BranchInventory.id == item_id,
        models.BranchInventory.branch_id == branch_id
    ).first()

    if not item:
        raise HTTPException(status_code=404, detail="Inventory item not found for this specific branch.")

    item.is_available = is_available
    db.commit()

    return {
        "success": True,
        "message": f"Item '{item.item_name}' availability updated to {is_available} for branch ID {branch_id}"
    }