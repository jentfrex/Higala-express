from fastapi import APIRouter

router = APIRouter(prefix="/api/admin/health", tags=["Admin Subsystem Health"])

@router.get("/", summary="Admin Subsystem Health Check")
async def admin_health_check():
    return {"success": True, "message": "Admin subsystem healthy", "status": "operational"}