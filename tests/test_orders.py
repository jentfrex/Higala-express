import pytest
from fastapi.testclient import TestClient
from database import SessionLocal, Base, get_db
from main import app
from models import User, Merchant

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_unauthorized_order_creation():
    response = client.post("/orders/", json={
        "item_description": "Test Meal",
        "pickup_location": "Uptown",
        "dropoff_location": "Downtown",
        "price": 150.0
    })
    assert response.status_code == 401

def test_split_checkout_insufficient_wallet():
    db = SessionLocal()
    try:
        customer = User(
            username="poor_customer_test", 
            hashed_password="fake", 
            role="customer", 
            wallet_balance=50.0
        )
        db.add(customer)

        owner = User(
            username="merchant_owner_test", 
            hashed_password="fake", 
            role="merchant", 
            wallet_balance=0.0
        )
        db.add(owner)
        db.commit()

        merchant = Merchant(name="Test Rice Store", owner_id=owner.id, is_active=True)
        db.add(merchant)
        db.commit()
        
        db.refresh(customer)
        db.refresh(merchant)

        payload = {
            "customer_id": customer.id,
            "items": [
                {
                    "merchant_id": merchant.id,
                    "item_name": "Premium Rice Sack",
                    "quantity": 1,
                    "price": 2200.0,
                    "pickup_location": "Agora Market",
                    "dropoff_location": "Uptown CDO"
                }
            ]
        }

        response = client.post("/checkout/split", json=payload)
        assert response.status_code == 400
        
        data = response.json()
        error_message = str(data.get("detail", data.get("message", data)))
        assert "insufficient" in error_message.lower()
    finally:
        db.query(Merchant).filter(Merchant.id == merchant.id).delete()
        db.query(User).filter(User.id.in_([customer.id, owner.id])).delete()
        db.commit()
        db.close()