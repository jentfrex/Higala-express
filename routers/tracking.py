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
async def order_tracking_websocket(
    websocket: WebSocket, 
    order_id: int, 
    token: str = None,
    db: Session = Depends(get_db)
):
    if not token:
        await websocket.close(code=4001, reason="Authentication required")
        return
    try:
        from jose import jwt
        from config import settings
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username = payload.get("sub")
        current_user = db.query(models.User).filter(models.User.username == username).first()
        if not current_user:
            await websocket.close(code=4001, reason="Invalid token")
            return
    except Exception:
        await websocket.close(code=4001, reason="Authentication failed")
        return