import os
from datetime import datetime
from sqlalchemy import create_engine, Column, Boolean, DateTime
from sqlalchemy.orm import sessionmaker, Query, declarative_base
from passlib.context import CryptContext

# Password hashing context for ajentq seeding
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Base
Base = declarative_base()

def get_database_url():
    if os.getenv("TESTING") == "1":
        return "sqlite:///./test_higala.db"
    return os.getenv("DATABASE_URL", "sqlite:///./higala_express.db")

# Create engine dynamically
def get_engine():
    url = get_database_url()
    return create_engine(
        url,
        connect_args={"check_same_thread": False} if "sqlite" in url else {}
    )

# Global engine and session for runtime/testing
engine = get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Function to allow runtime rebinding (used in tests)
def configure_database(new_engine=None):
    global engine, SessionLocal
    if new_engine:
        engine = new_engine
    else:
        engine = get_engine()
    SessionLocal.configure(bind=engine)
    return engine

# Debug information
print("=" * 60)
print("DATABASE URL :", get_database_url())
print("=" * 60)


# -------------------------------
# Soft Delete Query
# -------------------------------
class SoftDeleteQuery(Query):
    def __new__(cls, *args, **kwargs):
        obj = super().__new__(cls)
        if len(args) > 0:
            super(SoftDeleteQuery, obj).__init__(*args, **kwargs)
            return obj.filter(cls._get_model_class().is_deleted == False)
        return obj

    @classmethod
    def _get_model_class(cls):
        return getattr(cls, "_model_class", None)

    def __init__(self, entities, session=None, **kwargs):
        if entities:
            self._model_class = (
                entities[0] if hasattr(entities[0], "is_deleted") else None
            )
        super().__init__(entities, session, **kwargs)

        if self._model_class and hasattr(self._model_class, "is_deleted"):
            self.session = session


# -------------------------------
# Soft Delete Mixin
# -------------------------------
class SoftDeleteMixin:
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime, nullable=True)

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )

    def soft_delete(self, db_session):
        self.is_deleted = True
        self.deleted_at = datetime.utcnow()
        db_session.commit()


# -------------------------------
# Dependency
# -------------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Register all models so SQLAlchemy knows about them
import models

# Automatically seed/create the 'ajentq' account into the database if missing
def seed_ajentq_account():
    db = SessionLocal()
    try:
        existing_user = db.query(models.User).filter(models.User.username == "ajentq").first()
        if not existing_user:
            hashed_pw = pwd_context.hash("101391@Jent")
            ajentq_user = models.User(
                username="ajentq",
                hashed_password=hashed_pw,
                role="driver",
                status="online"
            )
            db.add(ajentq_user)
            db.commit()
            print("Successfully created 'ajentq' account in the database!")
        else:
            print("'ajentq' account already exists in database.")
    except Exception as e:
        db.rollback()
        print(f"Error seeding ajentq account: {e}")
    finally:
        db.close()

# Run table creation and automatic seeding on startup
Base.metadata.create_all(bind=engine)
seed_ajentq_account()