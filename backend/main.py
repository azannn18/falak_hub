import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
from datetime import datetime, timezone
import socket
import subprocess
import urllib.request
import uvicorn
import json
from typing import List, Optional
from geopy.geocoders import Nominatim

from astronomy.engine import FalakCalculator
from ai.predictive_cache import PredictiveCache
from paths import get_data_dir, get_frontend_dir, is_frozen

app = FastAPI(title="HILTRON API", version="1.2.0")

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
    arcl_geocentric: Optional[float] = None
    arcl_topocentric: Optional[float] = None
    sunset_sun_az: Optional[float] = None
    sunset_sun_alt: Optional[float] = None
    sunset_moon_az: Optional[float] = None
    sunset_moon_alt: Optional[float] = None

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

_offline_cities_cache = None


def _load_offline_cities():
    global _offline_cities_cache
    if _offline_cities_cache is None:
        cities_file = get_data_dir() / "cities_offline.json"
        if cities_file.is_file():
            try:
                _offline_cities_cache = json.loads(cities_file.read_text(encoding="utf-8"))
            except Exception:
                _offline_cities_cache = []
        else:
            _offline_cities_cache = []
    return _offline_cities_cache


def _search_offline_cities(query: str):
    q = query.strip().lower()
    if not q:
        return None
    best = None
    best_score = -1
    for entry in _load_offline_cities():
        name_l = entry["name"].lower()
        aliases = [a.lower() for a in entry.get("aliases", [])]
        if name_l == q or q in aliases:
            score = 100
        elif name_l.startswith(q) or any(a.startswith(q) for a in aliases):
            score = 80
        elif q in name_l or any(q in a for a in aliases):
            score = 60
        else:
            continue
        if score > best_score:
            best_score = score
            best = entry
    if best:
        return {
            "name": best["name"],
            "lat": best["lat"],
            "lon": best["lon"],
            "source": "offline",
        }
    return None


@app.get("/api/search")
def search_location(q: str):
    """
    Search for a city/location and get its coordinates.
    Uses Nominatim when online, with seamless fallback to the bundled offline city database.
    """
    try:
        geolocator = Nominatim(user_agent="HILTRON_App")
        location = geolocator.geocode(q, timeout=3)
        if location:
            return {
                "name": location.address,
                "lat": location.latitude,
                "lon": location.longitude,
                "source": "nominatim",
            }
    except Exception:
        pass

    offline_match = _search_offline_cities(q)
    if offline_match:
        return offline_match

    raise HTTPException(status_code=404, detail="Location not found")

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        print("Perangkat terhubung ke WebSocket.")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        print("Perangkat terputus dari WebSocket.")

    async def broadcast(self, message: str):
        for connection in list(self.active_connections):
            try:
                await connection.send_text(message)
            except Exception as e:
                print(f"Error broadcasting to connection: {e}")

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
    "is_tracking": False,
    "last_update": None
}

@app.get("/api/health")
def health_check():
    return {"status": "ok", "version": "1.2.0"}


def _detect_lan_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("10.255.255.255", 1))
            return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"


@app.get("/api/system-info")
def get_system_info(request: Request):
    desktop_mode = bool(getattr(app.state, "desktop_mode", False))
    port = int(getattr(app.state, "hiltron_port", request.url.port or 8000))
    local_ip = _detect_lan_ip()
    return {
        "desktop_mode": desktop_mode,
        "local_ip": local_ip,
        "port": port,
        "ws_url": f"ws://{local_ip}:{port}/ws/esp32",
    }


def _get_windows_location() -> Optional[dict]:
    """Try Windows native GeoCoordinateWatcher without flashing a console window."""
    if os.name != "nt":
        return None
    ps_script = (
        "Add-Type -AssemblyName System.Device; "
        "$w = New-Object System.Device.Location.GeoCoordinateWatcher([System.Device.Location.GeoPositionAccuracy]::Default); "
        "$null = $w.TryStart($false, [TimeSpan]::FromMilliseconds(2500)); "
        "if ($w.Permission -ne 'Denied') { "
        "  $deadline = (Get-Date).AddMilliseconds(2500); "
        "  while ($w.Position.Location.IsUnknown -and (Get-Date) -lt $deadline) { Start-Sleep -Milliseconds 150 } "
        "} "
        "$loc = $w.Position.Location; "
        "if (-not $loc.IsUnknown) { "
        "  $ci = [System.Globalization.CultureInfo]::InvariantCulture; "
        "  Write-Output ($loc.Latitude.ToString($ci) + ',' + $loc.Longitude.ToString($ci) + ',' + $loc.HorizontalAccuracy.ToString($ci)) "
        "} "
        "$w.Dispose()"
    )
    try:
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        res = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=creation_flags,
        )
        line = (res.stdout or "").strip().splitlines()
        if not line:
            return None
        parts = line[-1].split(",")
        if len(parts) < 2:
            return None
        lat = float(parts[0])
        lon = float(parts[1])
        acc = float(parts[2]) if len(parts) > 2 and parts[2] != "NaN" else 500.0
        return {
            "lat": lat,
            "lon": lon,
            "accuracy_m": round(acc),
            "name": None,
            "source": "windows_location",
        }
    except Exception:
        return None


