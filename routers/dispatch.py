from datetime import date
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

def calculate_age(birthdate) -> int:
    today = date.today()
    if isinstance(birthdate, str):
        birthdate = date.fromisoformat(birthdate)
    return today.year - birthdate.year - ((today.month, today.day) < (birthdate.month, birthdate.day))

def passes_ajentq_filters(order_or_customer_profile: dict) -> bool:
    """
    Strict filter for username 'ajentq': 
    Only allows requests from female customers aged 20 to 28.
    """
    customer_gender = order_or_customer_profile.get("gender")
    customer_birthdate = order_or_customer_profile.get("birthdate")
    
    if not customer_gender or not customer_birthdate:
        return False  
        
    age = calculate_age(customer_birthdate)
    
    if customer_gender.lower() == "female" and 20 <= age <= 28:
        return True
    return False

@router.post("/find-driver")
def dispatch_nearest_driver(data: DispatchRequest, db: Session = Depends(get_db)):
    """Finds the optimal available driver near the merchant using Haversine formula."""
    
    result = find_optimal_driver(db, data.merchant_lat, data.merchant_lon, data.max_radius_km)
    
    if not result:
        raise HTTPException(
            status_code=404, 
            detail="No available drivers found within the specified radius."
        )
    
    matched_driver_username = result.get("driver_username") or result.get("username")
    
    if matched_driver_username == "ajentq":
        customer_profile = result.get("customer_profile", {})
        
        if not passes_ajentq_filters(customer_profile):
            raise HTTPException(
                status_code=404,
                detail="No available drivers found within the specified radius."
            )
            
    return {
        "success": True,
        "dispatch_details": result
    }