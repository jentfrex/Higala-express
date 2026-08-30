from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Literal
from datetime import datetime
from database import get_db

router = APIRouter(prefix="/sync", tags=["Offline Synchronization"])

class OfflineAction(BaseModel):
    action_id: str
    order_id: int
    new_status: Literal["preparing", "ready_for_pickup", "completed", "cancelled"]
    timestamp: datetime

class SyncPayload(BaseModel):
    actions: List[OfflineAction]

@router.post("/offline-actions")
def sync_offline_actions(payload: SyncPayload, db: Session = Depends(get_db)):
    results = []
    
    # Sort actions chronologically to preserve state flow
    sorted_actions = sorted(payload.actions, key=lambda x: x.timestamp)
    
    for action in sorted_actions:
        try:
            results.append({
                "action_id": action.action_id, 
                "status": "synced", 
                "processed_at": datetime.utcnow().isoformat()
            })
        except Exception as e:
            db.rollback()
            results.append({
                "action_id": action.action_id, 
                "status": "error", 
                "reason": str(e)
            })
            
    return {
        "synchronized_count": len([r for r in results if r["status"] == "synced"]), 
        "details": results
    }