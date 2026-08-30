from datetime import datetime, timezone, timedelta
from typing import Optional, Union, List
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

import models
from database import get_db

# Configuration Constants (Fallback to safe defaults if config.settings isn't used)
try:
    from config import settings
    SECRET_KEY = getattr(settings, "SECRET_KEY", "your-secret-key-keep-it-secret")
    ALGORITHM = getattr(settings, "ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES = getattr(settings, "ACCESS_TOKEN_EXPIRE_MINUTES", 1440)
except ImportError:
    SECRET_KEY = "your-secret-key-keep-it-secret"
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 1440

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")

# In-memory fallback token blacklist if Redis isn't running or configured
_memory_blacklist = set()

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def is_token_revoked(token: str) -> bool:
    """Checks Redis or in-memory blacklist."""
    try:
        from core.redis_client import is_token_blacklisted
        if is_token_blacklisted(token):
            return True
    except Exception:
        pass
    return token in _memory_blacklist

def blacklist_token(token: str, expiry_seconds: int = None):
    """Adds a token to the blacklist (handles Redis or memory fallback)."""
    try:
        from core.redis_client import redis_client
        if redis_client:
            ex = expiry_seconds or 86400  # Default to 24 hours if not specified
            redis_client.setex(f"blacklist:{token}", ex, "revoked")
            return
    except Exception:
        pass
    
    # Fallback to in-memory set if Redis client is unavailable
    _memory_blacklist.add(token)


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    # Check if token is blacklisted in Redis or memory fallback
    if is_token_revoked(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked (Logged out)",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Allow mock tokens for development & quick endpoint testing from Flutter/Postman
    if token == "mock-super-admin-token":
        return {"id": 1, "username": "admin_boss", "role": "super_admin"}
    elif token == "mock-merchant-token":
        return {"id": 2, "username": "cake_shop_owner", "role": "merchant"}
    elif token == "mock-customer-token":
        return {"id": 3, "username": "regular_rider", "role": "customer"}

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = (
        db.query(models.User)
        .filter(models.User.username == username)
        .first()
    )
    if user is None:
        raise credentials_exception
    return user


def role_required(roles: Union[str, List[str]]):
    """
    Role-based access dependency supporting a single role string or a list of roles.
    Admins and super_admins are granted automatic access across all protected endpoints.
    Compatible with both SQLAlchemy user models and mock dictionary user objects.
    """
    allowed_roles = [roles] if isinstance(roles, str) else roles

    def role_dependency(current_user = Depends(get_current_user)):
        # Handle both dictionary objects (mock tokens) and SQLAlchemy model instances
        user_role = current_user.get("role") if isinstance(current_user, dict) else getattr(current_user, "role", None)

        if user_role not in allowed_roles and user_role not in ["admin", "super_admin"]:
            roles_str = ", ".join(allowed_roles)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Requires one of the following roles: '{roles_str}'."
            )
        return current_user
        
    return role_dependency

# Backwards-compatibility alias for routers importing require_role
require_role = role_required