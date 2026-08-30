from fastapi import APIRouter, Query
from typing import Optional

router = APIRouter(prefix="/api/admin/exports", tags=["Admin Data Exports"])

@router.post("/", summary="Create Data Export Job")
async def create_export_job(
    export_type: str = Query("transactions", description="Type of data to export: transactions, drivers, or orders")
):
    return {
        "success": True, 
        "message": f"Export job for '{export_type}' successfully initiated.",
        "download_url": f"/api/admin/exports/download/mock-{export_type}.csv"
    }