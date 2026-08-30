import sys
from fastapi.testclient import TestClient
from main import app

print("--- DEBUG INFO ---")
print("Loaded 'app' from module:", app.__module__)
print("Active application routes:")
for route in app.routes:
    if hasattr(route, "path"):
        print(f"  Path: {route.path} | Name: {route.name}")
print("------------------")

client = TestClient(app)

def test_admin_rbac_roles():
    response = client.get("/api/admin/rbac/roles")
    print(f"Test requested URL: /api/admin/rbac/roles -> Status: {response.status_code}")
    print("Response text:", response.text)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "roles" in data