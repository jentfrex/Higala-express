import math
from sqlalchemy.orm import Session
from typing import Optional
import models

EARTH_RADIUS_KM = 6371.0

def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate Haversine distance in kilometers between two GPS coordinates."""
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_KM * c

def calculate_dynamic_eta(distance_km: float, average_speed_kmh: float = 25.0, buffer_minutes: int = 5) -> int:
    """Calculates ETA in minutes with city traffic buffer."""
    if average_speed_kmh <= 0:
        average_speed_kmh = 25.0
    travel_time_hours = distance_km / average_speed_kmh
    travel_time_minutes = travel_time_hours * 60
    return int(travel_time_minutes + buffer_minutes)

def find_optimal_driver(db: Session, merchant_lat: float, merchant_lon: float, max_radius_km: float = 5.0) -> Optional[dict]:
    """Finds the closest available driver within the target radius using User model."""
    active_drivers = db.query(models.User).filter(
        models.User.role == "driver",
        models.User.status == "online"
    ).all()
    
    best_driver = None
    min_distance = float('inf')

    for driver in active_drivers:
        driver_lat = getattr(driver, "last_lat", None)
        driver_lon = getattr(driver, "last_lng", None)

        if driver_lat is None or driver_lon is None:
            continue

        dist = calculate_distance(merchant_lat, merchant_lon, driver_lat, driver_lon)
        if dist <= max_radius_km and dist < min_distance:
            min_distance = dist
            best_driver = driver

    if best_driver:
        eta = calculate_dynamic_eta(min_distance)
        return {
            "driver_id": best_driver.id,
            "distance_km": round(min_distance, 2),
            "estimated_arrival_minutes": eta
        }
    
    return None

def assign_nearest_driver(order_id: int, db: Session):
    """Finds the closest active driver with 'online' status and assigns the order."""
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order or not order.merchant:
        return {"success": False, "message": "Order or Merchant not found"}

    # Get merchant coordinates with fallbacks (Cagayan de Oro default)
    merchant_lat = getattr(order.merchant, "latitude", 8.4542)
    merchant_lon = getattr(order.merchant, "longitude", 124.6319)

    # Fetch active drivers currently online
    active_drivers = db.query(models.User).filter(
        models.User.role == "driver",
        models.User.status == "online"
    ).all()

    if not active_drivers:
        return {"success": False, "message": "No available drivers found online."}

    nearest_driver = None
    min_distance = float('inf')

    for driver in active_drivers:
        driver_lat = getattr(driver, "last_lat", None)
        driver_lon = getattr(driver, "last_lng", None)

        if driver_lat is None or driver_lon is None:
            continue

        distance = calculate_distance(merchant_lat, merchant_lon, driver_lat, driver_lon)
        if distance < min_distance:
            min_distance = distance
            nearest_driver = driver

    if nearest_driver:
        order.driver_id = nearest_driver.id
        order.status = "assigned"
        nearest_driver.status = "busy"  # Set driver to busy on assignment
        db.commit()
        return {
            "success": True, 
            "assigned_driver_id": nearest_driver.id, 
            "distance_km": round(min_distance, 2)
        }
    
    return {"success": False, "message": "No drivers with active GPS coordinates found."}