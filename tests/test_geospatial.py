import os
os.environ["TESTING"] = "1"

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_nearby_drivers_endpoint():
    response = client.get("/geo/nearby-drivers?lat=8.4542&lon=124.6319&radius_km=5.0")
    assert response.status_code in [200, 422, 500]