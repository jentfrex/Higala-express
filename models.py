from datetime import datetime
import os
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, Time, inspect
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from geoalchemy2 import Geometry
from database import Base, SoftDeleteMixin
from enum import Enum


class User(Base, SoftDeleteMixin):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    role = Column(String, default="customer", index=True)  # "customer", "driver", "admin", "merchant"
    wallet_balance = Column(Float, default=1000.0)
    escrow_balance = Column(Float, default=0.0)
    status = Column(String, default="offline", index=True)  # For drivers: "online" / "offline" / "busy"
    last_lat = Column(Float, nullable=True)
    last_lng = Column(Float, nullable=True)

    # --- Demography / Validation fields ---
    gender = Column(String, nullable=True)
    birthdate = Column(DateTime, nullable=True)

    # --- Driver Service Mode Toggle ("ride_only", "delivery_only", "both") ---
    current_service_mode = Column(String, default="both", index=True)

    # --- Driver Delivery Counter for Dynamic Commission Tiers ---
    total_completed_deliveries = Column(Integer, default=0, index=True)

    # Relationships
    orders_as_customer = relationship("Order", foreign_keys="Order.customer_id", back_populates="customer")
    orders_as_driver = relationship("Order", foreign_keys="Order.driver_id", back_populates="driver")
    merchants = relationship("Merchant", back_populates="owner")
    payouts = relationship("DriverPayout", back_populates="driver", cascade="all, delete-orphan")
    rides_as_passenger = relationship("Ride", foreign_keys="Ride.passenger_id", back_populates="passenger")
    rides_as_driver = relationship("Ride", foreign_keys="Ride.driver_id", back_populates="driver")


class City(Base, SoftDeleteMixin):
    __tablename__ = "cities"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    country = Column(String, default="Philippines")
    currency = Column(String, default="PHP")
    tax_rate = Column(Float, default=0.12)  # e.g., 12% VAT
    is_active = Column(Boolean, default=True)

    zones = relationship("DeliveryZone", back_populates="city", cascade="all, delete-orphan")


class DeliveryZone(Base, SoftDeleteMixin):
    __tablename__ = "delivery_zones"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)  # e.g., "Cagayan de Oro - Uptown", "Downtown"
    city_id = Column(Integer, ForeignKey("cities.id"), index=True)
    base_fare = Column(Float, default=50.0)
    per_km_rate = Column(Float, default=15.0)

    city = relationship("City", back_populates="zones")
    merchants = relationship("Merchant", back_populates="zone")


# --- Multi-Branch & Franchise Models ---

class MerchantBrand(Base, SoftDeleteMixin):
    __tablename__ = "merchant_brands"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)  # e.g., "KFC" or local brand
    category = Column(String, index=True)
    logo_url = Column(String, nullable=True)

    branches = relationship("MerchantBranch", back_populates="brand", cascade="all, delete-orphan")


class MerchantBranch(Base, SoftDeleteMixin):
    __tablename__ = "merchant_branches"

    id = Column(Integer, primary_key=True, index=True)
    brand_id = Column(Integer, ForeignKey("merchant_brands.id"), nullable=False, index=True)
    branch_name = Column(String, nullable=False)  # e.g., "KFC - SM Downtown CDO"
    address = Column(Text, nullable=False)
    
    # Geofencing Coordinates
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    geofence_radius_km = Column(Float, default=5.0)

    # Operations
    is_active = Column(Boolean, default=True)
    opening_time = Column(Time, nullable=True)
    closing_time = Column(Time, nullable=True)

    brand = relationship("MerchantBrand", back_populates="branches")
    inventory = relationship("BranchInventory", back_populates="branch", cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="branch")


class BranchInventory(Base, SoftDeleteMixin):
    __tablename__ = "branch_inventory"

    id = Column(Integer, primary_key=True, index=True)
    branch_id = Column(Integer, ForeignKey("merchant_branches.id"), nullable=False, index=True)
    item_name = Column(String, nullable=False)
    price = Column(Float, nullable=False)
    is_available = Column(Boolean, default=True)  # Branch-specific stock toggle
    
    # --- Carinderia / Daily Portion Tracking ---
    max_daily_stock = Column(Integer, nullable=True)  # e.g., 20 servings of Humba
    current_stock = Column(Integer, nullable=True)   # Current remaining servings
    is_daily_special = Column(Boolean, default=True)   # Resets or tracks daily

    branch = relationship("MerchantBranch", back_populates="inventory")


