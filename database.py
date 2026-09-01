import os
from datetime import datetime
from sqlalchemy import create_engine, Column, Boolean, DateTime
from sqlalchemy.orm import sessionmaker, Query, declarative_base

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

# Run table creation on startup
Base.metadata.create_all(bind=engine)