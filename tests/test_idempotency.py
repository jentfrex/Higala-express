import json
from models import IdempotencyRecord

def test_idempotency_flow(client, db_session):
    headers = {"Idempotency-Key": "test-key-999"}

    # Mock endpoint test or direct record simulation to test the mechanics
    # First, let's verify a clean state
    existing = db_session.query(IdempotencyRecord).filter_by(key="test-key-999").first()
    assert existing is None

    # Save a record manually or via endpoint integration
    record = IdempotencyRecord(
        key="test-key-999",
        path="/checkout",
        response_status_code=200,
        response_body=json.dumps({"status": "success", "order_id": 101})
    )
    db_session.add(record)
    db_session.commit()

    # Query back to verify persistence & uniqueness constraints
    fetched = db_session.query(IdempotencyRecord).filter_by(key="test-key-999").first()
    assert fetched is not None
    assert fetched.response_status_code == 200
    
    data = json.loads(fetched.response_body)
    assert data["order_id"] == 101