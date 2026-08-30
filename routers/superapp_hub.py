from fastapi import APIRouter, Depends, HTTPException, status, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from typing import List, Optional
from core.security import role_required  # Assumes security checks are handled via dependency injection
from websocket_manager import manager    # Uses your updated ConnectionManager

# Initialize the unified Super App router
router = APIRouter(prefix="/api/v1", tags=["Super App Unified Hub"])

# ==========================================
# 1. SCHEMAS (Data Validation & Models)
# ==========================================

class RideBookingRequest(BaseModel):
    pickup_location: str
    dropoff_location: str
    passenger_id: int

class ParcelRequest(BaseModel):
    sender_name: str
    recipient_name: str
    dropoff_address: str
    item_description: str

class MerchantOrderUpdate(BaseModel):
    order_id: str
    status: str  # e.g., "preparing", "ready", "dispatched"
    prep_time_minutes: int

class ProductItemCreate(BaseModel):
    name: str
    price: float
    stock: int
    category: str
    image_url: Optional[str] = None

class ProductItemUpdate(BaseModel):
    name: Optional[str] = None
    price: Optional[float] = None
    stock: Optional[int] = None
    status: Optional[str] = None  # "Active" or "Offline"
    category: Optional[str] = None
    image_url: Optional[str] = None

class UserRoleUpdate(BaseModel):
    user_id: int
    new_role: str  # e.g., "super_admin", "city_operations", "driver", "customer"


# ==========================================
# 2. CUSTOMER SUPER-APP MODULE
# ==========================================

@router.post("/customer/rides/book", status_code=status.HTTP_201_CREATED)
async def book_ride(payload: RideBookingRequest):
    """
    Handles passenger ride-hailing requests and dispatches to the transport router network.
    """
    return {
        "status": "success",
        "message": "Ride request broadcasted to nearby drivers.",
        "data": {
            "pickup": payload.pickup_location,
            "dropoff": payload.dropoff_location,
            "assigned_driver": "Alex P.",  # Simulated real-time driver match
            "eta_minutes": 4
        }
    }

@router.post("/customer/parcels/send", status_code=status.HTTP_201_CREATED)
async def send_parcel(payload: ParcelRequest):
    """
    Manages small-scale item transport and parcel handling.
    """
    return {
        "status": "success",
        "message": "Parcel delivery order created successfully.",
        "tracking_code": "PKG-8849-CDO"
    }


# ==========================================
# 3. MERCHANT PORTAL MODULE (Inventory & Controls)
# ==========================================

@router.get("/merchant/{merchant_id}/dashboard")
async def get_merchant_dashboard(
    merchant_id: str, 
    current_user: dict = Depends(role_required(["merchant", "super_admin"]))
):
    """
    Fetches real-time metrics, today's sales, and active order queues for store operators.
    Secured by RBAC: Requires 'merchant' or 'super_admin' roles.
    """
    return {
        "merchant_id": merchant_id,
        "store_name": "CDO Central Branch",
        "todays_sales_php": 3450.00,
        "pending_orders_count": 1,
        "active_order_queue": [
            {
                "order_id": "8842",
                "customer_name": "Juan dela Cruz",
                "items": [
                    {"name": "Premium Sinandomeng Rice (50kg)", "qty": 1, "price": 2250.00, "favorite": True},
                    {"name": "Coca-Cola 1.5L", "qty": 2, "price": 70.00}
                ],
                "total_amount": 2390.00,
                "preference_tag": "Please check sack integrity for rice orders thoroughly before dispatch.",
                "address": "Purok 4, Carmen, CDO (Near Barangay Hall)",
                "state": "pending_acceptance"
            }
        ]
    }

@router.get("/merchant/{merchant_id}/products")
async def get_merchant_products(
    merchant_id: str,
    current_user: dict = Depends(role_required(["merchant", "super_admin"]))
):
    """
    Fetches all inventory product items and categories for the merchant catalog.
    """
    return {
        "status": "success",
        "products": [
            {
                "id": 1,
                "name": "Premium Sinandomeng Rice (50kg)",
                "category": "Top Seller",
                "price": 2250.00,
                "stock": 35,
                "status": "Active",
                "image_url": "https://images.unsplash.com/photo-1586201375761-83865001e31c?auto=format&fit=crop&w=300&q=80"
            },
            {
                "id": 2,
                "name": "Coca-Cola 1.5L PET Bottle",
                "category": "Beverages",
                "price": 70.00,
                "stock": 8,
                "status": "Active",
                "image_url": "https://images.unsplash.com/photo-1554866585-cd94860890b7?auto=format&fit=crop&w=300&q=80"
            }
        ]
    }

