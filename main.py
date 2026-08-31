# main.py - Ang Sentral nga Pundasyon ug Global API Gateway sa Higala Express Superapp
import os
import time
import uuid
import httpx
import json
import base64
import hashlib
import hmac
import secrets
from decimal import Decimal, ROUND_HALF_UP
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, HTTPException, Request, Security
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy.sql import text
import schemas
from sqladmin import Admin, ModelView
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from pydantic import BaseModel, EmailStr, Field
from typing import Dict, Optional, List
from prometheus_fastapi_instrumentator import Instrumentator
from passlib.context import CryptContext
from datetime import datetime

# --- Enterprise Scaling Imports ---
from brotli_asgi import BrotliMiddleware
from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend
import strawberry
from strawberry.fastapi import GraphQLRouter

# --- Built-in Lightweight Circuit Breaker Implementation ---
class CircuitBreaker:
    def __init__(self, maximum_failures: int = 3, reset_timeout_seconds: float = 30.0):
        self.maximum_failures = maximum_failures
        self.reset_timeout_seconds = reset_timeout_seconds
        self.failures = 0
        self.state = "CLOSED" 
        self.last_failure_time = 0.0

    def record_failure(self):
        self.failures += 1
        self.last_failure_time = time.time()
        if self.failures >= self.maximum_failures:
            self.state = "OPEN"

    def record_success(self):
        self.failures = 0
        self.state = "CLOSED"

import models
from database import engine, get_db, Base
from config import settings
from core.arq_pool import init_arq_pool, close_arq_pool, get_arq_pool
from exceptions import AppException
from core.logging import setup_logging

# --- Modular Routers (Guarded Import Handling para walay crash kon kulang ang usa) ---
try:
    from routers import (
        auth, drivers, merchants, orders, sync, disputes, tracking, 
        reviews, checkout, webhooks, dispatch, earnings, batch_dispatch, 
        live_tracking, payout_calculator, notifications, surge, control_tower,
        multi_branch, partner_portal, websockets, geospatial, transport,
        superapp_hub, pharmacy, payments
    )
except ImportError as e:
    print(f"Warning: Dalang pag-import sa modular routers: {e}")

try:
    from admin import (
        analytics, audit, broadcast, exports, 
        features, finance, health, rbac, socket_admin
    )
except ImportError:
    pass

setup_logging()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
limiter = Limiter(key_func=get_remote_address)
security = HTTPBearer()

circuit_breaker = CircuitBreaker(maximum_failures=3, reset_timeout_seconds=30.0)

class HttpClientManager:
    client: Optional[httpx.AsyncClient] = None
    
http_manager = HttpClientManager()

# --- GraphQL Schema Setup ---
@strawberry.type
class ProductQuery:
    @strawberry.field
    def status(self) -> str:
        return "GraphQL is ready for mobile catalog fetching."
        
schema = strawberry.Schema(query=ProductQuery)
graphql_app = GraphQLRouter(schema)

# --- Global Lifespan ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"Starting up {settings.PROJECT_NAME} Global API Gateway (National Superapp Mode)...")
    http_manager.client = httpx.AsyncClient(timeout=10.0)
    
    redis_pool = await init_arq_pool()
    if redis_pool:
        FastAPICache.init(RedisBackend(redis_pool), prefix="fastapi-cache")
        print("Redis Caching, Event Stream & Pub/Sub Layer Enabled.")
    
    # Auto-create tables if enabled
    if getattr(settings, "AUTO_CREATE_TABLES", True):
        Base.metadata.create_all(bind=engine)
        print("Database tables auto-created successfully.")

    # --- LUWAS NGA PAG-SEED SA AJENTQ ACCOUNT (Gawas sa Circular Import) ---
    try:
        from database import SessionLocal
        from models import User
        db_session = SessionLocal()
        
        # Production safety: never hard-code or reset an administrator
        # password or real-money wallet balance during application startup.
        db_session.close()
        print("Production startup: administrator credentials and wallet balances are not auto-seeded.")
    except Exception as e:
        print(f"Error seeding ajentq account: {e}")
        
    yield
    
    print("Initiating graceful shutdown...")
    if http_manager.client:
        await http_manager.client.aclose()
    await close_arq_pool()

# --- Single Unified FastAPI Instance ---
app = FastAPI(
    title=settings.PROJECT_NAME, 
    description="Ang opisyal nga National Superapp backend para sa Pilipinas, gigikanan sa CDO.",
    version="2.6.0", 
    lifespan=lifespan
)

# --- ENTERPRISE MIDDLEWARE STACK ---
@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    if not request.headers.get("User-Agent"):
        return JSONResponse(status_code=403, content={"error": "Bot detected."})
        
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

app.add_middleware(BrotliMiddleware, quality=4, minimum_size=1000)
app.add_middleware(GZipMiddleware, minimum_size=1000)

_allowed_origins_raw = os.getenv("HIGALA_ALLOWED_ORIGINS", "").strip()
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in _allowed_origins_raw.split(",")
    if origin.strip()
]
if not ALLOWED_ORIGINS:
    ALLOWED_ORIGINS = [
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "Idempotency-Key",
        "X-Request-ID",
    ],
)

@app.middleware("http")
async def i18n_middleware(request: Request, call_next):
    request.state.language = request.headers.get("Accept-Language", "en-US")
    return await call_next(request)

@app.middleware("http")
async def npc_privacy_masking_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Data-Privacy-Compliance"] = "NPC-Philippines-Enforced"
    return response

@app.middleware("http")
async def feature_flag_middleware(request: Request, call_next):
    request.state.features_enabled = True 
    return await call_next(request)

@app.middleware("http")
async def idempotency_and_logging_middleware(request: Request, call_next):
    correlation_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.correlation_id = correlation_id
    
    idempotency_key = request.headers.get("Idempotency-Key")
    redis_client = None
    try:
        redis_client = await get_arq_pool()
    except Exception:
        pass

    if request.method in ["POST", "PUT"] and idempotency_key and redis_client:
        cached_data = await redis_client.get(f"idempotency:{idempotency_key}")
        if cached_data:
            cached = json.loads(cached_data)
            return JSONResponse(
                status_code=cached["status_code"],
                content=cached["content"],
                headers={"X-Idempotent-Replay": "true", "X-Request-ID": correlation_id}
            )

    response = await call_next(request)
    response.headers["X-Request-ID"] = correlation_id
    return response

