from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel

import models
import schemas
from database import get_db
from routers.auth import get_current_user

router = APIRouter(
    prefix="/notifications",
    tags=["Notifications"]
)

class NotificationPayload(BaseModel):
    user_id: int
    title: str
    message: str
    channel: str = "push"  # "push" or "sms"

def send_external_alert(user_id: int, title: str, message: str, channel: str):
    # Placeholder for actual third-party provider integration (e.g., Twilio for SMS, FCM for Push)
    print(f"Sending external {channel.upper()} to User ID {user_id}: \"{title} - {message}\"")

@router.post("/send", status_code=status.HTTP_202_ACCEPTED)
def trigger_notification(
    payload: NotificationPayload,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # Ensure only authorized roles or internal services can trigger broad alerts
    if current_user.role not in ["admin", "merchant"]:
        raise HTTPException(status_code=403, detail="Not authorized to dispatch notifications")
        
    # Verify user exists
    target_user = db.query(models.User).filter(models.User.id == payload.user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="Target user not found")

    # Dispatch alert asynchronously
    background_tasks.add_task(
        send_external_alert,
        user_id=payload.user_id,
        title=payload.title,
        message=payload.message,
        channel=payload.channel
    )

    return {"status": "success", "detail": "Notification queued successfully"}