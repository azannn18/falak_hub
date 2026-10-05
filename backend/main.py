from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json
from typing import List

app = FastAPI()

# Tambahkan CORS middleware agar Frontend bisa memanggil API tanpa kendala CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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