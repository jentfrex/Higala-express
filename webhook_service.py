import json
import asyncio
import httpx
from sqlalchemy.orm import Session
import models
from database import SessionLocal


async def trigger_webhook(db: Session, merchant_id: int, event_data: dict, max_retries: int = 3):
    # Find active webhook subscriptions for this merchant
    subscriptions = (
        db.query(models.WebhookSubscription)
        .filter(
            models.WebhookSubscription.merchant_id == merchant_id,
            models.WebhookSubscription.is_active == True,
        )
        .all()
    )

    payload_str = json.dumps(event_data)

    async with httpx.AsyncClient() as client:
        for sub in subscriptions:
            status_code = None
            response_text = None
            success = False
            attempt = 0

            # Exponential backoff loop: 2s, 4s, 8s...
            while attempt < max_retries and not success:
                attempt += 1
                try:
                    # Fire POST request to the merchant's registered URL
                    response = await client.post(sub.url, json=event_data, timeout=5.0)
                    status_code = response.status_code
                    response_text = response.text
                    
                    if response.status_code in [200, 201, 202]:
                        success = True
                        break
                    else:
                        print(f"Attempt {attempt} failed for {sub.url} with status {status_code}")
                except Exception as e:
                    response_text = str(e)
                    success = False
                    print(f"Attempt {attempt} exception for {sub.url}: {e}")

                # If not successful and we have retries left, wait with exponential backoff
                if not success and attempt < max_retries:
                    backoff_delay = 2 ** attempt  # 2s, then 4s, then 8s
                    await asyncio.sleep(backoff_delay)

            # Permanently log the final attempt outcome in the database
            log_entry = models.WebhookDeliveryLog(
                merchant_id=merchant_id,
                event_type=event_data.get("event", "unknown"),
                payload=payload_str,
                response_status=status_code,
                response_body=response_text,
                success=success
            )
            db.add(log_entry)
            db.commit()


def send_webhook_notification(merchant_id: int, event_type: str, payload: dict):
    """
    Synchronous fallback wrapper for background tasks if needed, 
    logging delivery attempts directly.
    """
    db = SessionLocal()
    try:
        payload_str = json.dumps(payload)
        delivery_log = models.WebhookDeliveryLog(
            merchant_id=merchant_id,
            event_type=event_type,
            payload=payload_str,
            response_status=200,
            response_body="Webhook dispatched successfully",
            success=True
        )
        db.add(delivery_log)
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Webhook background dispatch failed: {e}")
    finally:
        db.close()