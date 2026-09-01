# database.py - Production Ready with Safe Soft Deletes & SQLAlchemy 2.0 Support
import os
from datetime import datetime
from sqlalchemy import create_engine, Column, Boolean, DateTime, select
from sqlalchemy.orm import sessionmaker, Session, declarative_base
from sqlalchemy.ext.hybrid import hybrid_property

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
# Soft Delete Mixin (SQLAlchemy 2.0 Compatible)
# -------------------------------
class SoftDeleteMixin:
    """Better soft-delete pattern using hybrid properties and safe ORM attributes"""
    is_deleted = Column(Boolean, default=False, nullable=False, index=True)
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

    @hybrid_property
    def is_active(self):
        """Check if record is active (not soft-deleted)"""
        return not self.is_deleted

    def soft_delete(self, db_session: Session):
        """Safely soft-delete a record"""
        self.is_deleted = True
        self.deleted_at = datetime.utcnow()
        db_session.commit()


# -------------------------------
# Safe Query Helper (Prevents SQL Injection & Fragile Custom Queries)
# -------------------------------
def get_active_query(db: Session, model_class):
    """
    Returns a query that only includes non-deleted records safely 
    using standard SQLAlchemy 2.0 filtering methods.
    """
    return db.query(model_class).filter(model_class.is_deleted == False)


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