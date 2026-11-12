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

app = FastAPI(title="HILTRON API", version="1.1.0")

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
def get_ephemeris(lat: float, lon: float, date: str, timestamp: str = None):
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
def get_mabims_map(date: str):
    """
    Returns a global grid of MABIMS visibility for the given date.
    Response is Geobuf encoded for spatial Big Data optimization.
    """
    try:
        dt = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        # Menggunakan resolusi 10 agar lebih ringan dan tidak timeout (terutama di Vercel/lokal)
        c, ca = get_calculator()
        pbf_data = ca.generate_global_grid(dt, resolution=10)
        return Response(content=pbf_data, media_type="application/x-protobuf")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"ERROR: {str(e)}")

@app.get("/api/search")
def search_location(q: str):
    """
    Search for a city/location and get its coordinates.
    """
    try:
        from geopy.geocoders import Nominatim
        geolocator = Nominatim(user_agent="HILTRON_App")
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

esp32_telemetry = {
    "status": "disconnected",
    "azimuth": 0.0,
    "altitude": 0.0,
    "cal_sys": 0,
    "cal_gyro": 0,
    "cal_accel": 0,
    "cal_mag": 0,
    "cal_locked": False,
    "gps_valid": False,
    "gps_lat": 0.0,
    "gps_lon": 0.0,
    "gps_sats": 0,
    "last_update": None
}

@app.get("/api/telemetry")
def get_telemetry():
    return esp32_telemetry

class TargetCoordinates(BaseModel):
    target_azimuth: float
    target_altitude: float

@app.websocket("/ws/esp32")
async def websocket_esp32(websocket: WebSocket):
    await manager.connect(websocket)
    global esp32_telemetry
    esp32_telemetry["status"] = "connected"
    try:
        while True:
            # Tetap listen untuk menangkap pesan jika ESP32 mengirim balasan / telemetry
            data = await websocket.receive_text()
            try:
                parsed = json.loads(data)
                if parsed.get("type") == "telemetry":
                    esp32_telemetry.update({
                        "status": "connected",
                        "azimuth": parsed.get("azimuth", 0.0),
                        "altitude": parsed.get("altitude", 0.0),
                        "cal_sys": parsed.get("cal_sys", 0),
                        "cal_gyro": parsed.get("cal_gyro", 0),
                        "cal_accel": parsed.get("cal_accel", 0),
                        "cal_mag": parsed.get("cal_mag", 0),
                        "cal_locked": (str(parsed.get("cal_locked", False)).lower() == "true") if isinstance(parsed.get("cal_locked", False), str) else bool(parsed.get("cal_locked", False)),
                        "gps_valid": parsed.get("gps_valid", False),
                        "gps_lat": parsed.get("gps_lat", 0.0),
                        "gps_lon": parsed.get("gps_lon", 0.0),
                        "gps_sats": parsed.get("gps_sats", 0),
                        "last_update": datetime.now().isoformat()
                    })
                elif parsed.get("type") == "event":
                    event_status = parsed.get("status")
                    if event_status == "CALIBRATION_SAVED":
                        esp32_telemetry["cal_locked"] = True
                    elif event_status == "CALIBRATION_CLEARED":
                        esp32_telemetry["cal_locked"] = False
                elif parsed.get("status") == "ESP32_READY":
                    esp32_telemetry["status"] = "connected"
            except:
                pass
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        esp32_telemetry["status"] = "disconnected"

@app.post("/api/point-hilal")
async def point_hilal(target: TargetCoordinates):
    payload = {
        "command": "POINT_HILAL",
        "target_azimuth": target.target_azimuth,
        "target_altitude": target.target_altitude
    }
    # Ubah dictionary python menjadi JSON string dan kirim ke ESP32
    if len(manager.active_connections) == 0:
        return {
            "status": "warning",
            "message": "ESP32 belum terhubung ke Server! Periksa apakah ESP32 sudah menyala dan terhubung ke Wi-Fi.",
            "payload": payload
        }
    await manager.broadcast(json.dumps(payload))
    return {"status": "success", "message": "Command POINT_HILAL berhasil dikirim ke ESP32", "payload": payload}

@app.api_route("/api/set-home", methods=["GET", "POST"])
async def set_home():
    payload = {"command": "SET_HOME"}
    if len(manager.active_connections) == 0:
        return {
            "status": "warning",
            "message": "ESP32 belum terhubung ke Server! Pastikan ESP32 sudah online.",
            "payload": payload
        }
    await manager.broadcast(json.dumps(payload))
    return {"status": "success", "message": "Perintah SET_HOME (0° Ufuk & Utara) berhasil dikirim ke ESP32", "payload": payload}

@app.api_route("/api/save-calibration", methods=["GET", "POST"])
async def save_calibration():
    payload = {"command": "SAVE_CALIBRATION"}
    if len(manager.active_connections) == 0:
        return {
            "status": "warning",
            "message": "ESP32 belum terhubung ke Server! Pastikan ESP32 sudah online.",
            "payload": payload
        }
    await manager.broadcast(json.dumps(payload))
    esp32_telemetry["cal_locked"] = True
    return {"status": "success", "message": "Perintah SAVE_CALIBRATION berhasil dikirim ke ESP32", "payload": payload}

@app.api_route("/api/clear-calibration", methods=["GET", "POST"])
async def clear_calibration():
    payload = {"command": "CLEAR_CALIBRATION"}
    if len(manager.active_connections) == 0:
        return {
            "status": "warning",
            "message": "ESP32 belum terhubung ke Server! Pastikan ESP32 sudah online.",
            "payload": payload
        }
    await manager.broadcast(json.dumps(payload))
    esp32_telemetry["cal_locked"] = False
    return {"status": "success", "message": "Perintah CLEAR_CALIBRATION berhasil dikirim ke ESP32", "payload": payload}

@app.websocket("/ws")
async def websocket_alias(websocket: WebSocket):
    await websocket_esp32(websocket)

from fastapi.staticfiles import StaticFiles

class SafeStaticFiles(StaticFiles):
    async def __call__(self, scope, receive, send):
        if scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": 1000})
            return
        await super().__call__(scope, receive, send)

# Serve frontend statis untuk penggunaan lokal (di luar Vercel)
import os
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.exists(frontend_dir):
    app.mount("/", SafeStaticFiles(directory=frontend_dir, html=True), name="frontend")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("backend.main:app", host="0.0.0.0", port=port, reload=True)