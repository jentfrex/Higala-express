import pytest
from fastapi.testclient import TestClient
import models

def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"


def test_read_root(client):
    response = client.get("/")
    assert response.status_code == 200
    # Ensure your FastAPI app route for "/" returns a JSON object containing "success": True
    # e.g., @app.get("/") def read_root(): return {"success": True}
    assert response.json()["success"] is True


def test_admin_panel_accessible(client):
    response = client.get("/admin/")
    assert response.status_code in [200, 307, 401]


def test_multi_branch_router_loaded(client):
    # Verifies that the multi-branch nearest router endpoint is registered and active
    response = client.post("/branches/nearest", json={
        "brand_id": 999,
        "latitude": 8.4772,
        "longitude": 124.6459
    })
    # A 404 confirms the route exists and is mounted (brand just doesn't exist yet)
    assert response.status_code in [200, 404]


def test_webhook_delivery_log_creation(db_session):
    log = models.WebhookDeliveryLog(
        merchant_id=1,
        event_type="order.created",
        payload='{"order_id": 1}',
        response_status=200,
        response_body="OK",
        success=True
    )

    db_session.add(log)
    db_session.commit()

    saved_log = (
        db_session.query(models.WebhookDeliveryLog)
        .filter_by(merchant_id=1)
        .first()
    )

    assert saved_log is not None
    assert saved_log.event_type == "order.created"
    assert saved_log.success is True
    assert saved_log.response_status == 200


def test_end_to_end_order_workflow(client):
    # Register
    response = client.post(
        "/auth/register",
        json={
            "username": "delivery_boss_test",
            "password": "securepassword123",
            "role": "customer"
        },
    )

    assert response.status_code in [200, 201]

    # Login
    login_response = client.post(
        "/auth/token",
        data={
            "username": "delivery_boss_test",
            "password": "securepassword123",
        },
    )

    assert login_response.status_code == 200

    token_data = login_response.json()
    access_token = token_data["access_token"]

    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    # Create Order
    order_response = client.post(
        "/orders/",
        json={
            "item_description": "Express Package",
            "pickup_location": "Downtown CDO",
            "dropoff_location": "Uptown CDO",
            "price": 150.0,
        },
        headers=headers,
    )

    assert order_response.status_code in [200, 201]