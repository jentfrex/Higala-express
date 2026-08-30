from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

import models
import schemas
from database import get_db
from routers.auth import get_current_user

router = APIRouter(
    prefix="/merchants",
    tags=["Merchants & Webhooks"]
)


@router.post("/subscribe")
def subscribe_webhook(
    webhook: schemas.WebhookSubscribe, 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(get_current_user)
):
    new_sub = models.WebhookSubscription(
        merchant_id=webhook.merchant_id,
        url=webhook.url
    )
    db.add(new_sub)
    db.commit()
    db.refresh(new_sub)
    return {"message": "Webhook subscription created successfully", "subscription_id": new_sub.id}


@router.get("/subscriptions/{merchant_id}")
def get_subscriptions(
    merchant_id: int, 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(get_current_user)
):
    subs = db.query(models.WebhookSubscription).filter(
        models.WebhookSubscription.merchant_id == merchant_id
    ).all()
    return subs