from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict

router = APIRouter(prefix="/admin", tags=["Admin Dashboard"])

# Mock database of role permissions
ROLE_PERMISSIONS: Dict[str, List[str]] = {
    "super_admin": ["read", "write", "delete", "finance_refund", "manage_staff"],
    "support_agent": ["read_orders", "write_support_tickets"],
    "city_operations": ["read_drivers", "manage_geofence"]
}

class RoleUpdatePayload(BaseModel):
    permissions: List[str]

@router.get("/rbac/roles")
async def get_all_roles():
    return {"success": True, "roles": ROLE_PERMISSIONS}

@router.put("/rbac/roles/{role_name}")
async def update_role_permissions(role_name: str, payload: RoleUpdatePayload):
    if role_name not in ROLE_PERMISSIONS:
        raise HTTPException(status_code=404, detail="Role not found")
    ROLE_PERMISSIONS[role_name] = payload.permissions
    return {
        "success": True, 
        "message": f"Permissions for role '{role_name}' updated successfully.",
        "updated_permissions": ROLE_PERMISSIONS[role_name]
    }