@router.post("/merchant/{merchant_id}/products", status_code=status.HTTP_201_CREATED)
async def add_merchant_product(
    merchant_id: str,
    payload: ProductItemCreate,
    current_user: dict = Depends(role_required(["merchant", "super_admin"]))
):
    """
    Enables merchants to add new items into inventory with photo and category control.
    """
    return {
        "status": "success",
        "message": f"Product '{payload.name}' added successfully to inventory.",
        "product": {
            "id": 3,  # Generated ID
            "name": payload.name,
            "price": payload.price,
            "stock": payload.stock,
            "category": payload.category,
            "status": "Active",
            "image_url": payload.image_url or "https://images.unsplash.com/photo-default"
        }
    }

@router.patch("/merchant/products/{product_id}")
async def update_merchant_product(
    product_id: int,
    payload: ProductItemUpdate,
    current_user: dict = Depends(role_required(["merchant", "super_admin"]))
):
    """
    Allows quick toggling between Active/Offline states or updating stock/pricing without item deletion loops.
    """
    return {
        "status": "success",
        "message": f"Product ID {product_id} updated successfully.",
        "updated_fields": payload.dict(exclude_unset=True)
    }

@router.patch("/merchant/orders/update")
async def update_merchant_order(
    payload: MerchantOrderUpdate,
    current_user: dict = Depends(role_required(["merchant", "super_admin"]))
):
    """
    Manages incoming preparation states and customer fulfillment schedules dynamically.
    """
    return {
        "status": "success",
        "message": f"Order {payload.order_id} updated to '{payload.status}'.",
        "estimated_prep_time": f"{payload.prep_time_minutes} minutes"
    }


# ==========================================
# 4. CONTROL TOWER ADMIN DASHBOARD MODULE
# ==========================================

@router.get("/admin/control-tower/overview")
async def get_control_tower_overview(
    current_user: dict = Depends(role_required(["super_admin", "city_operations"]))
):
    """
    Provides system-wide overview monitoring active users, ride volumes, and disputes.
    """
    return {
        "platform_metrics": {
            "total_active_users": 1245,
            "todays_rides": 389,
            "pending_disputes": 3
        }
    }

@router.patch("/admin/users/role")
async def update_user_role(
    payload: UserRoleUpdate,
    current_user: dict = Depends(role_required(["super_admin"]))
):
    """
    Implements Role-Based Access Control (RBAC) management strictly for 'super_admin' roles.
    """
    allowed_roles = ["super_admin", "support_agent", "city_operations", "driver", "customer", "merchant"]
    if payload.new_role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role specified. Must be one of {allowed_roles}"
        )
    
    return {
        "status": "success",
        "message": f"User ID {payload.user_id} successfully updated to role: {payload.new_role}"
    }


# ==========================================
# 5. REAL-TIME WEBSOCKET TELEMETRY MODULE
# ==========================================

@router.websocket("/ws/telemetry/{channel_id}")
async def websocket_telemetry_endpoint(websocket: WebSocket, channel_id: str):
    """
    Streams live GPS coordinate updates and trip status changes for drivers and tracking passengers.
    """
    await manager.connect(channel_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Broadcast incoming raw telemetry payload to everyone tracking this channel/ride
            await manager.broadcast_telemetry(channel_id, {"raw_payload": data})
    except WebSocketDisconnect:
        manager.disconnect(channel_id, websocket)


# ==========================================
# 6. REAL-TIME MERCHANT WEBSOCKET CHANNEL
# ==========================================

@router.websocket("/ws/merchant/{merchant_id}")
async def websocket_merchant_endpoint(websocket: WebSocket, merchant_id: str):
    """
    Dedicated real-time websocket connection for merchants to receive continuous order pings, 
    chat messages from customers/riders, and auto-stock depletion syncs.
    """
    await manager.connect(merchant_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Broadcast or echo merchant actions/chat payloads across active operator sessions
            await manager.broadcast_telemetry(merchant_id, {"merchant_event": data})
    except WebSocketDisconnect:
        manager.disconnect(merchant_id, websocket)