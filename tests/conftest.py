import os

# 1. DELETE ANY STALE TEST DB IMMEDIATELY to prevent schema conflicts
TEST_DB_PATH = "./test_higala_absolute.db"
if os.path.exists(TEST_DB_PATH):
    try:
        os.remove(TEST_DB_PATH)
    except Exception:
        pass

# 2. FORCE ENV VARS BEFORE ANY IMPORTS HAPPEN
os.environ["TESTING"] = "1"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH}"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from sqlalchemy.ext.compiler import compiles
from geoalchemy2.types import Geometry

@compiles(Geometry, "sqlite")
def sqlite_geometry_compiler(element, compiler, **kw):
    return "VARCHAR"

# 3. LATE IMPORTS - Ensures main.py and database.py pick up the env vars above
import database
import models
from main import app

test_engine = create_engine(
    f"sqlite:///{TEST_DB_PATH}",
    connect_args={"check_same_thread": False},
)

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

# 4. GLOBALLY OVERRIDE DATABASE MODULE REFERENCES
database.engine = test_engine
database.SessionLocal = TestingSessionLocal
database.Base.metadata.bind = test_engine

@pytest.fixture(scope="session", autouse=True)
def setup_database():
    # Create tables ONCE per test run
    database.Base.metadata.create_all(bind=test_engine)
    
    db = TestingSessionLocal()
    try:
        users_to_seed = [
            models.User(username="test_webhook_buyer", hashed_password="fake", role="customer", wallet_balance=5000.0, escrow_balance=0.0, status="offline"),
            models.User(username="test_merchant", hashed_password="fake", role="merchant", wallet_balance=1000.0, status="online"),
            models.User(username="test_driver", hashed_password="fake", role="driver", wallet_balance=500.0, status="online", total_completed_deliveries=0),
        
        ]
        for u in users_to_seed:
            if not db.query(models.User).filter_by(username=u.username).first():
                db.add(u)
        db.commit()
    except Exception as e:
        db.rollback()
        print("Seeding error:", e)
    finally:
        db.close()

    yield
    
    # Cleanup after ALL tests finish
    database.Base.metadata.drop_all(bind=test_engine)
    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except Exception:
            pass

@pytest.fixture(scope="function")
def db_session():
    """Use this fixture in your tests to get a clean database session!"""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture(scope="function", autouse=True)
def override_db(db_session):
    def _override_get_db():
        yield db_session
        
    app.dependency_overrides[database.get_db] = _override_get_db
    yield
    app.dependency_overrides.clear()

@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c