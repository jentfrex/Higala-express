from sqlalchemy.orm import Session
import models
from database import SessionLocal  # Siguraduha nga naay SessionLocal o Session maker sa imong database.py

async def background_log_audit(ctx, user_id: int, action: str, details: str = None):
    """
    Background task to write audit logs asynchronously via ARQ without delaying API responses.
    """
    db = SessionLocal()
    try:
        log = models.AuditLog(user_id=user_id, action=action, details=details)
        db.add(log)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()