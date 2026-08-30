import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models
from database import Base, get_db
from main import app

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)

@pytest.fixture(autouse=True)
def db_session():
    """Create a clean database session for each test and bind it to dependency overrides."""
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    
    def override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    
    yield session
    
    session.close()
    transaction.rollback()
    connection.close()
    app.dependency_overrides.clear()


client = TestClient(app)


def test_driver_service_mode_toggle(db_session):
    """Test updating the driver's service mode (ride_only, delivery_only, both)."""
    driver = models.User(
        username="mode_test_driver",
        hashed_password="mocked_hash",
        role="driver",
        current_service_mode="both"
    )
    db_session.add(driver)
    db_session.commit()
    driver_id = driver.id

    from routers.auth import get_current_user
    
    def override_current_driver():
        return db_session.query(models.User).filter(models.User.id == driver_id).first()

    app.dependency_overrides[get_current_user] = override_current_driver

    # 1. Test switching to ride_only
    response_ride = client.post("/drivers/service-mode", json={"mode": "ride_only"})
    assert response_ride.status_code == 200
    assert response_ride.json()["success"] is True

    # Verify persistence in DB
    db_session.expire_all()
    updated_driver_ride = db_session.query(models.User).filter(models.User.id == driver_id).first()
    assert updated_driver_ride.current_service_mode == "ride_only"

    # 2. Test invalid mode rejection
    response_invalid = client.post("/drivers/service-mode", json={"mode": "teleport_mode"})
    assert response_invalid.status_code == 400


def test_driver_shift_workflow(db_session):
    """Test starting and ending a driver shift correctly updates driver status."""
    driver = models.User(
        username="shift_test_driver",
        hashed_password="mocked_hash",
        role="driver",
        status="offline"
    )
    db_session.add(driver)
    db_session.commit()
    driver_id = driver.id

    from routers.auth import get_current_user

    def override_current_driver_shift():
        return db_session.query(models.User).filter(models.User.id == driver_id).first()

    app.dependency_overrides[get_current_user] = override_current_driver_shift

    # Start Shift
    start_response = client.post("/drivers/shift/start")
    assert start_response.status_code == 200

    # Verify user status is online
    db_session.expire_all()
    user_status = db_session.query(models.User).filter(models.User.id == driver_id).first()
    assert user_status.status == "online"

    # End Shift
    end_response = client.post("/drivers/shift/end")
    assert end_response.status_code == 200

    # Verify user status is offline
    db_session.expire_all()
    user_status_offline = db_session.query(models.User).filter(models.User.id == driver_id).first()
    assert user_status_offline.status == "offline"