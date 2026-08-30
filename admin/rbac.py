from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Dict

router = APIRouter(prefix="/api/admin", tags=["Admin RBAC Management"])

# Centralized Role Permissions Mapping
ROLE_PERMISSIONS: Dict[str, List[str]] = {
    "super_admin": ["read", "write", "delete", "finance_refund", "manage_staff"],
    "support_agent": ["read_orders", "write_support_tickets"],
    "city_operations": ["read_drivers", "manage_geofence"]
}

class RoleUpdatePayload(BaseModel):
    permissions: List[str] = Field(..., description="List of permission strings to assign to the role")

@router.get("/rbac/roles", summary="Get All Role Permissions")
async def get_all_roles():
    """
    Kuhaa ang tanang magamit nga roles ug ang ilang tagsa-tagsang permissions sa sistema.
    """
    return {"success": True, "roles": ROLE_PERMISSIONS}

@router.put("/rbac/roles/{role_name}", summary="Update Role Permissions")
async def update_role_permissions(role_name: str, payload: RoleUpdatePayload):
    """
    I-update ang mga permissions sa usa ka piho nga role sa Admin Control Tower.
    """
    if role_name not in ROLE_PERMISSIONS:
        raise HTTPException(status_code=404, detail=f"Role '{role_name}' not found")
    
    ROLE_PERMISSIONS[role_name] = payload.permissions
    return {
        "success": True, 
        "message": f"Permissions for role '{role_name}' updated successfully.",
        "updated_permissions": ROLE_PERMISSIONS[role_name]
    }