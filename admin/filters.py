from fastapi import APIRouter

router = APIRouter()

@router.get("/filters")
async def get_admin_filters():
    return {"success": True, "message": "Admin filters endpoint active"}