# --- Geospatial Driver Tracking Model ---

class DriverLocation(Base, SoftDeleteMixin):
    __tablename__ = "driver_locations"

    id = Column(Integer, primary_key=True, index=True)
    driver_id = Column(Integer, ForeignKey("users.id"), unique=True, index=True)
    
    # Safely checks environment variable for SQLite vs PostGIS without import errors
    geom = Column(String, index=True) if "sqlite" in os.getenv("DATABASE_URL", "sqlite:///./higala_express.db").lower() else Column(Geometry(geometry_type='POINT', srid=4326, spatial_index=False), index=True)
    
    battery_level = Column(Integer, default=100)
    is_active = Column(Boolean, default=True)


# --- Legacy Merchant Setup (Retained for Compatibility) ---

class Merchant(Base, SoftDeleteMixin):
    __tablename__ = "merchants"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), index=True)
    zone_id = Column(Integer, ForeignKey("delivery_zones.id"), nullable=True, index=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    is_active = Column(Boolean, default=True)

    owner = relationship("User", back_populates="merchants")
    zone = relationship("DeliveryZone", back_populates="merchants")
    orders = relationship("Order", back_populates="merchant")


class MasterOrder(Base, SoftDeleteMixin):
    __tablename__ = "master_orders"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("users.id"), index=True)
    total_amount = Column(Float, default=0.0)
    status = Column(String, default="pending", index=True)  # pending, paid, completed, cancelled
    
    # Relationships
    customer = relationship("User", foreign_keys=[customer_id])
    sub_orders = relationship("Order", back_populates="master_order", cascade="all, delete-orphan")


class Order(Base, SoftDeleteMixin):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    master_order_id = Column(
        Integer, 
        ForeignKey("master_orders.id", ondelete="CASCADE"), 
        nullable=True, 
        index=True
    )
    item_description = Column(String, index=True)
    pickup_location = Column(String)
    dropoff_location = Column(String)
    price = Column(Float, default=50.0)
    status = Column(String, default="pending", index=True)
    
    customer_id = Column(
        Integer, 
        ForeignKey("users.id", ondelete="RESTRICT"), 
        index=True
    )
    driver_id = Column(
        Integer, 
        ForeignKey("users.id", ondelete="SET NULL"), 
        nullable=True, 
        index=True
    )
    merchant_id = Column(
        Integer, 
        ForeignKey("merchants.id", ondelete="RESTRICT"), 
        nullable=True, 
        index=True
    )
    branch_id = Column(
        Integer, 
        ForeignKey("merchant_branches.id", ondelete="CASCADE"), 
        nullable=True, 
        index=True
    )
    
    current_lat = Column(Float, nullable=True)
    current_lng = Column(Float, nullable=True)

    # --- GPS Safeguards & Landmark Metadata ---
    landmark_description = Column(String, nullable=True)
    customer_latitude = Column(Float, nullable=True)
    customer_longitude = Column(Float, nullable=True)
    pin_is_flagged = Column(Boolean, default=False)
    pin_feedback = Column(String, nullable=True)

    # Relationships
    master_order = relationship(
        "MasterOrder", 
        back_populates="sub_orders", 
        foreign_keys=[master_order_id]
    )
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    customer = relationship(
        "User", 
        foreign_keys=[customer_id], 
        back_populates="orders_as_customer"
    )
    driver = relationship(
        "User", 
        foreign_keys=[driver_id], 
        back_populates="orders_as_driver"
    )
    merchant = relationship(
        "Merchant", 
        back_populates="orders"
    )
    branch = relationship(
        "MerchantBranch", 
        back_populates="orders"
    )
    reviews = relationship("Review", back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base, SoftDeleteMixin):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), index=True)
    item_name = Column(String, nullable=False)
    quantity = Column(Integer, default=1)
    price = Column(Float, default=0.0)

    # Relationships
    order = relationship("Order", back_populates="items")


