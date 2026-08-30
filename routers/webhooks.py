from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, HttpUrl
from typing import List, Optional

from database import get_db
from models import WebhookSubscription, WebhookDeliveryLog, User
import httpx

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])

class WebhookCreate(BaseModel):
    url: str

class WebhookResponse(BaseModel):
    id: int
    merchant_id: int
    url: str
    is_active: bool

    class Config:
        orm_mode = True

class DeliveryLogResponse(BaseModel):
    id: int
    merchant_id: int
    event_type: str
    response_status: Optional[int]
    success: bool
    timestamp: str

    class Config:
        orm_mode = True

@router.post("/subscribe", response_model=WebhookResponse)
def register_webhook(data: WebhookCreate, merchant_owner_id: int, db: Session = Depends(get_db)):
    """Register or update a webhook endpoint URL for a merchant."""
    existing = db.query(WebhookSubscription).filter(WebhookSubscription.merchant_id == merchant_owner_id).first()
    if existing:
        existing.url = data.url
        existing.is_active = True
        db.commit()
        db.refresh(existing)
        return existing

    subscription = WebhookSubscription(
        merchant_id=merchant_owner_id,
        url=data.url,
        is_active=True
    )
    db.add(subscription)
    db.commit()
    db.refresh(subscription)
    return subscription

@router.patch("/{subscription_id}/toggle", response_model=WebhookResponse)
def toggle_webhook(subscription_id: int, db: Session = Depends(get_db)):
    """Enable or disable an active webhook subscription."""
    sub = db.query(WebhookSubscription).filter(WebhookSubscription.id == subscription_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Webhook subscription not found")
    
    sub.is_active = not sub.is_active
    db.commit()
    db.refresh(sub)
    return sub

@router.get("/logs/{merchant_id}", response_model=List[DeliveryLogResponse])
def get_delivery_logs(merchant_id: int, db: Session = Depends(get_db)):
    """View webhook delivery logs and attempt history for a merchant."""
    logs = db.query(WebhookDeliveryLog).filter(WebhookDeliveryLog.merchant_id == merchant_id).order_by(WebhookDeliveryLog.id.desc()).all()
    return logs

@router.post("/logs/{log_id}/retry")
def retry_webhook_delivery(log_id: int, db: Session = Depends(get_db)):
    """Manually retry a failed webhook delivery log."""
    log = db.query(WebhookDeliveryLog).filter(WebhookDeliveryLog.id == log_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="Webhook delivery log not found")

    subscription = db.query(WebhookSubscription).filter(WebhookSubscription.merchant_id == log.merchant_id).first()
    if not subscription or not subscription.is_active:
        raise HTTPException(status_code=400, detail="Merchant has no active webhook subscription")

    # Resend payload via HTTP POST
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.post(
                subscription.url,
                json=eval(log.payload) if isinstance(log.payload, str) else log.payload
            )
            log.response_status = response.status_code
            log.response_body = response.text
            log.success = 200 <= response.status_code < 300
    except Exception as e:
        log.response_body = str(e)
        log.success = False

    db.commit()
    return {"success": log.success, "response_status": log.response_status}