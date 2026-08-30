import httpx
import json
from sqlalchemy.orm import Session
import models

def trigger_webhook(db: Session, merchant_id: int, event_type: str, payload_data: dict):
    """
    Finds active webhook subscriptions for a merchant and dispatches 
    the event payload via a POST request, logging the delivery attempt.
    """
    subscriptions = db.query(models.WebhookSubscription).filter(
        models.WebhookSubscription.merchant_id == merchant_id,
        models.WebhookSubscription.is_active == True
    ).all()

    if not subscriptions:
        return

    payload_str = json.dumps(payload_data)

    for sub in subscriptions:
        success = False
        response_status = None
        response_body = None

        try:
            headers = {"Content-Type": "application/json"}
            if sub.secret:
                headers["X-Webhook-Secret"] = sub.secret

            with httpx.Client(timeout=5.0) as client:
                response = client.post(sub.url, content=payload_str, headers=headers)
                response_status = response.status_code
                response_body = response.text
                success = 200 <= response.status_code < 300
        except Exception as e:
            response_status = 500
            response_body = str(e)
            success = False

        # Log the delivery attempt
        delivery_log = models.WebhookDeliveryLog(
            merchant_id=merchant_id,
            event_type=event_type,
            payload=payload_str,
            response_status=response_status,
            response_body=response_body,
            success=success
        )
        db.add(delivery_log)
    
    db.commit()
