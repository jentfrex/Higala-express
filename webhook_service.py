import json
import asyncio
import logging
import httpx
from sqlalchemy.orm import Session
import models
from database import SessionLocal

logger = logging.getLogger("higala.webhooks")

async def trigger_webhook(
    db: Session, 
    merchant_id: int, 
    event_data: dict, 
    max_retries: int = 3
):
    # Find active webhook subscriptions for this merchant
    subscriptions = (
        db.query(models.WebhookSubscription)
        .filter(
            models.WebhookSubscription.merchant_id == merchant_id,
            models.WebhookSubscription.is_active == True,
        )
        .all()
    )

    if not subscriptions:
        return

    payload_str = json.dumps(event_data)
    event_type = event_data.get("event", "unknown")

    async with httpx.AsyncClient() as client:
        for sub in subscriptions:
            status_code = None
            response_text = None
            success = False
            
            # Exponential backoff loop (2s, 4s...)
            for attempt in range(1, max_retries + 1):
                try:
                    logger.debug(f"Webhook attempt {attempt} to {sub.url}")
                    response = await client.post(
                        sub.url, 
                        json=event_data, 
                        timeout=10.0,
                        headers={"X-Webhook-Attempt": str(attempt)}
                    )
                    status_code = response.status_code
                    response_text = response.text
                    
                    if response.status_code in [200, 201, 202, 204]:
                        success = True
                        break
                    else:
                        logger.warning(f"Attempt {attempt} failed for {sub.url} (HTTP {status_code})")
                        
                # Catch exceptions properly to avoid silent failures
                except httpx.RequestError as e:
                    response_text = f"Network error: {str(e)}"
                    logger.error(f"Attempt {attempt} network exception for {sub.url}: {e}")
                except Exception as e:
                    response_text = f"Unexpected error: {str(e)}"
                    logger.error(f"Attempt {attempt} unexpected exception for {sub.url}: {e}")

                # Wait before retrying (Exponential Backoff)
                if not success and attempt < max_retries:
                    backoff_delay = 2 ** attempt  
                    await asyncio.sleep(backoff_delay)

            # Dead Letter Queue via WebhookDeliveryLog
            log_entry = models.WebhookDeliveryLog(
                merchant_id=merchant_id,
                event_type=event_type,
                payload=payload_str,
                response_status=status_code,
                response_body=response_text[:1000] if response_text else None,
                success=success
            )
            db.add(log_entry)
            
            # Notify/Disable broken webhooks so merchants know
            if not success:
                logger.critical(f"Webhook {sub.id} max retries exhausted. Auto-disabling.")
                sub.is_active = False  

            try:
                db.commit()
            except Exception as e:
                db.rollback()
                logger.error(f"Failed to commit webhook delivery log: {e}")


def send_webhook_notification(merchant_id: int, event_type: str, payload: dict):
    """
    Synchronous fallback wrapper for background tasks if needed.
    """
    db = SessionLocal()
    try:
        payload_str = json.dumps(payload)
        delivery_log = models.WebhookDeliveryLog(
            merchant_id=merchant_id,
            event_type=event_type,
            payload=payload_str,
            response_status=None,
            response_body="Queued for background delivery",
            success=False # Explicitly set to false until fully processed
        )
        db.add(delivery_log)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Webhook background dispatch failed: {e}")
    finally:
        db.close()