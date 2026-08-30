import asyncio
import json
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import redis.asyncio as redis

router = APIRouter(tags=["WebSockets"])

REDIS_URL = "redis://localhost:6379"
redis_client = redis.from_url(REDIS_URL, encoding="utf-8", decode_responses=True)

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, room_id: str, websocket: WebSocket):
        await websocket.accept()
        if room_id not in self.active_connections:
            self.active_connections[room_id] = []
        self.active_connections[room_id].append(websocket)

    def disconnect(self, room_id: str, websocket: WebSocket):
        if room_id in self.active_connections:
            if websocket in self.active_connections[room_id]:
                self.active_connections[room_id].remove(websocket)
            if not self.active_connections[room_id]:
                del self.active_connections[room_id]

    async def broadcast_local(self, room_id: str, message: dict):
        if room_id in self.active_connections:
            disconnected = []
            for connection in self.active_connections[room_id]:
                try:
                    await connection.send_text(json.dumps(message))
                except Exception:
                    disconnected.append(connection)
            for dead in disconnected:
                self.disconnect(room_id, dead)

manager = ConnectionManager()

async def redis_listener(room_id: str, pubsub):
    """Background task listening to Redis Pub/Sub channels."""
    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                data = json.loads(message["data"])
                await manager.broadcast_local(room_id, data)
    except asyncio.CancelledError:
        pass
    except Exception:
        pass

@router.websocket("/ws/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str):
    await manager.connect(room_id, websocket)
    
    pubsub = None
    listener_task = None
    redis_available = True

    try:
        pubsub = redis_client.pubsub()
        await pubsub.subscribe(room_id)
        listener_task = asyncio.create_task(redis_listener(room_id, pubsub))
    except Exception:
        redis_available = False

    try:
        while True:
            data = await websocket.receive_text()
            message_payload = {"sender": id(websocket), "content": data}
            
            if redis_available:
                try:
                    await redis_client.publish(room_id, json.dumps(message_payload))
                except Exception:
                    redis_available = False
                    await manager.broadcast_local(room_id, message_payload)
            else:
                await manager.broadcast_local(room_id, message_payload)
            
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(room_id, websocket)
        
        if listener_task:
            listener_task.cancel()
            try:
                await listener_task
            except asyncio.CancelledError:
                pass

        if pubsub:
            try:
                await pubsub.unsubscribe(room_id)
            except Exception:
                pass
            try:
                await pubsub.close()
            except Exception:
                pass