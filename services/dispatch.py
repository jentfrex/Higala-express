from math import radians, sin, cos, sqrt, atan2
from sqlalchemy.orm import Session
from typing import Optional

EARTH_RADIUS_KM = 6371.0

def calculate_haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return EARTH_RADIUS_KM * c

def calculate_dynamic_eta(distance_km: float, average_speed_kmh: float = 25.0, buffer_minutes: int = 5) -> int:
    """Calculates ETA in minutes with city traffic buffer."""
    if average_speed_kmh <= 0:
        average_speed_kmh = 25.0
    travel_time_hours = distance_km / average_speed_kmh
    travel_time_minutes = travel_time_hours * 60
    return int(travel_time_minutes + buffer_minutes)

def find_optimal_driver(db: Session, merchant_lat: float, merchant_lon: float, max_radius_km: float = 5.0) -> Optional[dict]:
    """Finds the closest available driver within the target radius."""
    from models import DriverLocation
    
    available_drivers = db.query(DriverLocation).filter(DriverLocation.is_online == True, DriverLocation.is_busy == False).all()
    
    best_driver = None
    min_distance = float('inf')

    for driver in available_drivers:
        dist = calculate_haversine_distance(merchant_lat, merchant_lon, driver.latitude, driver.longitude)
        if dist <= max_radius_km and dist < min_distance:
            min_distance = dist
            best_driver = driver

    if best_driver:
        eta = calculate_dynamic_eta(min_distance)
        return {
            "driver_id": best_driver.driver_id,
            "distance_km": round(min_distance, 2),
            "estimated_arrival_minutes": eta
        }
    
    return None