def _get_ip_location() -> Optional[dict]:
    """Fallback city-level location detection via public IP geolocation."""
    providers = ("https://ipwho.is/", "https://ipinfo.io/json")
    for url in providers:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "HILTRON/1.2"})
            with urllib.request.urlopen(req, timeout=4) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            if "ipwho.is" in url:
                if not data.get("success", False):
                    continue
                lat = float(data["latitude"])
                lon = float(data["longitude"])
                city = data.get("city")
                country = data.get("country")
            else:
                loc = data.get("loc", "")
                if "," not in loc:
                    continue
                lat_s, lon_s = loc.split(",", 1)
                lat, lon = float(lat_s), float(lon_s)
                city = data.get("city")
                country = data.get("country")
            name = ", ".join(p for p in (city, country) if p) or None
            return {
                "lat": lat,
                "lon": lon,
                "accuracy_m": 5000,
                "name": name,
                "source": "ip_geolocation",
            }
        except Exception:
            continue
    return None


@app.get("/api/device-location")
def get_device_location():
    """
    Desktop location fallback when WebView2 navigator.geolocation is blocked or unavailable.
    Tries Windows native GeoCoordinateWatcher first, then IP geolocation.
    """
    loc = _get_windows_location()
    if loc:
        return loc

    loc = _get_ip_location()
    if loc:
        return loc

    raise HTTPException(
        status_code=503,
        detail="Lokasi perangkat tidak tersedia (izin Lokasi Windows nonaktif dan tidak ada koneksi internet).",
    )

@app.get("/api/telemetry")
def get_telemetry():
    return esp32_telemetry

class TargetCoordinates(BaseModel):
    target_azimuth: float
    target_altitude: float

class LiveTrackingCoordinates(BaseModel):
    target_azimuth: float
    target_altitude: float
    tracking: bool = True

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
                    is_tr = parsed.get("is_tracking", False)
                    if isinstance(is_tr, str):
                        is_tr = (is_tr.lower() == "true")

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
                        "is_tracking": bool(is_tr),
                        "last_update": datetime.now().isoformat()
                    })
                elif parsed.get("type") == "event":
                    event_status = parsed.get("status")
                    if event_status == "CALIBRATION_SAVED":
                        esp32_telemetry["cal_locked"] = True
                    elif event_status == "CALIBRATION_CLEARED":
                        esp32_telemetry["cal_locked"] = False
                    elif event_status == "TRACKING_STARTED":
                        esp32_telemetry["is_tracking"] = True
                    elif event_status == "TRACKING_STOPPED":
                        esp32_telemetry["is_tracking"] = False
                elif parsed.get("status") == "ESP32_READY":
                    esp32_telemetry["status"] = "connected"
            except:
                pass
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        esp32_telemetry["status"] = "disconnected"
        esp32_telemetry["is_tracking"] = False

@app.post("/api/point-hilal")
async def point_hilal(target: TargetCoordinates):
    payload = {
        "command": "POINT_HILAL",
        "target_azimuth": target.target_azimuth,
        "target_altitude": target.target_altitude
    }
    if len(manager.active_connections) == 0:
        return {
            "status": "warning",
            "message": "ESP32 belum terhubung ke Server! Periksa apakah ESP32 sudah menyala dan terhubung ke Wi-Fi.",
            "payload": payload
        }
    await manager.broadcast(json.dumps(payload))
    return {"status": "success", "message": "Command POINT_HILAL berhasil dikirim ke ESP32", "payload": payload}

@app.post("/api/start-tracking")
async def start_tracking(target: LiveTrackingCoordinates):
    payload = {
        "command": "START_TRACKING",
        "target_azimuth": target.target_azimuth,
        "target_altitude": target.target_altitude,
        "tracking": True
    }
    esp32_telemetry["is_tracking"] = True
    if len(manager.active_connections) == 0:
        return {
            "status": "warning",
            "message": "ESP32 belum terhubung ke Server! Pastikan ESP32 sudah online.",
            "payload": payload
        }
    await manager.broadcast(json.dumps(payload))
    return {"status": "success", "message": "Command START_TRACKING berhasil dikirim ke ESP32", "payload": payload}

@app.post("/api/live-tracking")
async def live_tracking(target: LiveTrackingCoordinates):
    payload = {
        "command": "LIVE_TRACKING",
        "target_azimuth": target.target_azimuth,
        "target_altitude": target.target_altitude,
        "tracking": target.tracking
    }
    if len(manager.active_connections) == 0:
        return {
            "status": "warning",
            "message": "ESP32 belum terhubung ke Server!",
            "payload": payload
        }
    await manager.broadcast(json.dumps(payload))
    return {"status": "success", "message": "Command LIVE_TRACKING berhasil dikirim ke ESP32", "payload": payload}

@app.api_route("/api/stop-tracking", methods=["GET", "POST"])
async def stop_tracking():
    payload = {"command": "STOP_TRACKING"}
    esp32_telemetry["is_tracking"] = False
    if len(manager.active_connections) == 0:
        return {
            "status": "warning",
            "message": "ESP32 belum terhubung ke Server!",
            "payload": payload
        }
    await manager.broadcast(json.dumps(payload))
    return {"status": "success", "message": "Command STOP_TRACKING berhasil dikirim ke ESP32", "payload": payload}

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

    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        req_path = scope.get("path", "")
        if req_path == "/" or req_path.endswith((".html", ".js", ".css")):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
            response.headers["Pragma"] = "no-cache"
        return response

# Serve frontend statis untuk penggunaan lokal & desktop (di luar Vercel)
frontend_dir = str(get_frontend_dir())
if os.path.exists(frontend_dir):
    app.mount("/", SafeStaticFiles(directory=frontend_dir, html=True), name="frontend")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    if is_frozen():
        uvicorn.run(app, host="0.0.0.0", port=port, reload=False)
    else:
        uvicorn.run("backend.main:app", host="0.0.0.0", port=port, reload=True)
