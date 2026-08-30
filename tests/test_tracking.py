import pytest
from fastapi.testclient import TestClient
from main import app
import models
from database import Base, engine

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_tracking_test_db():
    # Ensures all tables are created in the test database for tracking tests
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

def test_websocket_live_tracking(client, db_session):
    # Seed a dummy order with id 12345 in the test database so the tracking endpoint finds it
    existing_order = db_session.query(models.Order).filter(models.Order.id == 12345).first()
    if not existing_order:
        test_order = models.Order(
            id=12345,
            item_description="Test Delivery Item",
            pickup_location="Store A",
            dropoff_location="Customer B",
            price=150.0,
            status="pending"
        )
        db_session.add(test_order)
        db_session.commit()

    order_id = 12345

    # Connect to the tracking WebSocket endpoint and verify broadcast loop
    with client.websocket_connect(f"/tracking/ws/{order_id}") as websocket:
        # Simulate a rider sending GPS coordinates
        gps_payload = {"lat": 8.4834, "lng": 124.6319, "status": "on_the_way"}
        websocket.send_json(gps_payload)

        # Receive the echoed/broadcasted coordinates back from the socket
        data = websocket.receive_json()
        
        assert data["lat"] == 8.4834
        assert data["lng"] == 124.6319
        assert data["status"] == "on_the_way"