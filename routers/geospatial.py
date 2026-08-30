from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
import models
from geoalchemy2.functions import ST_DWithin, ST_Distance
from geoalchemy2.elements import WKTElement

router = APIRouter(prefix="/geo", tags=["Geospatial Delivery"])

@router.get("/nearby-drivers")
async def get_nearby_drivers(
    lat: float, 
    lon: float, 
    radius_km: float = 3.0, 
    db: Session = Depends(get_db)
):
    """
    Find all active drivers within a given radius (in km) sorted by proximity 
    using PostGIS spatial indexing.
    """
    radius_meters = radius_km * 1000
    point_wkt = f'POINT({lon} {lat})'
    reference_point = WKTElement(point_wkt, srid=4326)

    try:
        nearby_drivers = (
            db.query(
                models.DriverLocation,
                ST_Distance(
                    models.DriverLocation.geom, 
                    reference_point
                ).label("distance_meters")
            )
            .filter(models.DriverLocation.is_active == True)
            .filter(
                ST_DWithin(
                    models.DriverLocation.geom,
                    reference_point,
                    radius_meters
                )
            )
            .order_by(models.DriverLocation.geom.distance_centroid(reference_point))
            .all()
        )

        results = []
        for driver, distance in nearby_drivers:
            results.append({
                "driver_id": driver.driver_id,
                "battery_level": getattr(driver, "battery_level", 100),
                "distance_km": round(distance / 1000, 2)
            })

        return {
            "success": True,
            "count": len(results),
            "drivers": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PostGIS error: {str(e)}")