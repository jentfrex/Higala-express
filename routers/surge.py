from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List

import models
from database import get_db
from routers.auth import get_current_user

router = APIRouter(
    prefix="/surge",
    tags=["Surge Pricing"]
)

class SurgeCalculationRequest(BaseModel):
    base_fee: float
    is_peak_hour: bool = False
    is_bad_weather: bool = False
    active_order_volume: int = 0  # Number of unassigned orders in the queue

class SurgeCalculationResponse(BaseModel):
    base_fee: float
    surge_multiplier: float
    adjusted_delivery_fee: float
    driver_bonus: float
    reason: str

@router.post("/calculate", response_model=SurgeCalculationResponse)
def calculate_surge_fee(
    payload: SurgeCalculationRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    multiplier = 1.0
    reasons: List[str] = []

    # 1. Peak hours modifier
    if payload.is_peak_hour:
        multiplier += 0.25
        reasons.append("Peak hours")

    # 2. Bad weather modifier
    if payload.is_bad_weather:
        multiplier += 0.35
        reasons.append("Bad weather conditions")

    # 3. High-demand order volume modifier
    if payload.active_order_volume > 50:
        multiplier += 0.40
        reasons.append("High demand volume")
    elif payload.active_order_volume > 20:
        multiplier += 0.20
        reasons.append("Moderate demand volume")

    adjusted_fee = round(payload.base_fee * multiplier, 2)
    
    # Drivers receive an extra incentive bonus portion from the surge markup
    driver_bonus = round((adjusted_fee - payload.base_fee) * 0.60, 2) if multiplier > 1.0 else 0.0
    reason_str = ", ".join(reasons) if reasons else "Standard base rates apply"

    return {
        "base_fee": payload.base_fee,
        "surge_multiplier": round(multiplier, 2),
        "adjusted_delivery_fee": adjusted_fee,
        "driver_bonus": driver_bonus,
        "reason": reason_str
    }