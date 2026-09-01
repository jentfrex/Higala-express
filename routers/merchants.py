from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

import models
import schemas
from database import get_db
from core.security import get_current_user
from core.logging import get_logger

logger = get_logger("merchants")

router = APIRouter(
    prefix="/merchants",
    tags=["Merchants & Webhooks"]
)


def get_current_merchant(
    current_user: models.User = Depends(get_current_user), 
    db: Session = Depends(get_db)
) -> models.User:
    """Validates merchant access and pending approval status."""
    if current_user.role not in ["merchant", "admin", "super_admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only merchants can access this endpoint."
        )

    if getattr(current_user, "status", "active") == "pending_approval":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Merchant account is pending admin approval."
        )

    return current_user


@router.post("/subscribe")
def subscribe_webhook(
    webhook: schemas.WebhookSubscribe, 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(get_current_merchant)
):
    new_sub = models.WebhookSubscription(
        merchant_id=webhook.merchant_id,
        url=webhook.url
    )
    db.add(new_sub)
    db.commit()
    db.refresh(new_sub)
    
    logger.info(f"Webhook subscription created for merchant {webhook.merchant_id}")
    return {"message": "Webhook subscription created successfully", "subscription_id": new_sub.id}


@router.get("/subscriptions/{merchant_id}")
def get_subscriptions(
    merchant_id: int, 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(get_current_merchant)
):
    subs = db.query(models.WebhookSubscription).filter(
        models.WebhookSubscription.merchant_id == merchant_id
    ).all()
    return subs