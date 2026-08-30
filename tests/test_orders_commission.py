import pytest
from fastapi.testclient import TestClient
from database import get_db
from main import app
import models

def test_driver_commission_tier_transition(db_session, client):
    db = db_session

    # Create users without explicit primary keys to let SQLite handle autoincrement safely
    driver = models.User(
        username="driver_test_commission",
        hashed_password="fake",
        role="driver",
        status="online",
        wallet_balance=0.0,
        total_completed_deliveries=9
    )
    customer = models.User(
        username="customer_test_commission",
        hashed_password="fake",
        role="customer",
        wallet_balance=0.0,
        total_completed_deliveries=0
    )
    db.add_all([driver, customer])
    db.commit()
    db.refresh(driver)
    db.refresh(customer)

    order = models.Order(
        customer_id=customer.id,
        driver_id=driver.id,
        item_description="Test Package 1",
        pickup_location="Store A",
        dropoff_location="Location B",
        status="picked_up",  # <-- Changed to "picked_up"
        price=100.0,
        customer_latitude=0.0,
        customer_longitude=0.0
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    # Override authentication dependency to return our test driver
    from routers.auth import get_current_user
    app.dependency_overrides[get_current_user] = lambda: driver

    response = client.patch(
        f"/orders/{order.id}/complete",
        json={
            "driver_latitude": 0.0,
            "driver_longitude": 0.0,
            "flag_bad_pin": False
        }
    )

    assert response.status_code == 200, f"Response failed: {response.text}"
    data = response.json()
    assert data["success"] is True
    assert "Standard Tier (15% Commission)" in data["breakdown"]["driver_tier_applied"]
    assert data["breakdown"]["driver_earned_amount"] == 85.0
    assert data["breakdown"]["platform_driver_commission_amount"] == 15.0

    db.refresh(driver)
    assert driver.total_completed_deliveries == 10

    # Second order to test tier transition (Loyalty Tier)
    order_11 = models.Order(
        customer_id=customer.id,
        driver_id=driver.id,
        item_description="Test Package 2",
        pickup_location="Store A",
        dropoff_location="Location B",
        status="picked_up",  # <-- Changed from accepted to picked_up
        price=200.0,
        customer_latitude=0.0,
        customer_longitude=0.0
    )
    db.add(order_11)
    db.commit()
    db.refresh(order_11)

    response_11 = client.patch(
        f"/orders/{order_11.id}/complete",
        json={
            "driver_latitude": 0.0,
            "driver_longitude": 0.0,
            "flag_bad_pin": False
        }
    )

    assert response_11.status_code == 200, f"Response 2 failed: {response_11.text}"
    data_11 = response_11.json()
    assert "Loyalty Tier (6% Commission)" in data_11["breakdown"]["driver_tier_applied"]
    assert data_11["breakdown"]["driver_earned_amount"] == 188.0
    assert data_11["breakdown"]["platform_driver_commission_amount"] == 12.0