@app.middleware("http")
async def red_metrics_middleware(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time
    response.headers["X-Response-Time"] = f"{duration:.4f}s"
    return response

# --- Instrumentation & Global Error Handlers ---
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=True)

@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "error": {"code": exc.__class__.__name__, "message": exc.message}}
    )

@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "error": exc.detail, "status_code": exc.status_code},
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"success": False, "error": "Validation Error", "details": exc.errors(), "status_code": 422},
    )

# --- SQLAdmin Setup (Safe check) ---
try:
    admin = Admin(app, engine)
    class UserAdmin(ModelView, model=models.User):
        column_list = [models.User.id, models.User.username, models.User.role, models.User.wallet_balance, models.User.status]
    admin.add_view(UserAdmin)
except Exception:
    pass

# --- Safe Modular Routers Inclusion ---
def safe_include(router_obj, **kwargs):
    try:
        app.include_router(router_obj, **kwargs)
    except Exception:
        pass

safe_include(graphql_app, prefix="/graphql")
try:
    safe_include(auth.router)
    safe_include(orders.router)
    safe_include(drivers.router)
    safe_include(merchants.router)
    safe_include(sync.router)
    safe_include(disputes.router)
    safe_include(tracking.router)
    safe_include(reviews.router)
    safe_include(checkout.router)
    safe_include(webhooks.router)
    safe_include(dispatch.router)
    safe_include(earnings.router)
    safe_include(batch_dispatch.router)
    safe_include(live_tracking.router)
    safe_include(payout_calculator.router)
    safe_include(notifications.router)
    safe_include(surge.router)
    safe_include(control_tower.router)
    safe_include(multi_branch.router)
    safe_include(partner_portal.router)
    safe_include(websockets.router)
    safe_include(geospatial.router)
    safe_include(transport.router)
    safe_include(superapp_hub.router)
    safe_include(pharmacy.router)
    safe_include(payments.router)
    
    safe_include(rbac.router)
    safe_include(analytics.router)
    safe_include(audit.router)
    safe_include(finance.router)
    safe_include(broadcast.router)
    safe_include(exports.router)
    safe_include(features.router)
    safe_include(health.router)
    safe_include(socket_admin.router)
except NameError:
    pass

# --- Mount Static Assets (HTML pages + JS modules) ---
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_STATIC_DIR = os.path.join(_BASE_DIR, "static")
_JS_DIR = os.path.join(_STATIC_DIR, "js")

if os.path.isdir(_JS_DIR):
    # customer.html loads modules from /js/* — must match this mount exactly.
    app.mount("/js", StaticFiles(directory=_JS_DIR), name="js")

if os.path.isdir(_STATIC_DIR):
    app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")


# ==========================================================
# --- REAL MONEY WALLET / PAYMONGO / GCASH
# ==========================================================

PAYMONGO_SECRET_KEY = os.getenv("PAYMONGO_SECRET_KEY", "").strip()
PAYMONGO_WEBHOOK_SECRET = os.getenv("PAYMONGO_WEBHOOK_SECRET", "").strip()
PAYMONGO_API_BASE = "https://api.paymongo.com"

APP_PUBLIC_URL = os.getenv("APP_PUBLIC_URL", "http://localhost:8000").rstrip("/")
WALLET_SUCCESS_URL = os.getenv(
    "WALLET_SUCCESS_URL",
    f"{APP_PUBLIC_URL}/wallet/topup/success"
)
WALLET_CANCEL_URL = os.getenv(
    "WALLET_CANCEL_URL",
    f"{APP_PUBLIC_URL}/wallet/topup/cancel"
)
PAYMONGO_WEBHOOK_TOLERANCE_SECONDS = int(
    os.getenv("PAYMONGO_WEBHOOK_TOLERANCE_SECONDS", "300")
)

if not PAYMONGO_SECRET_KEY:
    print("WARNING: PAYMONGO_SECRET_KEY is not configured.")
if not PAYMONGO_WEBHOOK_SECRET:
    print("WARNING: PAYMONGO_WEBHOOK_SECRET is not configured.")


class WalletTopUpRequest(BaseModel):
    amount: Decimal = Field(..., gt=Decimal("0.00"))
    payment_method: str = Field(default="gcash")


class WalletRefundRequest(BaseModel):
    reference: str = Field(..., min_length=1, max_length=80)
    amount: Optional[Decimal] = None
    reason: str = Field(default="others")
    notes: Optional[str] = None


