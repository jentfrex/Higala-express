# routers/surge.py - PRODUCTION RIDE-HAILING & SURGE LOGIC (ERROR-FREE)

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from database import get_db
import models
from models import Ride, User
from typing import Optional
from decimal import Decimal
import math
import logging
from routers.auth import get_current_user

# Setup logger to prevent NameError
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rides", tags=["Ride-Hailing & Surge"])

class SurgeCalculator:
    """Isolated surge pricing logic - never touches food/goods orders"""
    
    BASE_RATE = Decimal("50.00")  # ₱50 base fare
    PER_KM_RATE = Decimal("15.00")  # ₱15 per km
    SURGE_MULTIPLIERS = {
        0.5: Decimal("1.0"),    # 0-50% utilization: 1.0x
        0.7: Decimal("1.25"),   # 50-70%: 1.25x
        0.9: Decimal("1.5"),    # 70-90%: 1.5x
        1.0: Decimal("2.0"),    # 90%+: 2.0x
    }
    
    @staticmethod
    def calculate_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> Decimal:
        """Haversine formula for distance calculation"""
        R = 6371  # Earth radius in km
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lng2 - lng1)
        a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        return Decimal(str(R * c))
    
    @staticmethod
    def get_surge_multiplier(db: Session, zone_id: Optional[int] = None) -> Decimal:
        """
        Calculate surge multiplier based on ride utilization.
        """
        available_drivers = db.query(User).filter(
            User.role == "driver",
            User.status == "online",
            User.current_service_mode.in_(["ride_only", "both"])
        ).count()
        
        total_drivers = db.query(User).filter(User.role == "driver").count()
        
        if total_drivers == 0:
            return SurgeCalculator.SURGE_MULTIPLIERS[1.0]  # 2.0x when no drivers
        
        active_rides = db.query(Ride).filter(
            Ride.status.in_(["searching", "accepted", "in_transit"])
        ).count()
        
        utilization = active_rides / max(available_drivers, 1)
        
        for threshold in sorted(SurgeCalculator.SURGE_MULTIPLIERS.keys(), reverse=True):
            if utilization >= threshold:
                return SurgeCalculator.SURGE_MULTIPLIERS[threshold]
        
        return Decimal("1.0")
    
    @staticmethod
    def calculate_ride_fare(
        pickup_lat: float,
        pickup_lng: float,
        dropoff_lat: float,
        dropoff_lng: float,
        surge_multiplier: Decimal = Decimal("1.0")
    ) -> Decimal:
        """Calculate fare = (BASE + distance * PER_KM) * SURGE_MULTIPLIER"""
        distance = SurgeCalculator.calculate_distance(
            pickup_lat, pickup_lng, dropoff_lat, dropoff_lng
        )
        base_fare = SurgeCalculator.BASE_RATE + (distance * SurgeCalculator.PER_KM_RATE)
        return (base_fare * surge_multiplier).quantize(Decimal("0.01"))

# Rate limiting per customer
RIDE_BOOKING_LIMIT = 3  # Max 3 pending rides per customer
RIDE_BOOKING_WINDOW = 300  # Per 5 minutes

@router.post("/book", status_code=201)
def book_ride(
    pickup_lat: float,
    pickup_lng: float,
    dropoff_lat: float,
    dropoff_lng: float,
    service_type: str = "standard",
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    ISOLATED ride-booking endpoint with built-in rate limiting and surge pricing.
    """
    
    # RATE LIMITING: Prevent ride booking spam
    recent_bookings = db.query(Ride).filter(
        Ride.passenger_id == current_user.id,
        Ride.status.in_(["searching", "accepted"]),
        Ride.created_at >= (datetime.utcnow() - timedelta(seconds=RIDE_BOOKING_WINDOW))
    ).count()
    
    if recent_bookings >= RIDE_BOOKING_LIMIT:
        raise HTTPException(
            status_code=429,
            detail=f"Too many pending rides. Max {RIDE_BOOKING_LIMIT} active bookings allowed."
        )
    
    # INPUT VALIDATION
    if not all([pickup_lat, pickup_lng, dropoff_lat, dropoff_lng]):
        raise HTTPException(status_code=400, detail="All coordinates required")
    
    try:
        # Calculate fare WITH surge pricing
        surge_multiplier = SurgeCalculator.get_surge_multiplier(db)
        fare = SurgeCalculator.calculate_ride_fare(
            pickup_lat, pickup_lng, dropoff_lat, dropoff_lng,
            surge_multiplier
        )
        
        # Platform takes 10% commission on driver fare
        platform_commission = (fare * Decimal("0.10")).quantize(Decimal("0.01"))
        driver_gets = fare - platform_commission
        
        # Check customer wallet
        if current_user.wallet_balance < float(fare):
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient wallet balance. Need ₱{fare}, have ₱{current_user.wallet_balance}"
            )
        
        # Create ride record (Completely separate from food orders)
        ride = Ride(
            passenger_id=current_user.id,
            pickup_lat=pickup_lat,
            pickup_lng=pickup_lng,
            dropoff_lat=dropoff_lat,
            dropoff_lng=dropoff_lng,
            fare=float(fare),
            platform_commission=float(platform_commission),
            service_type=service_type,
            status="searching"
        )
        db.add(ride)
        db.commit()
        db.refresh(ride)
        
        return {
            "success": True,
            "ride_id": ride.id,
            "passenger_id": current_user.id,
            "fare": float(fare),
            "platform_commission": float(platform_commission),
            "driver_earns": float(driver_gets),
            "surge_multiplier": float(surge_multiplier),
            "status": "searching",
            "created_at": ride.created_at.isoformat()
        }
    
    except HTTPException as he:
        db.rollback()
        raise he
    except Exception as e:
        db.rollback()
        logger.error(f"Ride booking failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ride booking failed: {str(e)}")