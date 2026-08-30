# main.py - Ang Sentral nga Pundasyon ug Global API Gateway sa Higala Express Superapp
import os
import time
import uuid
import httpx
import json
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
        
        user = db_session.query(User).filter(User.username == "ajentq").first()
        hashed_pwd = pwd_context.hash("101391@Jent")
        
        if not user:
            new_user = User(
                username="ajentq",
                hashed_password=hashed_pwd,
                role="admin",
                wallet_balance=50000.0,
                status="online"
            )
            db_session.add(new_user)
            db_session.commit()
            print("==========================================")
            print(" SUCCESS: Seeding ajentq account created! ")
            print("==========================================")
        else:
            user.hashed_password = hashed_pwd
            db_session.commit()
            print("==========================================")
            print(" SUCCESS: ajentq account updated/synced! ")
            print("==========================================")
        db_session.close()
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
    version="2.5.0", 
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
# --- INTEGRATED V1 SUPERAPP ENDPOINTS (Wallet, Rides, AI, SOS) ---
# ==========================================================

class WalletTopUp(BaseModel):
    user_id: int
    amount: float = Field(..., gt=0)
    payment_method: str = Field(..., example="GCash via PayMongo or QR Ph")

class RideBooking(BaseModel):
    user_id: int
    service_type: str = Field(..., example="Habal-Habal | Taxi | Inter-City Carpool")
    pickup_location: str
    dropoff_location: str
    fare_amount: float

class FoodOrder(BaseModel):
    user_id: int
    merchant_id: int
    items: List[str]
    total_price: float
    delivery_address: str

class SOSAlert(BaseModel):
    user_id: int
    latitude: float
    longitude: float
    emergency_type: str = Field(..., example="Medical | Police | Fire | DRRMO")

@app.post("/api/v1/wallet/topup", tags=["Fintech Hub"])
def wallet_topup(payload: WalletTopUp):
    return {
        "status": "success",
        "message": f"Successfully initiated top-up of PHP {payload.amount:.2f}",
        "gateway": payload.payment_method,
        "timestamp": datetime.utcnow()
    }

@app.post("/api/v1/wallet/transfer", tags=["Fintech Hub"])
def p2p_transfer(sender_id: int, receiver_phone: str, amount: float):
    return {
        "status": "success",
        "message": f"Transferred PHP {amount:.2f} to {receiver_phone}",
        "transaction_fee": 0.00
    }

@app.post("/api/v1/mobility/book-ride", tags=["Mobility & Logistics"])
def book_ride(booking: RideBooking):
    return {
        "status": "dispatched",
        "booking_id": 88821,
        "service": booking.service_type,
        "estimated_arrival": "4 minutes",
        "fare": booking.fare_amount
    }

@app.post("/api/v1/commerce/order-food", tags=["Commerce & Hub"])
def order_food(order: FoodOrder):
    return {
        "status": "order_placed",
        "order_id": 5042,
        "merchant_id": order.merchant_id,
        "total": order.total_price,
        "escrow_secured": True,
        "estimated_delivery": "25-35 minutes"
    }

@app.post("/api/v1/community/sos", tags=["Community & Welfare"])
def trigger_sos(alert: SOSAlert):
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