from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session
from typing import Dict, List
import asyncio
import models
from database import get_db

router = APIRouter(prefix="/tracking/ws", tags=["Real-Time Tracking"])

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, List[WebSocket]] = {}

    async def connect(self, order_id: int, websocket: WebSocket):
        await websocket.accept()
        if order_id not in self.active_connections:
            self.active_connections[order_id] = []
        self.active_connections[order_id].append(websocket)

    def disconnect(self, order_id: int, websocket: WebSocket):
        if order_id in self.active_connections:
            if websocket in self.active_connections[order_id]:
                self.active_connections[order_id].remove(websocket)
            if not self.active_connections[order_id]:
                del self.active_connections[order_id]

    async def broadcast_to_order(self, order_id: int, data: dict):
        if order_id in self.active_connections:
            for connection in self.active_connections[order_id]:
                await connection.send_json(data)

manager = ConnectionManager()

@router.websocket("/{order_id}")
async def order_tracking_websocket(websocket: WebSocket, order_id: int, db: Session = Depends(get_db)):
    """WebSocket endpoint for drivers to stream location and clients to watch live."""
    await manager.connect(order_id, websocket)
    try:
        while True:
            try:
                # Use a small timeout so the loop never permanently hangs if a client stops sending
                data = await asyncio.wait_for(websocket.receive_json(), timeout=5.0)
            except asyncio.TimeoutError:
                # Send a ping/heartbeat check or continue waiting
                continue

            lat = data.get("lat")
            lng = data.get("lng")
            status_val = data.get("status")

            if lat is not None and lng is not None:
                order = db.query(models.Order.id).filter(models.Order.id == order_id).first()
                if order:
                    await manager.broadcast_to_order(order_id, {
                        "lat": lat,
                        "lng": lng,
                        "status": status_val
                    })
    except WebSocketDisconnect:
        manager.disconnect(order_id, websocket)
    except Exception:
        manager.disconnect(order_id, websocket)
    finally:
        manager.disconnect(order_id, websocket)