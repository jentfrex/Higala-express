from datetime import timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from slowapi import Limiter
from slowapi.util import get_remote_address
from fastapi import APIRouter, Depends, HTTPException, status, Request

import models
import schemas
from database import get_db
from core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    get_current_user,
    blacklist_token,
    oauth2_scheme,
    ACCESS_TOKEN_EXPIRE_MINUTES
)
from core.logging import get_logger

logger = get_logger("auth")
limiter = Limiter(key_func=get_remote_address)

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)

class PasswordChangePayload(BaseModel):
    old_password: str
    new_password: str

class LoginRequest(BaseModel):
    username: str
    password: str


# Helper Function for Portal Login Processing
def _process_portal_login(login_data: LoginRequest, target_role: str, db: Session):
    user = db.query(models.User).filter(models.User.username == login_data.username).first()
    
    # 1. Verify user credentials
    if not user or not verify_password(login_data.password, user.hashed_password):
        logger.warning(f"Failed login attempt for username: {login_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 2. Strict Role Portal Authorization Check
    user_role = getattr(user, "role", None)
    if target_role == "admin" and user_role not in ["admin", "super_admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Admin portal restricted to administrators."
        )
    elif target_role != "admin" and user_role != target_role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied. This account cannot log in via the {target_role} portal."
        )

    # 3. Check Account Approval Status for Drivers & Merchants
    user_status = getattr(user, "status", "active")
    if user_role in ["driver", "merchant"] and user_status == "pending_approval":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account registration is still pending admin approval."
        )

    logger.info(f"User {user.username} successfully logged in via {target_role} portal.", extra={"user_id": user.id})

    # 4. Generate Access Token with embedded role claim
    access_token = create_access_token(
        data={"sub": user.username, "role": user_role, "status": user_status},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return {"access_token": access_token, "token_type": "bearer", "role": user_role, "username": user.username}


# ==========================================
# REGISTRATION ENDPOINTS (With Approval Logic)
# ==========================================

@router.post("/register", response_model=schemas.UserOut, status_code=status.HTTP_201_CREATED)
def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    """Registers a new user with pending approval status for drivers/merchants."""
    db_user = db.query(models.User).filter(models.User.username == user.username).first()
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Username already registered"
        )
    
    role = getattr(user, "role", "customer") or "customer"
    
    # Enforce pending_approval status for drivers and merchants
    initial_status = "pending_approval" if role in ["driver", "merchant"] else "active"
    
    hashed_pwd = get_password_hash(user.password)
    new_user = models.User(
        username=user.username,
        email=getattr(user, "email", None),
        hashed_password=hashed_pwd,
        role=role,
        status=initial_status,
        is_active=True
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    logger.info(f"Registered new user {new_user.username} with role {role} and status {initial_status}")
    return new_user


# ==========================================
# DISTINCT ROLE PORTAL LOGIN ENDPOINTS
# ==========================================

@router.post("/login/customer", response_model=schemas.Token)
@limiter.limit("5/minute")
def login_customer(request: Request, payload: LoginRequest, db: Session = Depends(get_db)):
    """Customer Portal Login Endpoint"""
    return _process_portal_login(payload, "customer", db)

@router.post("/login/merchant", response_model=schemas.Token)
@limiter.limit("5/minute")
def login_merchant(request: Request, payload: LoginRequest, db: Session = Depends(get_db)):
    """Merchant Portal Login Endpoint"""
    return _process_portal_login(payload, "merchant", db)


@router.post("/login/driver", response_model=schemas.Token)
@limiter.limit("5/minute")
def login_driver(request: Request, payload: LoginRequest, db: Session = Depends(get_db)):
    """Driver Portal Login Endpoint"""
    return _process_portal_login(payload, "driver", db)


@router.post("/admin/login", response_model=schemas.Token)
@limiter.limit("5/minute")
def login_admin(request: Request, payload: LoginRequest, db: Session = Depends(get_db)):
    """Admin Audit & Remittance Portal Login Endpoint"""
    return _process_portal_login(payload, "admin", db)


# Generic OAuth2 Token Endpoint for Swagger UI Compatibility
@router.post("/token", response_model=schemas.Token)
@limiter.limit("5/minute")
def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Standard OAuth2 token endpoint for FastAPI docs."""
    payload = LoginRequest(username=form_data.username, password=form_data.password)
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    if not user:
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    
    target_role = "admin" if user.role in ["admin", "super_admin"] else user.role
    return _process_portal_login(payload, target_role, db)


# ==========================================
# UTILITY AUTH ENDPOINTS
# ==========================================

@router.post("/refresh", response_model=schemas.Token)
def refresh_token(current_user: models.User = Depends(get_current_user)):
    """Issues a fresh access token for an active session."""
    access_token = create_access_token(
        data={"sub": current_user.username, "role": current_user.role},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/change-password")
def change_password(payload: PasswordChangePayload, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Allows an authenticated user to securely change their password."""
    if not verify_password(payload.old_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect existing password")
    
    current_user.hashed_password = get_password_hash(payload.new_password)
    db.commit()
    logger.info(f"Password changed for user {current_user.username}")
    return {"success": True, "message": "Password updated successfully."}


@router.post("/logout")
def logout(token: str = Depends(oauth2_scheme), current_user: models.User = Depends(get_current_user)):
    """Logs out the user by blacklisting their active token."""
    blacklist_token(token, expiry_seconds=ACCESS_TOKEN_EXPIRE_MINUTES * 60)
    logger.info(f"User {current_user.username} logged out.")
    return {"success": True, "message": "Successfully logged out and token revoked."}


@router.get("/me", response_model=schemas.UserOut)
def get_me(current_user: models.User = Depends(get_current_user)):
    """Returns profile info for the currently authenticated user."""
    return current_user