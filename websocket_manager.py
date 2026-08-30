from typing import Dict, List, Union
from fastapi import WebSocket
import json

class ConnectionManager:
    def __init__(self):
        # Map channel/order/ride identifier (int or str) to a list of active websocket connections
        self.active_connections: Dict[Union[int, str], List[WebSocket]] = {}

    async def connect(self, channel_id: Union[int, str], websocket: WebSocket):
        """Accepts and registers a new WebSocket connection to a specific channel/order/ride."""
        await websocket.accept()
        if channel_id not in self.active_connections:
            self.active_connections[channel_id] = []
        if websocket not in self.active_connections[channel_id]:
            self.active_connections[channel_id].append(websocket)

    def disconnect(self, channel_id: Union[int, str], websocket: WebSocket):
        """Removes a WebSocket connection from the active channel pool."""
        if channel_id in self.active_connections:
            if websocket in self.active_connections[channel_id]:
                self.active_connections[channel_id].remove(websocket)
            if not self.active_connections[channel_id]:
                del self.active_connections[channel_id]

    async def broadcast_to_order(self, order_id: Union[int, str], data: dict):
        """Broadcasts JSON data to all connections listening to a specific order."""
        if order_id in self.active_connections:
            for connection in self.active_connections[order_id]:
                await connection.send_json(data)

    async def broadcast_telemetry(self, channel_id: Union[int, str], data: dict):
        """Streams real-time GPS coordinates and driver status updates to tracking clients."""
        if channel_id in self.active_connections:
            for connection in self.active_connections[channel_id]:
                await connection.send_text(json.dumps(data))

manager = ConnectionManager()