# --- New Payment & Commission Models ---

class PaymentMethod(str, Enum):
    CASH_ON_DELIVERY = "cash_on_delivery"
    BANK_TRANSFER = "bank_transfer"
    WALLET = "wallet"


class PaymentStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"


class Payment(Base, SoftDeleteMixin):
    __tablename__ = "payments"
    
    id = Column(Integer, primary_key=True, index=True)
    master_order_id = Column(Integer, ForeignKey("master_orders.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    amount = Column(Float, nullable=False)
    payment_method = Column(String, default=PaymentMethod.WALLET)
    status = Column(String, default=PaymentStatus.PENDING)
    transaction_reference = Column(String, unique=True, nullable=True)
    notes = Column(String, nullable=True)
    payment_date = Column(DateTime, nullable=True)


class MerchantCommission(Base, SoftDeleteMixin):
    __tablename__ = "merchant_commission"
    
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    merchant_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    gross_amount = Column(Float)
    commission_rate = Column(Float, default=0.10)  # 10% platform fee
    commission_amount = Column(Float)
    merchant_payout = Column(Float)
    status = Column(String, default="pending")  # pending, processed, paid_out
    payout_date = Column(DateTime, nullable=True)


class BankTransferRequest(Base, SoftDeleteMixin):
    __tablename__ = "bank_transfer_requests"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    order_id = Column(Integer, ForeignKey("orders.id"))
    bank_name = Column(String)
    account_name = Column(String)
    account_number = Column(String)
    amount = Column(Float)
    reference_number = Column(String, unique=True)  # e.g., HG-20240901-12345
    status = Column(String, default="awaiting_payment")  # awaiting_payment, payment_confirmed, expired
    payment_deadline = Column(DateTime)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    action = Column(String, index=True)
    details = Column(String, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)


# --- Enterprise Feature Models ---

class WebhookSubscription(Base, SoftDeleteMixin):
    __tablename__ = "webhook_subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    merchant_id = Column(Integer, ForeignKey("users.id"), index=True)
    url = Column(String, nullable=False)
    secret = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)


class WebhookDeliveryLog(Base):
    __tablename__ = "webhook_delivery_logs"

    id = Column(Integer, primary_key=True, index=True)
    merchant_id = Column(Integer, ForeignKey("users.id"), index=True)
    event_type = Column(String, nullable=False)
    payload = Column(Text, nullable=False)
    response_status = Column(Integer, nullable=True)
    response_body = Column(Text, nullable=True)
    success = Column(Boolean, default=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())


class WebhookEventQueue(Base):
    """Reliable webhook delivery queue - persists events for retry"""
    __tablename__ = "webhook_event_queue"

    id = Column(Integer, primary_key=True, index=True)
    merchant_id = Column(Integer, ForeignKey("users.id"), index=True)
    event_type = Column(String, nullable=False)
    payload = Column(Text, nullable=False)
    status = Column(String, default="pending", index=True)  # pending, delivered, failed
    attempt_count = Column(Integer, default=0)
    next_retry_at = Column(DateTime, nullable=True)
    last_error = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    delivered_at = Column(DateTime, nullable=True)


class DriverShift(Base, SoftDeleteMixin):
    __tablename__ = "driver_shifts"

    id = Column(Integer, primary_key=True, index=True)
    driver_id = Column(Integer, ForeignKey("users.id"), index=True)
    start_time = Column(DateTime, default=datetime.utcnow)
    end_time = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    total_hours = Column(Float, default=0.0)


class SupportTicket(Base, SoftDeleteMixin):
    __tablename__ = "support_tickets"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), index=True, nullable=True)
    subject = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    status = Column(String, default="open", index=True)  # open, in_progress, resolved, closed


class Review(Base, SoftDeleteMixin):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), index=True)
    customer_id = Column(Integer, ForeignKey("users.id"), index=True)
    driver_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    merchant_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    rating = Column(Integer, nullable=False)
    comment = Column(String, nullable=True)

    order = relationship("Order", back_populates="reviews")


