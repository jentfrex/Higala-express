from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, Any

router = APIRouter(prefix="/api/admin/features", tags=["Admin Feature Flags"])

FEATURE_FLAGS: Dict[str, bool] = {
    "surge_pricing_enabled": True,
    "beta_merchant_portal": False,
    "instant_driver_payouts": True,
}

class FeatureFlagUpdate(BaseModel):
    enabled: bool

class FeatureFlagCreate(BaseModel):
    name: str = Field(..., description="Unique name of the feature flag")
    enabled: bool

@router.get("/", summary="Get All Feature Flags")
async def get_all_feature_flags():
    return {"success": True, "flags": FEATURE_FLAGS}

@router.patch("/{flag_name}", summary="Update Feature Flag Status")
async def update_feature_flag(flag_name: str, payload: FeatureFlagUpdate):
    if flag_name not in FEATURE_FLAGS:
        raise HTTPException(status_code=404, detail="Feature flag not found")
    FEATURE_FLAGS[flag_name] = payload.enabled
    return {"success": True, "message": f"Feature '{flag_name}' updated to {payload.enabled}", "flags": FEATURE_FLAGS}

@router.post("/", summary="Create New Feature Flag")
async def create_feature_flag(payload: FeatureFlagCreate):
    if payload.name in FEATURE_FLAGS:
        raise HTTPException(status_code=400, detail="Feature flag already exists")
    FEATURE_FLAGS[payload.name] = payload.enabled
    return {"success": True, "message": f"Feature flag '{payload.name}' created.", "flags": FEATURE_FLAGS}