from fastapi.testclient import TestClient
from datetime import date
from fastapi import FastAPI
from routers.dispatch import router as dispatch_router

app = FastAPI()
app.include_router(dispatch_router)

client = TestClient(app)

def get_birthdate_for_age(age: int) -> str:
    today = date.today()
    birth_year = today.year - age
    return date(birth_year, today.month, today.day).isoformat()

def test_dispatch_normal_driver(monkeypatch):
    """Test that standard drivers receive orders regardless of customer demographics."""
    monkeypatch.setattr("routers.dispatch.find_optimal_driver", lambda db, lat, lon, radius: {
        "driver_username": "driver123",
        "customer_profile": {"gender": "male", "birthdate": get_birthdate_for_age(25)}
    })

    response = client.post("/dispatch/find-driver", json={
        "merchant_lat": 8.4542,
        "merchant_lon": 124.6319,
        "max_radius_km": 5.0
    })

    assert response.status_code == 200
    assert response.json()["success"] is True


    response = client.post("/dispatch/find-driver", json={
        "merchant_lat": 8.4542,
        "merchant_lon": 124.6319,
        "max_radius_km": 5.0
    })

    assert response.status_code == 200
    assert response.json()["success"] is True


    response = client.post("/dispatch/find-driver", json={
        "merchant_lat": 8.4542,
        "merchant_lon": 124.6319,
        "max_radius_km": 5.0
    })

    assert response.status_code == 404
    assert response.json()["detail"] == "No available drivers found within the specified radius."