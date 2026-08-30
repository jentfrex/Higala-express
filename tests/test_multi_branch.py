import pytest
import models

def test_find_nearest_branch(client, db_session):
    brand = db_session.query(models.MerchantBrand).filter_by(id=1).first()
    if not brand:
        brand = models.MerchantBrand(id=1, name="Higala Burger", category="Fast Food")
        db_session.merge(brand)
        db_session.commit()
    
    branch_uptown = db_session.query(models.MerchantBranch).filter_by(id=1).first()
    if not branch_uptown:
        branch_uptown = models.MerchantBranch(
            id=1,
            brand_id=1,
            branch_name="Higala Burger - Uptown",
            address="Masterson Avenue, CDO",
            latitude=8.4772,
            longitude=124.6459,
            geofence_radius_km=5.0,
            is_active=True
        )
        db_session.merge(branch_uptown)
        db_session.commit()

    response = client.post("/branches/nearest", json={
        "brand_id": 1,
        "latitude": 8.4775,
        "longitude": 124.6460
    })
    data = response.json()
    assert response.status_code == 200
    assert data["success"] is True
    assert data["nearest_branch_id"] == 1
    # Updated to check for 'Higala Burger - Uptown' or 'CDO' to match your seed definition
    assert "Uptown" in data["branch_name"] or "CDO" in data["branch_name"]


def test_out_of_geofence_branch(client):
    response = client.post("/branches/nearest", json={
        "brand_id": 1,
        "latitude": 14.5995,
        "longitude": 120.9842
    })
    assert response.status_code in [400, 404]


def test_update_branch_inventory(client, db_session):
    item = models.BranchInventory(
        id=1,
        branch_id=1,
        item_name="Cheeseburger",
        price=150.0,
        is_available=True
    )
    db_session.merge(item)
    db_session.commit()

    response = client.patch("/branches/1/inventory/1?is_available=false")
    data = response.json()
    assert response.status_code == 200
    assert data["success"] is True
    # Checked for 'False' matching Python's boolean capitalization in the response string
    assert "False" in data["message"]