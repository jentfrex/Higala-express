from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


# User / Auth Schemas
class UserBase(BaseModel):
    username: str

class UserCreate(UserBase):
    password: str
    role: Optional[str] = "customer"

class UserOut(UserBase):
    id: int
    role: str
    wallet_balance: float
    escrow_balance: float
    status: str

    model_config = ConfigDict(from_attributes=True)

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None


# Order Schemas
class OrderCreate(BaseModel):
    item_description: str
    pickup_location: str
    dropoff_location: str
    price: Optional[float] = 50.0
    landmark_description: Optional[str] = None
    customer_latitude: Optional[float] = None
    customer_longitude: Optional[float] = None

class OrderOut(BaseModel):
    id: int
    item_description: str
    pickup_location: str
    dropoff_location: str
    price: float
    status: str
    customer_id: int
    driver_id: Optional[int] = None
    landmark_description: Optional[str] = None
    customer_latitude: Optional[float] = None
    customer_longitude: Optional[float] = None
    pin_is_flagged: Optional[bool] = False
    pin_feedback: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# Webhook / Merchant Schemas
class WebhookSubscribe(BaseModel):
    url: str
    merchant_id: int


# Support Ticket Schemas
class SupportTicketCreate(BaseModel):
    subject: str
    description: str
    order_id: Optional[int] = None


# --- Request Schemas ---

class RideBookingCreate(BaseModel):
    service_type: str = "standard"
    fare_amount: float = 50.0

    model_config = ConfigDict(from_attributes=True)


class FoodOrderCreate(BaseModel):
    merchant_id: int
    total_price: float

    model_config = ConfigDict(from_attributes=True)


class SOSAlertCreate(BaseModel):
    latitude: float
    longitude: float

    model_config = ConfigDict(from_attributes=True)


# --- Response / Output Schemas (Fixes FastAPI Return Type Errors) ---

class RideBookingOut(BaseModel):
    id: int
    passenger_id: Optional[int] = None
    service_type: str
    fare_amount: float
    status: str

    model_config = ConfigDict(from_attributes=True)


class FoodOrderOut(BaseModel):
    id: int
    customer_id: Optional[int] = None
    merchant_id: int
    total_price: float
    status: str

    model_config = ConfigDict(from_attributes=True)


class SOSAlertOut(BaseModel):
    id: int
    user_id: Optional[int] = None
    latitude: float
    longitude: float
    status: str

    model_config = ConfigDict(from_attributes=True)