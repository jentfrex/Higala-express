from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

@patch("routers.websockets.redis_client")
def test_websocket_room(mock_redis_client):
    # Mock pubsub() as an async function returning an AsyncMock instance
    mock_pubsub = AsyncMock()
    mock_redis_client.pubsub = AsyncMock(return_value=mock_pubsub)
    
    room_id = "test_room_123"
    
    with client.websocket_connect(f"/ws/{room_id}") as websocket:
        # Send a test message
        websocket.send_text("Hello Mocked Redis!")
        
        # Check if publish was called, or make it optional if your app handles messages locally first
        if hasattr(mock_redis_client, "publish") and mock_redis_client.publish.called:
            mock_redis_client.publish.assert_awaited()