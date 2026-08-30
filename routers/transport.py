from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from database import get_db
import models

router = APIRouter(prefix="/api/transport", tags=["Passenger & Delivery Transport"])

class RideBookingRequest(BaseModel):
    passenger_id: int
    pickup_lat: float
    pickup_lng: float
    dropoff_lat: float
    dropoff_lng: float
    fare: float 
    service_type: Optional[str] = "passenger_transport"

class RideAcceptRequest(BaseModel):
    driver_id: int

@router.post("/book", status_code=status.HTTP_201_CREATED)
def book_ride(payload: RideBookingRequest, db: Session = Depends(get_db)):
    # 1. Verify passenger exists and check wallet balance
    passenger = db.query(models.User).filter(models.User.id == payload.passenger_id).first()
    if not passenger:
        raise HTTPException(status_code=404, detail="Passenger not found")
        
    if passenger.wallet_balance is None or passenger.wallet_balance < payload.fare:
        raise HTTPException(status_code=400, detail="Insufficient wallet balance for this ride")

    # 2. Deduct fare upfront from passenger wallet
    passenger.wallet_balance -= payload.fare
    db.add(models.WalletTransaction(
        user_id=passenger.id,
        amount=-payload.fare,
        transaction_type="ride_payment",
        description=f"Payment for {payload.service_type}"
    ))

    # 3. Calculate initial platform commission at 15%
    initial_commission_rate = 0.15
    commission = payload.fare * initial_commission_rate
    
    new_ride = models.Ride(
        passenger_id=payload.passenger_id,
        pickup_lat=payload.pickup_lat,
        pickup_lng=payload.pickup_lng,
        dropoff_lat=payload.dropoff_lat,
        dropoff_lng=payload.dropoff_lng,
        fare=payload.fare,
        platform_commission=commission,
        service_type=payload.service_type,
        status="searching"
    )
    
    db.add(new_ride)
    db.commit()
    db.refresh(new_ride)
    
    return {
        "success": True,
        "message": f"Request created successfully for {payload.service_type}. Searching for nearby drivers...",
        "ride_id": new_ride.id,
        "service_type": new_ride.service_type,
        "fare": new_ride.fare,
        "platform_commission": new_ride.platform_commission,
        "status": new_ride.status
    }

@router.post("/{ride_id}/accept")
def accept_ride(ride_id: int, payload: RideAcceptRequest, db: Session = Depends(get_db)):
    ride = db.query(models.Ride).filter(models.Ride.id == ride_id).first()
    if not ride:
        raise HTTPException(status_code=404, detail="Request not found")
    
    if ride.status != "searching":
        raise HTTPException(status_code=400, detail="Request is no longer available for acceptance")
        
    ride.driver_id = payload.driver_id
    ride.status = "accepted"
    db.commit()
    db.refresh(ride)
    
    return {
        "success": True,
        "message": "Request accepted by driver.",
        "ride_id": ride.id,
        "driver_id": ride.driver_id,
        "status": ride.status
    }

@router.patch("/{ride_id}/status")
def update_ride_status(ride_id: int, new_status: str, db: Session = Depends(get_db)):
    valid_statuses = ["searching", "accepted", "in_transit", "completed", "cancelled"]
    if new_status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Choose from {valid_statuses}")
        
    ride = db.query(models.Ride).filter(models.Ride.id == ride_id).first()
    if not ride:
        raise HTTPException(status_code=404, detail="Request not found")
        
    old_status = ride.status
    ride.status = new_status

    # If the ride is newly marked as "completed", settle the driver payout using the sliding scale!
    if new_status == "completed" and old_status != "completed" and ride.driver_id:
        driver = db.query(models.User).filter(models.User.id == ride.driver_id).first()
        if driver:
            # Check completed rides count for the driver
            completed_count = db.query(models.Ride).filter(
                models.Ride.driver_id == driver.id, 
                models.Ride.status == "completed"
            ).count()

            # Sliding scale: 15% platform cut for first 10, drops to 5% for 11+
            commission_rate = 0.15 if completed_count <= 10 else 0.05
            
            # Recalculate commission and payout
            actual_commission = ride.fare * commission_rate
            ride.platform_commission = actual_commission
            driver_payout = ride.fare - actual_commission

            driver.wallet_balance += driver_payout
            db.add(models.WalletTransaction(
                user_id=driver.id,
                amount=driver_payout,
                transaction_type="driver_ride_payout",
                description=f"Earnings for Ride #{ride.id} (Platform tier: {int(commission_rate * 100)}%)"
            ))

    db.commit()
    
    return {
        "success": True,
        "message": f"Status updated to '{new_status}'",
        "ride_id": ride.id,
        "status": ride.status
    }

@router.get("/analytics/earnings-breakdown")
def get_transport_earnings_breakdown(db: Session = Depends(get_db)):
    completed_items = db.query(models.Ride).filter(models.Ride.status == "completed").all()
    
    passenger_rides = [r for r in completed_items if r.service_type == "passenger_transport"]
    delivery_rides = [r for r in completed_items if r.service_type == "delivery_on_demand"]
    
    return {
        "success": True,
        "passenger_transport": {
            "total_completed": len(passenger_rides),
            "gross_fare": sum(r.fare for r in passenger_rides),
            "commission_earned": sum(r.platform_commission for r in passenger_rides)
        },
        "delivery_on_demand": {
            "total_completed": len(delivery_rides),
            "gross_fare": sum(r.fare for r in delivery_rides),
            "commission_earned": sum(r.platform_commission for r in delivery_rides)
        },
        "combined_total_commission": sum(r.platform_commission for r in completed_items)
    }

@router.get("/{ride_id}")
def get_ride_details(ride_id: int, db: Session = Depends(get_db)):
    ride = db.query(models.Ride).filter(models.Ride.id == ride_id).first()
    if not ride:
        raise HTTPException(status_code=404, detail="Request not found")
    return {"success": True, "ride": ride}