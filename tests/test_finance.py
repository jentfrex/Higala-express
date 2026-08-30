from fastapi.testclient import TestClient
from main import app
from database import SessionLocal
from models import User, Merchant

def test_split_checkout_with_finances():
    client = TestClient(app)
    db = SessionLocal()

    try:
        # 1. Create a test customer with enough wallet balance
        customer = User(username="test_buyer_finance", hashed_password="fake", role="customer", wallet_balance=5000.0)
        db.add(customer)

        # 2. Create test merchant owners
        merchant_owner_1 = User(username="merchant_owner_1", hashed_password="fake", role="merchant", wallet_balance=0.0)
        merchant_owner_2 = User(username="merchant_owner_2", hashed_password="fake", role="merchant", wallet_balance=0.0)
        db.add_all([merchant_owner_1, merchant_owner_2])
        db.commit()

        # 3. Create test merchants linked to their owners
        merchant_1 = Merchant(name="Inasal Joint", owner_id=merchant_owner_1.id, is_active=True)
        merchant_2 = Merchant(name="Rice Wholesaler", owner_id=merchant_owner_2.id, is_active=True)
        db.add_all([merchant_1, merchant_2])
        db.commit()

        # Payload representing a multi-vendor split cart checkout
        payload = {
            "customer_id": customer.id,
            "items": [
                {
                    "merchant_id": merchant_1.id,
                    "item_name": "Chicken Inasal",
                    "quantity": 2,
                    "price": 100.0,  # Total: 200.0
                    "pickup_location": "Uptown",
                    "dropoff_location": "Downtown"
                },
                {
                    "merchant_id": merchant_2.id,
                    "item_name": "Sack of Rice",
                    "quantity": 1,
                    "price": 1800.0,  # Total: 1800.0
                    "pickup_location": "Agora",
                    "dropoff_location": "Downtown"
                }
            ]
        }

        # Grand total should be 200.0 + 1800.0 = 2000.0
        response = client.post("/checkout/split", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["total_amount"] == 2000.0
        assert len(data["sub_order_ids"]) == 2

        # Verify wallet balances after automatic split settlement (10% commission rate)
        db.expire_all()
        
        updated_customer = db.query(User).filter(User.id == customer.id).first()
        updated_owner_1 = db.query(User).filter(User.id == merchant_owner_1.id).first()
        updated_owner_2 = db.query(User).filter(User.id == merchant_owner_2.id).first()

        # Customer balance check updated to 3000.0 (5000.0 - 2000.0 total cart cost)
        assert updated_customer.wallet_balance == 3000.0

        # Merchant 1 net payout: 200.0 - 10% commission (20.0) = 180.0
        assert updated_owner_1.wallet_balance == 180.0

        # Merchant 2 net payout: 1800.0 - 10% commission (180.0) = 1620.0
        assert updated_owner_2.wallet_balance == 1620.0

    finally:
        db.close()