import httpx
from sqlalchemy.orm import Session
from models import WebhookSubscription, WebhookDeliveryLog, Order, Merchant

def trigger_merchant_webhook(db: Session, order_id: int):
    """
    Finds the merchant associated with an order, checks if they have an active webhook subscription,
    and dispatches a real-time HTTP POST notification payload.
    """
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order or not order.merchant_id:
        return

    merchant = db.query(Merchant).filter(Merchant.id == order.merchant_id).first()
    if not merchant or not merchant.owner_id:
        return

    # Look for active webhook subscription for this merchant owner
    subscription = db.query(WebhookSubscription).filter(
        WebhookSubscription.merchant_id == merchant.owner_id,
        WebhookSubscription.is_active == True
    ).first()

    if not subscription:
        return  # No webhook configured for this merchant

    payload_data = {
        "event": "order.created",
        "sub_order_id": order.id,
        "master_order_id": order.master_order_id,
        "item_description": order.item_description,
        "price": order.price,
        "pickup_location": order.pickup_location,
        "dropoff_location": order.dropoff_location,
        "status": order.status
    }

    # Attempt to dispatch the webhook via HTTP POST using json parameter
    response_status = None
    response_body = None
    success = False

    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.post(
                subscription.url,
                json=payload_data
            )
            response_status = response.status_code
            response_body = response.text
            success = 200 <= response.status_code < 300
    except Exception as e:
        response_body = str(e)
        success = False

    # Log the delivery attempt
    delivery_log = WebhookDeliveryLog(
        merchant_id=merchant.owner_id,
        event_type="order.created",
        payload=str(payload_data),
        response_status=response_status,
        response_body=response_body,
        success=success
    )
    db.add(delivery_log)
    db.commit()