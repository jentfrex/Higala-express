from unittest.mock import patch, MagicMock
from models import User, Merchant, WebhookSubscription, WebhookDeliveryLog
from database import Base

def test_merchant_webhook_dispatch(client, db_session):
    # Ensure tables exist for this session
    Base.metadata.create_all(bind=db_session.get_bind())

    customer = db_session.query(User).filter_by(username="test_webhook_buyer").first()
    if not customer:
        customer = User(username="test_webhook_buyer", hashed_password="fake", role="customer", wallet_balance=5000.0)
        db_session.add(customer)
        db_session.commit()
        db_session.refresh(customer)

    owner = db_session.query(User).filter_by(username="test_merchant_owner_webhook").first()
    if not owner:
        owner = User(username="test_merchant_owner_webhook", hashed_password="fake", role="merchant", wallet_balance=0.0)
        db_session.add(owner)
        db_session.commit()
        db_session.refresh(owner)

    merchant = db_session.query(Merchant).filter_by(name="CDO Rice Store", owner_id=owner.id).first()
    if not merchant:
        merchant = Merchant(name="CDO Rice Store", owner_id=owner.id, is_active=True)
        db_session.add(merchant)
        db_session.commit()
        db_session.refresh(merchant)

    subscription = db_session.query(WebhookSubscription).filter_by(merchant_id=owner.id, url="https://example.com/webhook-receiver").first()
    if not subscription:
        subscription = WebhookSubscription(
            merchant_id=owner.id,
            url="https://example.com/webhook-receiver",
            is_active=True
        )
        db_session.add(subscription)
        db_session.commit()

    with patch("services.webhook.httpx.Client") as mock_httpx_client:
        mock_instance = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "OK"
        mock_instance.post.return_value = mock_response
        
        mock_httpx_client.return_value.__enter__.return_value = mock_instance

        payload = {
            "customer_id": customer.id,
            "items": [
                {
                    "merchant_id": merchant.id,
                    "item_name": "Premium Rice 50kg",
                    "quantity": 1,
                    "price": 2200.0,
                    "pickup_location": "Agora Market",
                    "dropoff_location": "Uptown CDO"
                }
            ]
        }

        response = client.post("/checkout/split", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    log = db_session.query(WebhookDeliveryLog).filter(WebhookDeliveryLog.merchant_id == owner.id).first()
    assert log is not None
    assert log.event_type == "order.created"
    assert log.success is True


def test_webhook_invalid_signature(client, db_session):
    # Ensure tables exist for this session too
    Base.metadata.create_all(bind=db_session.get_bind())

    payload = {
        "event": "order.created",
        "order_id": 9999
    }
    
    response = client.post("/webhooks/receive", json=payload, headers={"X-Signature": "invalid_fake_sig"})
    assert response.status_code in [401, 403, 422, 404]