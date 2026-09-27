from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
from datetime import datetime, timezone
import uvicorn
from geopy.geocoders import Nominatim

from astronomy.engine import FalakCalculator
from ai.predictive_cache import PredictiveCache

app = FastAPI(title="FalakHub API", version="1.1.0")

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

calc = FalakCalculator()
cache = PredictiveCache(calc)
geolocator = Nominatim(user_agent="FalakHub_App")

class HijriDate(BaseModel):
    day: int
    month_name: str
    year: int
    formatted: str

class EphemerisResponse(BaseModel):
    time_utc: str
    gmst_hours: float
    sun_alt: float
    sun_az: float
    moon_alt: float
    moon_az: float
    arcv: float
    arcl: float
    illumination: float
    mabims_status: str
    is_visible: bool
    hijri: HijriDate

@app.get("/api/ephemeris", response_model=EphemerisResponse)
async def get_ephemeris(lat: float, lon: float, date: str):
    """
    Get highly precise ephemeris data for a specific location at sunset for the given date.
    Date format: YYYY-MM-DD
    """
    try:
        dt = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        data = calc.calculate_ephemeris(lat, lon, dt)
        
        # Log query for AI caching mechanism
        cache.train([[lat, lon]])
        
        return data
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/map/mabims")
async def get_mabims_map(date: str):
    """
    Returns a global grid of MABIMS visibility for the given date.
    Response is Geobuf encoded for spatial Big Data optimization.
    """
    try:
        dt = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        # Using a coarse resolution for the demo.
        pbf_data = cache.generate_global_grid(dt, resolution=5)
        return Response(content=pbf_data, media_type="application/x-protobuf")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/search")
async def search_location(q: str):
    """
    Search for a city/location and get its coordinates.
    """
    try:
        location = geolocator.geocode(q)
        if location:
            return {
                "name": location.address,
                "lat": location.latitude,
                "lon": location.longitude
            }
        else:
            raise HTTPException(status_code=404, detail="Location not found")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
