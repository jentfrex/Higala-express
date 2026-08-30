from sqlalchemy.orm import Session
import models

def background_log_audit(db_factory, user_id: int, action: str, details: str = None):
    """Background task to write audit logs asynchronously without delaying API responses."""
    db = db_factory()
    try:
        log = models.AuditLog(user_id=user_id, action=action, details=details)
        db.add(log)
        db.commit()
    finally:
        db.close()
