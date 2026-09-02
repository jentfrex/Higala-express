from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from database import get_db
from services.dispatcher import find_optimal_driver

router = APIRouter(prefix="/dispatch", tags=["Dispatch"])

class DispatchRequest(BaseModel):
    merchant_lat: float
    merchant_lon: float
    max_radius_km: float = 5.0
    driver_username: str | None = None 

@router.post("/find-driver")
def dispatch_nearest_driver(data: DispatchRequest, db: Session = Depends(get_db)):
    """Finds the optimal available driver near the merchant using Haversine formula."""
    
    result = find_optimal_driver(db, data.merchant_lat, data.merchant_lon, data.max_radius_km)
    
    if not result:
        raise HTTPException(
            status_code=404, 
            detail="No available drivers found within the specified radius."
        )
            
    return {
        "success": True,
        "dispatch_details": result
    }