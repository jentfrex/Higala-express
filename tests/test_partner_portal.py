import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

import database
import models
from main import app

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

# Reconfigure database globally and create tables immediately
database.configure_database(engine)
database.Base.metadata.create_all(bind=engine)
TestingSessionLocal = database.SessionLocal

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[database.get_db] = override_get_db

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_database():
    database.Base.metadata.create_all(bind=engine)
    yield
    database.Base.metadata.drop_all(bind=engine)

def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["success"] is True

def test_partner_portal_branch_not_found():
    response = client.get("/partner-portal/branch/99999/analytics")
    assert response.status_code == 404
    data = response.json()
    assert "Micro-hub / Branch not found" in str(data)

def test_partner_portal_inventory_empty_check():
    response = client.get("/partner-portal/branch/99999/inventory")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["inventory"] == []

def test_get_branch_analytics():
    db = TestingSessionLocal()
    if not db.query(models.MerchantBrand).filter_by(id=1).first():
        db.add(models.MerchantBrand(id=1, name="Cagayan Delicacies"))
    branch = models.MerchantBranch(
        id=1, brand_id=1, branch_name="Cagayan Hub", address="Divisoria, CDO", latitude=8.4772, longitude=124.6459
    )
    db.add(branch)
    db.add(models.Order(id=101, branch_id=1, price=350.0, status="pending"))
    db.commit()
    db.close()

    response = client.get("/partner-portal/branch/1/analytics")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["branch_name"] == "Cagayan Hub"
    assert data["analytics"]["total_orders"] == 1

def test_get_branch_orders_with_pagination_and_filter():
    db = TestingSessionLocal()
    if not db.query(models.MerchantBrand).filter_by(id=1).first():
        db.add(models.MerchantBrand(id=1, name="Cagayan Delicacies"))
    if not db.query(models.MerchantBranch).filter_by(id=1).first():
        db.add(models.MerchantBranch(
            id=1, brand_id=1, branch_name="Cagayan Hub", address="Divisoria, CDO", latitude=8.4772, longitude=124.6459
        ))
    db.add(models.Order(id=101, branch_id=1, price=350.0, status="pending"))
    db.commit()
    db.close()

    response = client.get("/partner-portal/branch/1/orders")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert len(data["orders"]) == 1

    response_filtered = client.get("/partner-portal/branch/1/orders?status=pending")
    assert response_filtered.status_code == 200
    assert len(response_filtered.json()["orders"]) == 1

    response_empty = client.get("/partner-portal/branch/1/orders?status=completed")
    assert response_empty.status_code == 200
    assert len(response_empty.json()["orders"]) == 0

def test_cancel_or_reject_branch_order():
    db = TestingSessionLocal()
    if not db.query(models.MerchantBrand).filter_by(id=1).first():
        db.add(models.MerchantBrand(id=1, name="Cagayan Delicacies"))
    if not db.query(models.MerchantBranch).filter_by(id=1).first():
        db.add(models.MerchantBranch(
            id=1, brand_id=1, branch_name="Cagayan Hub", address="Divisoria, CDO", latitude=8.4772, longitude=124.6459
        ))
    if not db.query(models.Order).filter_by(id=101).first():
        db.add(models.Order(id=101, branch_id=1, price=350.0, status="pending"))
    db.commit()
    db.close()

    payload = {"reason": "Kitchen ran out of ingredients"}
    response = client.post("/partner-portal/branch/1/orders/101/cancel", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["status"] == "rejected"
    assert data["reason"] == "Kitchen ran out of ingredients"

    response_retry = client.post("/partner-portal/branch/1/orders/101/cancel", json=payload)
    assert response_retry.status_code == 400

def test_deduct_carinderia_stock():
    db = TestingSessionLocal()
    if not db.query(models.MerchantBrand).filter_by(id=1).first():
        db.add(models.MerchantBrand(id=1, name="Cagayan Delicacies"))
    if not db.query(models.MerchantBranch).filter_by(id=1).first():
        db.add(models.MerchantBranch(
            id=1, brand_id=1, branch_name="Cagayan Hub", address="Divisoria, CDO", latitude=8.4772, longitude=124.6459
        ))
    if not db.query(models.BranchInventory).filter_by(id=1).first():
        db.add(models.BranchInventory(
            id=1, branch_id=1, item_name="Chicken Sisig", price=150.0,
            max_daily_stock=10, current_stock=10, is_available=True, is_daily_special=True
        ))
    db.commit()
    db.close()

    payload = {"quantity_sold": 2}
    response = client.post("/partner-portal/branch/1/inventory/1/deduct", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["current_stock"] == 8
    assert data["is_available"] is True