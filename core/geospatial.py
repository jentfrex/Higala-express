import math
from typing import Optional, Dict, Tuple

# Radius of the earth in kilometers
EARTH_RADIUS_KM = 6371.0

# Northern Mindanao Regional Zones Configuration (Ready for Database Migration)
NORTHERN_MINDANAO_ZONES = {
    "cdo": {
        "name": "Cagayan de Oro",
        "min_lat": 8.35,
        "max_lat": 8.58,
        "min_lng": 124.52,
        "max_lng": 124.78
    },
    "iligan": {
        "name": "Iligan City",
        "min_lat": 8.15,
        "max_lat": 8.35,
        "min_lng": 124.20,
        "max_lng": 124.35
    },
    "bukidnon": {
        "name": "Bukidnon Province",
        "min_lat": 7.50,
        "max_lat": 8.45,
        "min_lng": 124.70,
        "max_lng": 125.40
    }
}

def calculate_distance(lat1: Optional[float], lon1: Optional[float], lat2: Optional[float], lon2: Optional[float]) -> float:
    """
    Calculates the great-circle distance between two points
    on the Earth (specified in decimal degrees) in kilometers using the Haversine formula.
    Returns a safe maximum distance (999999.0) if any coordinate is missing,
    preventing JSON serialization and downstream comparison crashes.
    """
    if lat1 is None or lon1 is None or lat2 is None or lon2 is None:
        return 999999.0

    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.asin(math.sqrt(a))

    return EARTH_RADIUS_KM * c

def is_in_northern_mindanao(lat: Optional[float], lng: Optional[float]) -> Tuple[bool, Optional[str]]:
    """
    Validates if a given coordinate falls within any active zone 
    in the Northern Mindanao cluster (CDO, Iligan, Bukidnon).
    Returns a tuple: (is_valid: bool, zone_name: str or None)
    """
    if lat is None or lng is None:
        return False, None

    for zone_key, zone in NORTHERN_MINDANAO_ZONES.items():
        if (
            zone["min_lat"] <= lat <= zone["max_lat"] and
            zone["min_lng"] <= lng <= zone["max_lng"]
        ):
            return True, zone["name"]

    return False, None