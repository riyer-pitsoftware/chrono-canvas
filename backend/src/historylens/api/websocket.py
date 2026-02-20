import asyncio
import json
import logging

from fastapi import WebSocket, WebSocketDisconnect

from historylens.redis_client import subscribe

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, request_id: str):
        await websocket.accept()
        if request_id not in self.active_connections:
            self.active_connections[request_id] = []
        self.active_connections[request_id].append(websocket)

    def disconnect(self, websocket: WebSocket, request_id: str):
        if request_id in self.active_connections:
            self.active_connections[request_id] = [
                ws for ws in self.active_connections[request_id] if ws != websocket
            ]
            if not self.active_connections[request_id]:
                del self.active_connections[request_id]

    async def send_to_request(self, request_id: str, data: dict):
        if request_id in self.active_connections:
            for ws in self.active_connections[request_id]:
                try:
                    await ws.send_json(data)
                except Exception:
                    pass


manager = ConnectionManager()


async def generation_websocket(websocket: WebSocket, request_id: str):
    await manager.connect(websocket, request_id)
    channel = f"generation:{request_id}"

    try:
        pubsub = await subscribe(channel)

        async def listen_redis():
            async for message in pubsub.listen():
                if message["type"] == "message":
                    data = json.loads(message["data"])
                    await websocket.send_json(data)
                    if data.get("status") in ("completed", "failed"):
                        break

        redis_task = asyncio.create_task(listen_redis())

        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            redis_task.cancel()
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        manager.disconnect(websocket, request_id)
