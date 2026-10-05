import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
from datetime import datetime, timezone
import uvicorn
import json
from typing import List
from geopy.geocoders import Nominatim

from astronomy.engine import FalakCalculator
from ai.predictive_cache import PredictiveCache

app = FastAPI(title="FalakHub API", version="1.1.0")

# CORS untuk mengizinkan akses dari Vercel/Frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

calc = None
cache = None

def get_calculator():
    global calc, cache
    if calc is None:
        calc = FalakCalculator()
        cache = PredictiveCache(calc)
    return calc, cache

class HijriDate(BaseModel):
    day: int
    month_name: str
    year: int
    formatted: str

class EphemerisResponse(BaseModel):
    time_utc: str
    sunset_utc: str
    gmst_hours: float
    sun_alt: float
    sun_az: float
    sun_ra: float
    sun_dec: float
    moon_alt: float
    moon_az: float
    moon_ra: float
    moon_dec: float
    arcv: float
    arcl: float
    illumination: float
    mabims_status: str
    is_visible: bool
    hijri: HijriDate

@app.get("/api/ephemeris", response_model=EphemerisResponse)
async def get_ephemeris(lat: float, lon: float, date: str, timestamp: str = None):
    """
    Get highly precise ephemeris data.
    """
    try:
        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            except:
                dt = datetime.now(timezone.utc)
        else:
            dt = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            
        c, ca = get_calculator()
        data = c.calculate_ephemeris(lat, lon, dt)
        
        # Log query for AI caching mechanism
        ca.train([[lat, lon]])
        
        return data
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=f"INIT/RUNTIME ERROR: {str(e)}")

@app.get("/api/map/mabims")
async def get_mabims_map(date: str):
    """
    Returns a global grid of MABIMS visibility for the given date.
    Response is Geobuf encoded for spatial Big Data optimization.
    """
    try:
        dt = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        # Using a coarse resolution for the demo.
        c, ca = get_calculator()
        pbf_data = ca.generate_global_grid(dt, resolution=5)
        return Response(content=pbf_data, media_type="application/x-protobuf")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"ERROR: {str(e)}")

@app.get("/api/search")
async def search_location(q: str):
    """
    Search for a city/location and get its coordinates.
    """
    try:
        from geopy.geocoders import Nominatim
        geolocator = Nominatim(user_agent="FalakHub_App")
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

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        print("Perangkat terhubung ke WebSocket.")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        print("Perangkat terputus dari WebSocket.")

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

manager = ConnectionManager()

class TargetCoordinates(BaseModel):
    target_azimuth: float
    target_altitude: float

@app.websocket("/ws/esp32")
async def websocket_esp32(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Tetap listen untuk menangkap pesan jika ESP32 mengirim balasan / telemetry
            data = await websocket.receive_text()
            print(f"Pesan dari ESP32: {data}")
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.post("/api/point-hilal")
async def point_hilal(target: TargetCoordinates):
    payload = {
        "command": "POINT_HILAL",
        "target_azimuth": target.target_azimuth,
        "target_altitude": target.target_altitude
    }
    # Ubah dictionary python menjadi JSON string dan kirim ke ESP32
    await manager.broadcast(json.dumps(payload))
    return {"status": "success", "message": "Command POINT_HILAL berhasil dikirim ke ESP32", "payload": payload}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)