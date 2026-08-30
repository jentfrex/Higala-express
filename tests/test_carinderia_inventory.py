from fastapi.testclient import TestClient
from main import app
import models
from database import SessionLocal

client = TestClient(app)

def get_or_create_test_branch():
    db = SessionLocal()
    brand = db.query(models.MerchantBrand).filter_by(name="Test Carinderia Brand").first()
    if not brand:
        brand = models.MerchantBrand(name="Test Carinderia Brand", category="Carinderia")
        db.add(brand)
        db.commit()
        db.refresh(brand)
        
    branch = db.query(models.MerchantBranch).filter_by(branch_name="Test Branch CDO").first()
    if not branch:
        branch = models.MerchantBranch(
            brand_id=brand.id,
            branch_name="Test Branch CDO",
            address="Divisoria, CDO",
            latitude=8.484,
            longitude=124.649
        )
        db.add(branch)
        db.commit()
        db.refresh(branch)
    branch_id = branch.id
    db.close()
    return branch_id


def test_set_carinderia_daily_menu():
    branch_id = get_or_create_test_branch()

    # Test setting daily menu portions (e.g., Humba - 5 servings)
    response = client.post(
        f"/partner-portal/branch/{branch_id}/daily-menu",
        json={
            "item_name": "Special Humba",
            "price": 95.0,
            "max_daily_stock": 5,
            "is_available": True
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] == True
    assert data["item"]["current_stock"] == 5
    assert data["item"]["is_available"] == True


def test_daily_stock_reset_flow():
    branch_id = get_or_create_test_branch()

    # 1. Setup an item with 3 servings
    client.post(
        f"/partner-portal/branch/{branch_id}/daily-menu",
        json={
            "item_name": "Paklay",
            "price": 80.0,
            "max_daily_stock": 3,
            "is_available": True
        }
    )

    # Fetch inventory to get item_id
    inv_res = client.get(f"/partner-portal/branch/{branch_id}/inventory")
    item = next(i for i in inv_res.json()["inventory"] if i["item_name"] == "Paklay")
    item_id = item["id"]

    # 2. Deduct all 3 servings to make it SOLD OUT
    deduct_res = client.post(
        f"/partner-portal/branch/{branch_id}/inventory/{item_id}/deduct",
        json={"quantity_sold": 3}
    )
    assert deduct_res.json()["current_stock"] == 0
    assert deduct_res.json()["is_available"] == False

    # 3. Trigger One-Click Daily Reset
    reset_res = client.post(f"/partner-portal/branch/{branch_id}/daily-reset")
    assert reset_res.status_code == 200
    assert reset_res.json()["success"] == True

    # 4. Verify item stock and availability are restored
    inv_check = client.get(f"/partner-portal/branch/{branch_id}/inventory")
    updated_item = next(i for i in inv_check.json()["inventory"] if i["item_name"] == "Paklay")
    assert updated_item["current_stock"] == 3
    assert updated_item["is_available"] == True