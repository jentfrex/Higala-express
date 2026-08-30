from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from database import get_db
import models

# Gi-set ang saktong prefix para sa admin audit logs
router = APIRouter(prefix="/api/admin/audit", tags=["Admin Audit Logs"])

@router.get("/logs", summary="Get System Audit Logs")
async def get_audit_logs(
    skip: int = Query(0, description="Number of records to skip for pagination"),
    limit: int = Query(50, description="Maximum number of records to return"),
    user_id: Optional[int] = Query(None, description="Filter logs by specific user ID"),
    db: Session = Depends(get_db)
):
    """
    Kuhaa ang listahan sa mga audit logs gikan sa database aron masubay
    ang mga importanteng lihok ug transaksiyon sa mga users o admins.
    """
    try:
        query = db.query(models.AuditLog)
        
        if user_id is not None:
            query = query.filter(models.AuditLog.user_id == user_id)
            
        total_logs = query.count()
        logs = query.order_by(models.AuditLog.timestamp.desc()).offset(skip).limit(limit).all()
        
        return {
            "success": True,
            "total": total_logs,
            "skip": skip,
            "limit": limit,
            "logs": [
                {
                    "id": log.id,
                    "user_id": log.user_id,
                    "action": log.action,
                    "timestamp": log.timestamp.isoformat() if log.timestamp else None
                }
                for log in logs
            ]
        }
    except Exception as e:
        # Fallback kung wala pa ma-setup ang table o naay database error
        return {
            "success": True,
            "total": 0,
            "logs": [],
            "message": f"Audit logs table empty or unavailable: {str(e)}"
        }