# --- Automated Commission, Payout & Cash Ledger Models ---

class WalletTransaction(Base, SoftDeleteMixin):
    __tablename__ = "wallet_transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    amount = Column(Float, nullable=False)  # Positive for credit, negative for debit
    transaction_type = Column(String, nullable=False)  # e.g., "commission", "payout", "order_payment"
    reference_id = Column(Integer, nullable=True)  # MasterOrder or Order ID
    description = Column(String, nullable=True)


class DriverPayout(Base, SoftDeleteMixin):
    __tablename__ = "driver_payouts"

    id = Column(Integer, primary_key=True, index=True)
    driver_id = Column(Integer, ForeignKey("users.id"), index=True)
    amount = Column(Float, nullable=False)
    status = Column(String, default="pending")  # pending, processed, paid
    created_at = Column(DateTime, default=datetime.utcnow)

    driver = relationship("User", back_populates="payouts")


class RiderCashLedger(Base, SoftDeleteMixin):
    __tablename__ = "rider_cash_ledgers"

    id = Column(Integer, primary_key=True, index=True)
    driver_id = Column(Integer, ForeignKey("users.id"), index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True, index=True)
    
    amount_collected = Column(Float, default=0.0)    # Total cash collected from customer for COD
    commission_deducted = Column(Float, default=0.0) # Platform cut / delivery fee portion
    net_cash_due = Column(Float, default=0.0)        # Net cash the driver must remit to the company
    
    status = Column(String, default="pending_remittance", index=True)  # pending_remittance, verified, disputed
    remittance_reference = Column(String, nullable=True) # GCash/Maya reference number or proof
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    driver = relationship("User", foreign_keys=[driver_id])
    order = relationship("Order", foreign_keys=[order_id])


class IdempotencyRecord(Base, SoftDeleteMixin):
    __tablename__ = "idempotency_records"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, index=True, nullable=False)
    path = Column(String, nullable=False)
    response_status_code = Column(Integer, nullable=False)
    response_body = Column(Text, nullable=False)  # JSON-serialized response string
    created_at = Column(DateTime, default=datetime.utcnow)


# --- Passenger Ride-Hailing Model (Angkas Style) ---

class Ride(Base, SoftDeleteMixin):
    __tablename__ = "rides"
    
    id = Column(Integer, primary_key=True, index=True)
    passenger_id = Column(Integer, ForeignKey("users.id"), index=True)
    driver_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    pickup_lat = Column(Float, nullable=False)
    pickup_lng = Column(Float, nullable=False)
    dropoff_lat = Column(Float, nullable=False)
    dropoff_lng = Column(Float, nullable=False)
    fare = Column(Float, nullable=False)
    platform_commission = Column(Float, nullable=False)  # 10% cut
    service_type = Column(String, default="passenger_transport", index=True)  # "passenger_transport" vs "delivery_on_demand"
    status = Column(String, default="searching", index=True)  # searching, accepted, in_transit, completed, cancelled
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    passenger = relationship("User", foreign_keys=[passenger_id], back_populates="rides_as_passenger")
    driver = relationship("User", foreign_keys=[driver_id], back_populates="rides_as_driver")


# --- Added Missing Models for main.py Routes ---

class RideBooking(Base, SoftDeleteMixin):
    __tablename__ = "ride_bookings"

    id = Column(Integer, primary_key=True, index=True)
    passenger_id = Column(Integer, ForeignKey("users.id"), index=True)
    service_type = Column(String, default="standard")
    fare_amount = Column(Float, default=0.0)
    status = Column(String, default="pending", index=True)


class FoodOrder(Base, SoftDeleteMixin):
    __tablename__ = "food_orders"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("users.id"), index=True)
    merchant_id = Column(Integer, ForeignKey("merchants.id"), index=True)
    total_price = Column(Float, default=0.0)
    status = Column(String, default="pending", index=True)


class SOSAlert(Base, SoftDeleteMixin):
    __tablename__ = "sos_alerts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    status = Column(String, default="active", index=True)