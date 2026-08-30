from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import Optional, List

router = APIRouter(prefix="/api/admin/broadcast", tags=["Admin Broadcasts"])

class BroadcastMessage(BaseModel):
    title: str = Field(..., description="Title of the broadcast notification")
    body: str = Field(..., description="Content body of the message")
    target_audience: str = Field(..., description="Target group e.g., 'all_drivers', 'all_customers', 'zone_cdo'")
    scheduled_at: Optional[str] = Field(None, description="Optional schedule timestamp")

BROADCAST_HISTORY = []

@router.post("/send", summary="Send or Schedule Broadcast")
async def send_broadcast(payload: BroadcastMessage):
    broadcast_record = {
        "id": len(BROADCAST_HISTORY) + 1,
        "title": payload.title,
        "body": payload.body,
        "target_audience": payload.target_audience,
        "scheduled_at": payload.scheduled_at,
        "status": "scheduled" if payload.scheduled_at else "sent_immediatly"
    }
    BROADCAST_HISTORY.append(broadcast_record)
    return {"success": True, "message": "Broadcast notification processed successfully.", "data": broadcast_record}

@router.get("/history", summary="Get Broadcast History")
async def get_broadcast_history():
    return {"success": True, "history": BROADCAST_HISTORY}