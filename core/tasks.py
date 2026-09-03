from sqlalchemy.orm import Session
import models
from database import SessionLocal
from config import settings
from arq.connections import RedisSettings

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

# ARQ Worker Settings configuration para basahon gyud ang saktong REDIS_URL sa Render
class WorkerSettings:
    functions = [background_log_audit]
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)