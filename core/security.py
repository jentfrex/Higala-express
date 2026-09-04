"""
Security and authentication module for Higala Express.
Handles password hashing, JWT creation, token revoking, and role-based authorization.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional, Union, List
import os
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

import models
from database import get_db
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

# Configuration Constants from central settings
from config import settings

SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")

# In-memory fallback token blacklist if Redis isn't running or configured
_memory_blacklist = set()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against its hashed version."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Generate a bcrypt hash of a plain password."""
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Generate JWT access token with expiry and role payload."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def is_token_revoked(token: str) -> bool:
    """Checks Redis or in-memory blacklist using safe helpers."""
    try:
        from core.redis_client import is_token_blacklisted
        if is_token_blacklisted(token):
            return True
    except Exception:
        pass
    return token in _memory_blacklist

def blacklist_token(token: str, expiry_seconds: Optional[int] = None):
    """Adds a token to the blacklist (handles Redis or memory fallback safely)."""
    try:
        from core.redis_client import blacklist_token as redis_blacklist
        ex = expiry_seconds or 86400  # Default to 24 hours
        redis_blacklist(token, expire_seconds=ex)
        return
    except Exception:
        pass
    
    # Fallback to in-memory set
    _memory_blacklist.add(token)


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
):
    """Retrieves current user from JWT token and verifies status."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    # Check if token is blacklisted
    if is_token_revoked(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked (Logged out)",
            headers={"WWW-Authenticate": "Bearer"},
        )

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

    # Enforce active check
    if hasattr(user, "is_active") and not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive or suspended."
        )

    return user


def role_required(roles: Union[str, List[str]]):
    """
    Role-based access dependency supporting single role string or a list of roles.
    Admins and super_admins are granted automatic access across all protected endpoints.
    Enforces 'active' status approval checks for drivers and merchants.
    """
    allowed_roles = [roles] if isinstance(roles, str) else roles

    def role_dependency(current_user = Depends(get_current_user)):
        user_role = current_user.get("role") if isinstance(current_user, dict) else getattr(current_user, "role", None)
        user_status = current_user.get("status") if isinstance(current_user, dict) else getattr(current_user, "status", "active")

        # Admin override
        if user_role in ["admin", "super_admin"]:
            return current_user

        # Validate Role
        if user_role not in allowed_roles:
            roles_str = ", ".join(allowed_roles)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Requires one of the following roles: '{roles_str}'."
            )

        # Enforce Directive 3.1: Admin approval check for drivers and merchants
        if user_role in ["driver", "merchant"] and user_status == "pending_approval":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your account registration is pending admin approval."
            )

        return current_user
        
    return role_dependency

# Backwards-compatibility alias for routers
require_role = role_required