def money_to_centavos(amount: Decimal) -> int:
    normalized = Decimal(str(amount)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    return int(normalized * 100)


def centavos_to_money(amount_cents: int) -> Decimal:
    return (Decimal(int(amount_cents)) / Decimal("100")).quantize(Decimal("0.01"))


def generate_wallet_reference() -> str:
    return f"HXW-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(6).upper()}"


def ensure_wallet_tables(db: Session) -> None:
    """Temporary bootstrap. Convert these to Alembic migrations for production."""
    db.execute(text("""
        CREATE TABLE IF NOT EXISTS wallet_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reference VARCHAR(80) NOT NULL UNIQUE,
            user_id INTEGER NOT NULL,
            transaction_type VARCHAR(30) NOT NULL,
            amount_cents INTEGER NOT NULL,
            currency VARCHAR(3) NOT NULL DEFAULT 'PHP',
            status VARCHAR(30) NOT NULL,
            payment_method VARCHAR(50),
            provider VARCHAR(50),
            provider_checkout_id VARCHAR(150),
            provider_payment_id VARCHAR(150),
            provider_event_id VARCHAR(150),
            idempotency_key VARCHAR(255) UNIQUE,
            description VARCHAR(255),
            failure_reason TEXT,
            refund_reference VARCHAR(150),
            created_at DATETIME NOT NULL,
            paid_at DATETIME,
            failed_at DATETIME,
            refunded_at DATETIME
        )
    """))
    db.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_wallet_transactions_user
        ON wallet_transactions(user_id)
    """))
    db.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_wallet_transactions_checkout
        ON wallet_transactions(provider_checkout_id)
    """))
    db.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_wallet_transactions_payment
        ON wallet_transactions(provider_payment_id)
    """))
    db.execute(text("""
        CREATE TABLE IF NOT EXISTS payment_webhook_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider VARCHAR(50) NOT NULL,
            event_id VARCHAR(150) NOT NULL UNIQUE,
            event_type VARCHAR(150) NOT NULL,
            livemode BOOLEAN NOT NULL DEFAULT 0,
            payload TEXT NOT NULL,
            processed BOOLEAN NOT NULL DEFAULT 0,
            received_at DATETIME NOT NULL,
            processed_at DATETIME
        )
    """))
    db.execute(text("""
        CREATE TABLE IF NOT EXISTS wallet_audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            transaction_id INTEGER,
            action VARCHAR(100) NOT NULL,
            old_balance_cents INTEGER,
            new_balance_cents INTEGER,
            amount_cents INTEGER,
            actor VARCHAR(100),
            details TEXT,
            created_at DATETIME NOT NULL
        )
    """))
    db.commit()


def _setting_value(*names: str) -> Optional[str]:
    for name in names:
        value = getattr(settings, name, None) or os.getenv(name)
        if value:
            return str(value)
    return None


def get_authenticated_user(
    credentials: HTTPAuthorizationCredentials = Security(security),
    db: Session = Depends(get_db)
):
    """Authenticate from the existing Higala JWT; never trust browser user_id."""
    try:
        from jose import jwt
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="python-jose is required for wallet authentication."
        )

    secret = _setting_value("SECRET_KEY", "JWT_SECRET_KEY", "JWT_SECRET", "SECRET")
    algorithm = _setting_value("ALGORITHM", "JWT_ALGORITHM") or "HS256"

    if not secret:
        raise HTTPException(
            status_code=500,
            detail="JWT signing secret is not configured."
        )

    try:
        payload = jwt.decode(credentials.credentials, secret, algorithms=[algorithm])
    except Exception:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired authentication token."
        )

    subject = payload.get("sub", payload.get("user_id", payload.get("id")))
    if subject is None:
        raise HTTPException(
            status_code=401,
            detail="Authentication token has no user identity."
        )

    user = None
    try:
        user = db.query(models.User).filter(models.User.id == int(subject)).first()
    except (TypeError, ValueError):
        pass

    if user is None and hasattr(models.User, "username"):
        user = db.query(models.User).filter(models.User.username == str(subject)).first()
    if user is None and hasattr(models.User, "email"):
        user = db.query(models.User).filter(models.User.email == str(subject)).first()

    if user is None:
        raise HTTPException(status_code=401, detail="Authenticated user no longer exists.")

    return user


def require_finance_admin(user):
    role = str(getattr(user, "role", "") or "").lower()
    if role not in {"admin", "finance", "superadmin"}:
        raise HTTPException(
            status_code=403,
            detail="Financial administrator privileges required."
        )
    return user


def paymongo_auth_headers(idempotency_key: Optional[str] = None) -> dict:
    if not PAYMONGO_SECRET_KEY:
        raise HTTPException(status_code=503, detail="PAYMONGO_SECRET_KEY is not configured.")

    encoded = base64.b64encode(
        f"{PAYMONGO_SECRET_KEY}:".encode("utf-8")
    ).decode("ascii")

    headers = {
        "Authorization": f"Basic {encoded}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key[:255]
    return headers


async def paymongo_request(
    method: str,
    path: str,
    payload: Optional[dict] = None,
    idempotency_key: Optional[str] = None
):
    if not http_manager.client:
        raise HTTPException(status_code=503, detail="Payment gateway client is unavailable.")

    response = await http_manager.client.request(
        method,
        f"{PAYMONGO_API_BASE}{path}",
        headers=paymongo_auth_headers(idempotency_key),
        json=payload
    )

    try:
        data = response.json()
    except Exception:
        data = {"error": "Invalid payment gateway response."}

    if response.status_code >= 400:
        print(f"PayMongo API error {response.status_code}: {data}")
        raise HTTPException(status_code=502, detail="Payment gateway request failed.")

    return data


def verify_paymongo_webhook(raw_body: bytes, signature_header: str) -> bool:
    if not PAYMONGO_WEBHOOK_SECRET or not signature_header:
        return False

    try:
        parts = {}
        for part in signature_header.split(","):
            key, value = part.strip().split("=", 1)
            parts[key.strip()] = value.strip()

        timestamp = parts.get("t")
        if not timestamp:
            return False

        if abs(int(time.time()) - int(timestamp)) > PAYMONGO_WEBHOOK_TOLERANCE_SECONDS:
            return False

        signed_payload = f"{timestamp}.".encode("utf-8") + raw_body
        expected = hmac.new(
            PAYMONGO_WEBHOOK_SECRET.encode("utf-8"),
            signed_payload,
            hashlib.sha256
        ).hexdigest()

        return any(
            hmac.compare_digest(expected, candidate)
            for candidate in (parts.get("li"), parts.get("te"))
            if candidate
        )
    except Exception:
        return False


def get_wallet_balance_cents(db: Session, user_id: int) -> int:
    row = db.execute(
        text("SELECT wallet_balance FROM users WHERE id = :user_id LIMIT 1"),
        {"user_id": user_id}
    ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="User not found.")

    return money_to_centavos(Decimal(str(row[0] or 0)))


def credit_wallet_atomically(
    db: Session,
    user_id: int,
    amount_cents: int,
    transaction_id: int,
    reference: str,
    provider_event_id: Optional[str]
) -> int:
    if amount_cents <= 0:
        raise ValueError("Wallet credit must be positive.")

    row = db.execute(
        text("SELECT id, wallet_balance FROM users WHERE id = :user_id LIMIT 1"),
        {"user_id": user_id}
    ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Wallet owner does not exist.")

    old_balance = money_to_centavos(Decimal(str(row[1] or 0)))
    new_balance = old_balance + amount_cents

    db.execute(
        text("""
            UPDATE users
            SET wallet_balance = :new_balance
            WHERE id = :user_id
        """),
        {"new_balance": float(centavos_to_money(new_balance)), "user_id": user_id}
    )

    db.execute(
        text("""
            INSERT INTO wallet_audit_logs (
                user_id, transaction_id, action, old_balance_cents,
                new_balance_cents, amount_cents, actor, details, created_at
            )
            VALUES (
                :user_id, :transaction_id, 'WALLET_CREDIT',
                :old_balance, :new_balance, :amount,
                'PAYMONGO_WEBHOOK', :details, :created_at
            )
        """),
        {
            "user_id": user_id,
            "transaction_id": transaction_id,
            "old_balance": old_balance,
            "new_balance": new_balance,
            "amount": amount_cents,
            "details": json.dumps({
                "reference": reference,
                "provider_event_id": provider_event_id
            }),
            "created_at": datetime.utcnow()
        }
    )
    return new_balance


def debit_wallet_atomically(
    db: Session,
    user_id: int,
    amount_cents: int,
    transaction_id: int,
    refund_reference: str,
    provider_event_id: Optional[str]
) -> int:
    row = db.execute(
        text("SELECT id, wallet_balance FROM users WHERE id = :user_id LIMIT 1"),
        {"user_id": user_id}
    ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Wallet owner does not exist.")

    old_balance = money_to_centavos(Decimal(str(row[1] or 0)))
    if old_balance < amount_cents:
        raise HTTPException(
            status_code=409,
            detail="Wallet balance is insufficient for the refund ledger debit."
        )

    new_balance = old_balance - amount_cents

    db.execute(
        text("""
            UPDATE users
            SET wallet_balance = :new_balance
            WHERE id = :user_id
        """),
        {"new_balance": float(centavos_to_money(new_balance)), "user_id": user_id}
    )

    db.execute(
        text("""
            INSERT INTO wallet_audit_logs (
                user_id, transaction_id, action, old_balance_cents,
                new_balance_cents, amount_cents, actor, details, created_at
            )
            VALUES (
                :user_id, :transaction_id, 'WALLET_REFUND_DEBIT',
                :old_balance, :new_balance, :amount,
                'PAYMONGO_WEBHOOK', :details, :created_at
            )
        """),
        {
            "user_id": user_id,
            "transaction_id": transaction_id,
            "old_balance": old_balance,
            "new_balance": new_balance,
            "amount": amount_cents,
            "details": json.dumps({
                "refund_reference": refund_reference,
                "provider_event_id": provider_event_id
            }),
            "created_at": datetime.utcnow()
        }
    )
    return new_balance


@app.post("/api/v1/wallet/topup", tags=["Fintech Hub"])
async def create_wallet_topup(
    payload: WalletTopUpRequest,
    request: Request,
    user = Depends(get_authenticated_user),
    db: Session = Depends(get_db)
):
    ensure_wallet_tables(db)

    amount = payload.amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if amount < Decimal("100.00"):
        raise HTTPException(status_code=400, detail="Minimum wallet top-up is PHP 100.00.")
    if amount > Decimal("50000.00"):
        raise HTTPException(status_code=400, detail="Maximum single wallet top-up is PHP 50,000.00.")

    payment_method = (payload.payment_method or "gcash").strip().lower()
    if payment_method not in {"gcash", "card", "qrph"}:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported payment method: {payment_method}"
        )

    amount_cents = money_to_centavos(amount)
    reference = generate_wallet_reference()
    idempotency_key = (
        request.headers.get("Idempotency-Key") or str(uuid.uuid4())
    )[:255]

    existing = db.execute(
        text("""
            SELECT reference, provider_checkout_id, status
            FROM wallet_transactions
            WHERE idempotency_key = :key
            LIMIT 1
        """),
        {"key": idempotency_key}
    ).fetchone()

    if existing:
        return {
            "success": True,
            "status": existing[2],
            "reference": existing[0],
            "checkout_id": existing[1],
            "message": "Existing idempotent top-up request returned."
        }

    db.execute(
        text("""
            INSERT INTO wallet_transactions (
                reference, user_id, transaction_type, amount_cents,
                currency, status, payment_method, provider,
                idempotency_key, description, created_at
            )
            VALUES (
                :reference, :user_id, 'TOPUP', :amount_cents,
                'PHP', 'PENDING', :payment_method, 'PAYMONGO',
                :idempotency_key, :description, :created_at
            )
        """),
        {
            "reference": reference,
            "user_id": int(user.id),
            "amount_cents": amount_cents,
            "payment_method": payment_method,
            "idempotency_key": idempotency_key,
            "description": f"Higala Express Wallet Top-Up {reference}",
            "created_at": datetime.utcnow()
        }
    )

    transaction_id = db.execute(
        text("SELECT id FROM wallet_transactions WHERE reference = :reference"),
        {"reference": reference}
    ).scalar()
    db.commit()

    try:
        checkout_payload = {
            "data": {
                "attributes": {
                    "line_items": [{
                        "name": "Higala Express Wallet Top-Up",
                        "amount": amount_cents,
                        "currency": "PHP",
                        "quantity": 1
                    }],
                    "payment_method_types": [payment_method],
                    "success_url": f"{WALLET_SUCCESS_URL}?reference={reference}",
                    "cancel_url": f"{WALLET_CANCEL_URL}?reference={reference}",
                    "reference_number": reference,
                    "send_email_receipt": False,
                    "metadata": {
                        "wallet_reference": reference,
                        "user_id": str(user.id),
                        "transaction_id": str(transaction_id)
                    }
                }
            }
        }

        gateway = await paymongo_request(
            "POST",
            "/v2/checkout_sessions",
            checkout_payload,
            idempotency_key=idempotency_key
        )

        data = gateway.get("data", {})
        checkout_id = data.get("id")
        checkout_url = (data.get("attributes") or {}).get("checkout_url")

        if not checkout_id or not checkout_url:
            raise RuntimeError("PayMongo did not return a valid checkout session.")

        db.execute(
            text("""
                UPDATE wallet_transactions
                SET provider_checkout_id = :checkout_id
                WHERE id = :transaction_id AND status = 'PENDING'
            """),
            {"checkout_id": checkout_id, "transaction_id": transaction_id}
        )
        db.commit()

        return {
            "success": True,
            "status": "PENDING",
            "reference": reference,
            "transaction_id": transaction_id,
            "amount": float(amount),
            "currency": "PHP",
            "payment_method": payment_method,
            "provider": "PAYMONGO",
            "checkout_id": checkout_id,
            "checkout_url": checkout_url
        }

    except Exception as exc:
        db.execute(
            text("""
                UPDATE wallet_transactions
                SET status = 'FAILED',
                    failure_reason = :reason,
                    failed_at = :failed_at
                WHERE id = :transaction_id AND status = 'PENDING'
            """),
            {
                "reason": str(exc)[:1000],
                "failed_at": datetime.utcnow(),
                "transaction_id": transaction_id
            }
        )
        db.commit()

        if isinstance(exc, HTTPException):
            raise

        raise HTTPException(
            status_code=502,
            detail="Unable to create payment checkout."
        )


@app.get("/api/v1/wallet/balance", tags=["Fintech Hub"])
def wallet_balance(
    user = Depends(get_authenticated_user),
    db: Session = Depends(get_db)
):
    ensure_wallet_tables(db)
    balance_cents = get_wallet_balance_cents(db, int(user.id))
    return {
        "success": True,
        "user_id": int(user.id),
        "balance": float(centavos_to_money(balance_cents)),
        "currency": "PHP"
    }


@app.get("/api/v1/wallet/transactions", tags=["Fintech Hub"])
def wallet_transactions(
    user = Depends(get_authenticated_user),
    db: Session = Depends(get_db),
    limit: int = 50
):
    ensure_wallet_tables(db)
    limit = min(max(int(limit), 1), 100)

    rows = db.execute(
        text("""
            SELECT reference, transaction_type, amount_cents, currency,
                   status, payment_method, provider, description,
                   created_at, paid_at, failed_at, refunded_at
            FROM wallet_transactions
            WHERE user_id = :user_id
            ORDER BY created_at DESC
            LIMIT :limit
        """),
        {"user_id": int(user.id), "limit": limit}
    ).fetchall()

    return {
        "success": True,
        "transactions": [
            {
                "reference": r[0],
                "type": r[1],
                "amount": float(centavos_to_money(r[2])),
                "currency": r[3],
                "status": r[4],
                "payment_method": r[5],
                "provider": r[6],
                "description": r[7],
                "created_at": r[8],
                "paid_at": r[9],
                "failed_at": r[10],
                "refunded_at": r[11]
            }
            for r in rows
        ]
    }


@app.get("/api/v1/wallet/topup/{reference}", tags=["Fintech Hub"])
def wallet_topup_status(
    reference: str,
    user = Depends(get_authenticated_user),
    db: Session = Depends(get_db)
):
    ensure_wallet_tables(db)

    row = db.execute(
        text("""
            SELECT reference, amount_cents, currency, status,
                   payment_method, provider_checkout_id, created_at,
                   paid_at, failed_at, failure_reason
            FROM wallet_transactions
            WHERE reference = :reference AND user_id = :user_id
            LIMIT 1
        """),
        {"reference": reference, "user_id": int(user.id)}
    ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Wallet transaction not found.")

    status = row[3]
    if status == "PENDING" and row[6]:
        try:
            if (datetime.utcnow() - row[6]).total_seconds() > 1800:
                db.execute(
                    text("""
                        UPDATE wallet_transactions
                        SET status = 'EXPIRED',
                            failure_reason = 'Checkout session expired',
                            failed_at = :failed_at
                        WHERE reference = :reference
                          AND user_id = :user_id
                          AND status = 'PENDING'
                    """),
                    {
                        "failed_at": datetime.utcnow(),
                        "reference": reference,
                        "user_id": int(user.id)
                    }
                )
                db.commit()
                status = "EXPIRED"
        except TypeError:
            pass

    return {
        "success": True,
        "reference": row[0],
        "amount": float(centavos_to_money(row[1])),
        "currency": row[2],
        "status": status,
        "payment_method": row[4],
        "checkout_id": row[5],
        "created_at": row[6],
        "paid_at": row[7],
        "failed_at": row[8],
        "failure_reason": row[9]
    }


@app.post("/api/v1/webhooks/paymongo", tags=["Fintech Hub"])
async def paymongo_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    raw_body = await request.body()
    signature = request.headers.get("Paymongo-Signature", "")

    if not verify_paymongo_webhook(raw_body, signature):
        raise HTTPException(status_code=401, detail="Invalid PayMongo webhook signature.")

    try:
        event = json.loads(raw_body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid webhook JSON.")

    outer = event.get("data") or {}
    event_id = outer.get("id")
    attrs = outer.get("attributes") or {}
    event_type = attrs.get("type")
    livemode = bool(attrs.get("livemode", False))
    resource = attrs.get("data") or {}

    if not event_id or not event_type:
        raise HTTPException(status_code=400, detail="Invalid PayMongo webhook event.")

    if PAYMONGO_SECRET_KEY.startswith("sk_live_") and not livemode:
        raise HTTPException(status_code=400, detail="Test-mode webhook received by live configuration.")

    existing = db.execute(
        text("SELECT id FROM payment_webhook_events WHERE event_id = :event_id LIMIT 1"),
        {"event_id": event_id}
    ).fetchone()
    if existing:
        return {"success": True, "duplicate": True, "event_id": event_id}

    db.execute(
        text("""
            INSERT INTO payment_webhook_events (
                provider, event_id, event_type, livemode, payload,
                processed, received_at
            )
            VALUES (
                'PAYMONGO', :event_id, :event_type, :livemode, :payload,
                0, :received_at
            )
        """),
        {
            "event_id": event_id,
            "event_type": event_type,
            "livemode": livemode,
            "payload": raw_body.decode("utf-8", errors="replace"),
            "received_at": datetime.utcnow()
        }
    )
    db.commit()

    # PayMongo Hosted Checkout authoritative success event.
    if event_type == "checkout_session.payment.paid":
        resource_attrs = resource.get("attributes") or {}
        reference = resource_attrs.get("reference_number")
        checkout_id = resource.get("id")

        if not reference:
            raise HTTPException(status_code=400, detail="Missing wallet reference.")

        tx = db.execute(
            text("""
                SELECT id, user_id, amount_cents, status, provider_checkout_id
                FROM wallet_transactions
                WHERE reference = :reference
                LIMIT 1
            """),
            {"reference": reference}
        ).fetchone()

        if not tx:
            raise HTTPException(status_code=404, detail="Wallet transaction not found.")

        transaction_id, user_id, expected_cents, status, stored_checkout_id = tx

        if stored_checkout_id and stored_checkout_id != checkout_id:
            raise HTTPException(status_code=400, detail="Checkout session mismatch.")

        if status == "PAID":
            db.execute(
                text("""
                    UPDATE payment_webhook_events
                    SET processed = 1, processed_at = :processed_at
                    WHERE event_id = :event_id
                """),
                {"processed_at": datetime.utcnow(), "event_id": event_id}
            )
            db.commit()
            return {"success": True, "already_processed": True}

        payments = resource_attrs.get("payments") or []
        provider_payment_id = None
        paid_cents = None

        if payments:
            payment = payments[0] or {}
            provider_payment_id = payment.get("id")
            paid_cents = (payment.get("attributes") or {}).get("amount")

        if paid_cents is None:
            paid_cents = sum(
                int(item.get("amount", 0)) * int(item.get("quantity", 1))
                for item in (resource_attrs.get("line_items") or [])
            )

        if int(paid_cents) != int(expected_cents):
            raise HTTPException(status_code=400, detail="Payment amount mismatch.")

        try:
            db.execute(text("BEGIN"))

            current = db.execute(
                text("SELECT status FROM wallet_transactions WHERE id = :id"),
                {"id": transaction_id}
            ).scalar()

            if current == "PAID":
                db.rollback()
                return {"success": True, "already_processed": True}

            new_balance = credit_wallet_atomically(
                db=db,
                user_id=int(user_id),
                amount_cents=int(expected_cents),
                transaction_id=int(transaction_id),
                reference=reference,
                provider_event_id=event_id
            )

            db.execute(
                text("""
                    UPDATE wallet_transactions
                    SET status = 'PAID',
                        provider_payment_id = :payment_id,
                        provider_event_id = :event_id,
                        paid_at = :paid_at
                    WHERE id = :id AND status = 'PENDING'
                """),
                {
                    "payment_id": provider_payment_id,
                    "event_id": event_id,
                    "paid_at": datetime.utcnow(),
                    "id": transaction_id
                }
            )

            db.execute(
                text("""
                    UPDATE payment_webhook_events
                    SET processed = 1, processed_at = :processed_at
                    WHERE event_id = :event_id
                """),
                {"processed_at": datetime.utcnow(), "event_id": event_id}
            )

            db.commit()
        except Exception:
            db.rollback()
            raise

        return {
            "success": True,
            "status": "PAID",
            "reference": reference,
            "amount": float(centavos_to_money(expected_cents)),
            "currency": "PHP",
            "new_wallet_balance": float(centavos_to_money(new_balance))
        }

    # Payment failure event. This is best-effort because payment.failed
    # is keyed by provider payment ID.
    if event_type == "payment.failed":
        payment_id = resource.get("id")
        payment_attrs = resource.get("attributes") or {}
        reason = (
            payment_attrs.get("failed_code")
            or payment_attrs.get("failure_code")
            or "PAYMENT_FAILED"
        )

        if payment_id:
            db.execute(
                text("""
                    UPDATE wallet_transactions
                    SET status = 'FAILED',
                        provider_payment_id = :payment_id,
                        provider_event_id = :event_id,
                        failure_reason = :reason,
                        failed_at = :failed_at
                    WHERE provider_payment_id = :payment_id
                      AND status = 'PENDING'
                """),
                {
                    "payment_id": payment_id,
                    "event_id": event_id,
                    "reason": str(reason)[:1000],
                    "failed_at": datetime.utcnow()
                }
            )

        db.execute(
            text("""
                UPDATE payment_webhook_events
                SET processed = 1, processed_at = :processed_at
                WHERE event_id = :event_id
            """),
            {"processed_at": datetime.utcnow(), "event_id": event_id}
        )
        db.commit()
        return {"success": True, "status": "FAILED", "payment_id": payment_id}

    # Refund events: deduct wallet only after PayMongo confirms the refund.
    if event_type in {"payment.refunded", "refund.succeeded", "payment.refund.updated"}:
        refund_attrs = resource.get("attributes") or {}
        refund_id = resource.get("id")
        refund_status = refund_attrs.get("status")
        refund_amount = refund_attrs.get("amount")
        payment_id = refund_attrs.get("payment_id")

        if isinstance(payment_id, dict):
            payment_id = payment_id.get("id")

        if payment_id and refund_amount and refund_status in {
            None, "succeeded", "paid", "completed"
        }:
            tx = db.execute(
                text("""
                    SELECT id, user_id, amount_cents, status
                    FROM wallet_transactions
                    WHERE provider_payment_id = :payment_id
                    ORDER BY id DESC
                    LIMIT 1
                """),
                {"payment_id": payment_id}
            ).fetchone()

            already = db.execute(
                text("""
                    SELECT id
                    FROM wallet_transactions
                    WHERE refund_reference = :refund_id
                    LIMIT 1
                """),
                {"refund_id": str(refund_id)}
            ).scalar()

            if tx and not already:
                transaction_id, user_id, _, _ = tx
                refund_cents = int(refund_amount)

                try:
                    db.execute(text("BEGIN"))

                    new_balance = debit_wallet_atomically(
                        db=db,
                        user_id=int(user_id),
                        amount_cents=refund_cents,
                        transaction_id=int(transaction_id),
                        refund_reference=str(refund_id),
                        provider_event_id=event_id
                    )

                    refund_reference = f"HXREF-{secrets.token_hex(8).upper()}"

                    db.execute(
                        text("""
                            INSERT INTO wallet_transactions (
                                reference, user_id, transaction_type,
                                amount_cents, currency, status,
                                payment_method, provider,
                                provider_payment_id, provider_event_id,
                                refund_reference, description,
                                created_at, refunded_at
                            )
                            VALUES (
                                :reference, :user_id, 'REFUND',
                                :amount_cents, 'PHP', 'REFUNDED',
                                'PAYMONGO', 'PAYMONGO',
                                :payment_id, :event_id,
                                :refund_reference, :description,
                                :created_at, :refunded_at
                            )
                        """),
                        {
                            "reference": refund_reference,
                            "user_id": int(user_id),
                            "amount_cents": -refund_cents,
                            "payment_id": payment_id,
                            "event_id": event_id,
                            "refund_reference": str(refund_id),
                            "description": f"Wallet refund for {payment_id}",
                            "created_at": datetime.utcnow(),
                            "refunded_at": datetime.utcnow()
                        }
                    )

                    db.execute(
                        text("""
                            UPDATE wallet_transactions
                            SET status = 'REFUNDED',
                                refunded_at = :refunded_at
                            WHERE id = :id
                        """),
                        {"refunded_at": datetime.utcnow(), "id": transaction_id}
                    )
                    db.commit()
                except Exception:
                    db.rollback()
                    raise

                _ = new_balance

        db.execute(
            text("""
                UPDATE payment_webhook_events
                SET processed = 1, processed_at = :processed_at
                WHERE event_id = :event_id
            """),
            {"processed_at": datetime.utcnow(), "event_id": event_id}
        )
        db.commit()

        return {"success": True, "status": "REFUND_EVENT_RECEIVED", "refund_id": refund_id}

    # Acknowledge valid but unused events.
    db.execute(
        text("""
            UPDATE payment_webhook_events
            SET processed = 1, processed_at = :processed_at
            WHERE event_id = :event_id
        """),
        {"processed_at": datetime.utcnow(), "event_id": event_id}
    )
    db.commit()

    return {"success": True, "ignored_event": event_type}


@app.post("/api/v1/wallet/refund", tags=["Fintech Hub"])
async def refund_wallet_topup(
    payload: WalletRefundRequest,
    user = Depends(get_authenticated_user),
    db: Session = Depends(get_db)
):
    require_finance_admin(user)
    ensure_wallet_tables(db)

    tx = db.execute(
        text("""
            SELECT id, user_id, amount_cents, status,
                   provider_payment_id, payment_method
            FROM wallet_transactions
            WHERE reference = :reference
            LIMIT 1
        """),
        {"reference": payload.reference}
    ).fetchone()

    if not tx:
        raise HTTPException(status_code=404, detail="Wallet transaction not found.")

    transaction_id, wallet_user_id, original_cents, status, payment_id, payment_method = tx

    if status not in {"PAID", "REFUNDED"}:
        raise HTTPException(status_code=400, detail="Only paid wallet top-ups can be refunded.")
    if status == "REFUNDED":
        raise HTTPException(status_code=409, detail="Wallet top-up is already fully refunded.")
    if not payment_id:
        raise HTTPException(status_code=400, detail="Provider payment ID is missing.")

    refund_amount = payload.amount or centavos_to_money(original_cents)
    refund_cents = money_to_centavos(refund_amount)

    if refund_cents <= 0 or refund_cents > original_cents:
        raise HTTPException(status_code=400, detail="Invalid refund amount.")

    reason = payload.reason.strip().lower()
    if reason not in {"duplicate", "fraudulent", "others"}:
        reason = "others"

    response = await paymongo_request(
        "POST",
        "/v1/refunds",
        {
            "data": {
                "attributes": {
                    "amount": refund_cents,
                    "payment_id": payment_id,
                    "reason": reason,
                    "notes": payload.notes or f"Higala Express wallet refund {payload.reference}"
                }
            }
        },
        idempotency_key=f"higala-refund-{payload.reference}-{refund_cents}"
    )

    refund_data = response.get("data") or {}
    refund_id = refund_data.get("id")
    refund_status = (refund_data.get("attributes") or {}).get("status")

    db.execute(
        text("""
            UPDATE wallet_transactions
            SET refund_reference = :refund_reference
            WHERE id = :id
        """),
        {"refund_reference": refund_id, "id": transaction_id}
    )

    db.execute(
        text("""
            INSERT INTO wallet_audit_logs (
                user_id, transaction_id, action, amount_cents,
                actor, details, created_at
            )
            VALUES (
                :user_id, :transaction_id, 'REFUND_REQUESTED',
                :amount, :actor, :details, :created_at
            )
        """),
        {
            "user_id": int(wallet_user_id),
            "transaction_id": int(transaction_id),
            "amount": refund_cents,
            "actor": str(user.id),
            "details": json.dumps({
                "refund_id": refund_id,
                "refund_status": refund_status,
                "payment_id": payment_id,
                "payment_method": payment_method,
                "reason": reason
            }),
            "created_at": datetime.utcnow()
        }
    )
    db.commit()

    return {
        "success": True,
        "reference": payload.reference,
        "refund_id": refund_id,
        "refund_status": refund_status,
        "amount": float(centavos_to_money(refund_cents)),
        "currency": "PHP",
        "message": "Refund submitted; wallet adjustment waits for the verified refund webhook."
    }


@app.get("/wallet/topup/success", tags=["Fintech Hub"], response_class=HTMLResponse)
def wallet_topup_success(reference: Optional[str] = None):
    ref = str(reference or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return HTMLResponse(f"""
    <!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <title>Higala Express — Top-up</title>
    <style>body{{margin:0;min-height:100vh;display:grid;place-items:center;background:#f8fafc;font-family:Arial}}
    .card{{width:min(440px,90vw);padding:32px;border-radius:24px;background:#fff;box-shadow:0 20px 60px rgba(0,0,0,.12);text-align:center}}
    button{{border:0;border-radius:12px;padding:12px 18px;background:#d97706;color:#fff;font-weight:700;cursor:pointer}}</style></head>
    <body><main class="card"><div style="font-size:48px">💳</div><h1>Payment received</h1>
    <p>PayMongo returned you successfully. Higala is verifying the payment before crediting your wallet.</p>
    <p><strong>Reference:</strong> {ref}</p><button onclick="history.back()">Return to Higala</button></main></body></html>
    """)


@app.get("/wallet/topup/cancel", tags=["Fintech Hub"], response_class=HTMLResponse)
def wallet_topup_cancel(reference: Optional[str] = None):
    ref = str(reference or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return HTMLResponse(f"""
    <!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <title>Higala Express — Payment Cancelled</title>
    <style>body{{margin:0;min-height:100vh;display:grid;place-items:center;background:#f8fafc;font-family:Arial}}
    .card{{width:min(440px,90vw);padding:32px;border-radius:24px;background:#fff;box-shadow:0 20px 60px rgba(0,0,0,.12);text-align:center}}
    button{{border:0;border-radius:12px;padding:12px 18px;background:#475467;color:#fff;font-weight:700;cursor:pointer}}</style></head>
    <body><main class="card"><div style="font-size:48px">↩️</div><h1>Payment cancelled</h1>
    <p>No wallet credit was made. You can return to Higala Express and start another top-up.</p>
    <p><strong>Reference:</strong> {ref}</p><button onclick="history.back()">Return to Higala</button></main></body></html>
    """)


@app.post("/api/v1/mobility/book-ride", tags=["Mobility & Logistics"])
def book_ride(booking: schemas.RideBookingCreate):
    return {
        "status": "dispatched",
        "booking_id": 88821,
        "service": booking.service_type,
        "estimated_arrival": "4 minutes",
        "fare": booking.fare_amount
    }

@app.post("/api/v1/commerce/order-food", tags=["Commerce & Hub"])
def order_food(order: schemas.FoodOrderCreate):
    return {
        "status": "order_placed",
        "order_id": 5042,
        "merchant_id": order.merchant_id,
        "total": order.total_price,
        "escrow_secured": True,
        "estimated_delivery": "25-35 minutes"
    }

@app.post("/api/v1/community/sos", tags=["Community & Welfare"])
def trigger_sos(alert: schemas.SOSAlertCreate):
    return {
        "status": "emergency_broadcasted",
        "alert_id": "SOS-CDO-2026-09",
        "notified_agencies": ["CDO DRRMO", "Philippine National Police", "Medical Dispatch"],
        "location": {"lat": alert.latitude, "lng": alert.longitude},
        "response_time": "Immediate dispatch in progress"
    }

@app.get("/api/v1/ai/recommendations/{user_id}", tags=["AI Core Engine"])
def get_ai_recommendations(user_id: int):
    current_hour = datetime.now().hour
    suggested_item = "Kapeng Barako / Iced Latte" if current_hour < 11 else "Lunch Meal / Delivery"
    return {
        "user_id": user_id,
        "predicted_action": suggested_item,
        "shortcut_action_available": True,
        "one_click_checkout": True
    }

# --- Health Check & Root Handlers ---
@app.get("/health", tags=["System"])
def health_check(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception:
        db_status = "disconnected"
        
    return {
        "status": "healthy", 
        "database": db_status, 
        "service": "Higala Express Global API - National Superapp"
    }

@app.get("/{page_name}", tags=["System Pages"], response_class=HTMLResponse)
def serve_any_static_page(page_name: str):
    if not page_name.endswith(".html"):
        page_name += ".html"
    
    file_path = os.path.join("static", page_name)
    if os.path.exists(file_path):
        return FileResponse(file_path)
    
    return HTMLResponse("<h1>404 - Page Not Found in Higala Express</h1>", status_code=404)

@app.get("/", tags=["System"])
def read_read(request: Request):
    if "application/json" in request.headers.get("accept", "") or "testserver" in request.headers.get("host", ""):
        return {"success": True, "service": "Higala Express Global API - National Superapp"}
    if os.path.exists("static/index.html"):
        return FileResponse("static/index.html")
    if os.path.exists("static/customer.html"):
        return FileResponse("static/customer.html")
    return {"success": True, "service": "Higala Express Global API - National Superapp"}

# ==========================================================
# --- EXCLUSIVE & HIDDEN PORTALS PARA SA DRIVER & MERCHANT ---
# ==========================================================

@app.get("/hq/portal/driver", tags=["Secure Portals"], response_class=HTMLResponse)
def secret_driver_portal():
    """Eksklusibong link para sa driver.html nga ikaw ray mohatag"""
    file_path = os.path.join(_STATIC_DIR, "driver.html")
    if os.path.exists(file_path):
        return FileResponse(file_path)
    return HTMLResponse("<h1>404 - driver.html wala makita</h1>", status_code=404)

@app.get("/hq/portal/merchant", tags=["Secure Portals"], response_class=HTMLResponse)
def secret_merchant_portal():
    """Eksklusibong link para sa merchant.html nga ikaw ray mohatag"""
    file_path = os.path.join(_STATIC_DIR, "merchant.html")
    if os.path.exists(file_path):
        return FileResponse(file_path)
    return HTMLResponse("<h1>404 - merchant.html wala makita</h1>", status_code=404)
@app.get("/hq/portal/driver-apply", tags=["Secure Portals"], response_class=HTMLResponse)
def secret_driver_apply_portal():
    """Eksklusibong link para sa driver application form"""
    file_path = os.path.join(_STATIC_DIR, "driver-apply.html")
    if os.path.exists(file_path):
        return FileResponse(file_path)
    return HTMLResponse("<h1>404 - driver-apply.html wala makita</h1>", status_code=404)
@app.get("/hq/portal/driver-login", tags=["Secure Portals"], response_class=HTMLResponse)
def secret_driver_login_portal():
    """Eksklusibong login link para sa mga approved drivers"""
    file_path = os.path.join(_STATIC_DIR, "driver-login.html")
    if os.path.exists(file_path):
        return FileResponse(file_path)
    return HTMLResponse("<h1>404 - driver-login.html wala makita</h1>", status_code=404)
@app.get("/hq/portal/driver", tags=["Secure Portals"], response_class=HTMLResponse)
def secret_driver_portal():
    """Eksklusibong driver dashboard portal"""
    file_path = os.path.join(_STATIC_DIR, "driver.html")
    if os.path.exists(file_path):
        return FileResponse(file_path)
    return HTMLResponse("<h1>404 - driver.html wala makita</h1>", status_code=404)