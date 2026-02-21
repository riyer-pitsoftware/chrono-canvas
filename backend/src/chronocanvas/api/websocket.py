import asyncio
import json
import logging

from fastapi import WebSocket, WebSocketDisconnect

from chronocanvas.redis_client import subscribe

logger = logging.getLogger(__name__)

# Maximum seconds to wait for a single send() before treating the client as
# too slow to keep alive.  Prevents a stalled receiver from blocking the relay.
_SEND_TIMEOUT_S = 5.0

# Interval between server-sent pings that keep proxies and browsers from
# closing idle connections.
_PING_INTERVAL_S = 20.0

# If the generation backend stops publishing for this many seconds the
# connection is closed rather than leaking an open WebSocket indefinitely.
# A completed/failed message from Redis will always close the connection first.
_IDLE_TIMEOUT_S = 300.0


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
        """Send *data* to all sockets watching *request_id*.

        Backpressure strategy: each send is bounded by ``_SEND_TIMEOUT_S``.
        Sockets that cannot accept a message within that window are disconnected
        rather than buffered indefinitely to avoid memory growth.
        """
        if request_id not in self.active_connections:
            return
        for ws in list(self.active_connections[request_id]):
            try:
                await asyncio.wait_for(ws.send_json(data), timeout=_SEND_TIMEOUT_S)
            except asyncio.TimeoutError:
                logger.warning(
                    "send_json timed out for request_id=%s; disconnecting slow client",
                    request_id,
                )
                self.disconnect(ws, request_id)
            except Exception as exc:
                logger.warning(
                    "send_json failed for request_id=%s: %s", request_id, exc
                )


manager = ConnectionManager()


async def generation_websocket(websocket: WebSocket, request_id: str):
    """Relay Redis pub/sub progress messages to a WebSocket client.

    Lifecycle guarantees
    --------------------
    * The Redis pub/sub subscription is explicitly unsubscribed and closed in
      the ``finally`` block regardless of how the connection ends.
    * Background tasks (Redis relay, heartbeat) are cancelled *and awaited* in
      ``finally`` so no coroutine leaks after the handler returns.
    * The connection is closed automatically when the generation reports
      ``completed`` or ``failed``, when the client disconnects, when a send
      times out (slow client), or when ``_IDLE_TIMEOUT_S`` elapses with no
      progress event from the backend.

    Backpressure
    ------------
    Each ``send_json`` call is wrapped in ``asyncio.wait_for(_SEND_TIMEOUT_S)``.
    Clients that cannot drain their receive buffer fast enough are disconnected
    (drop strategy) rather than causing unbounded server-side buffering.
    """
    await manager.connect(websocket, request_id)
    channel = f"generation:{request_id}"
    pubsub = None
    redis_task: asyncio.Task | None = None
    heartbeat_task: asyncio.Task | None = None
    recv_task: asyncio.Task | None = None

    try:
        pubsub = await subscribe(channel)

        async def listen_redis() -> None:
            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue
                try:
                    data = json.loads(message["data"])
                except (json.JSONDecodeError, KeyError) as exc:
                    logger.warning(
                        "Malformed Redis message on channel=%s: %s", channel, exc
                    )
                    continue
                try:
                    await asyncio.wait_for(
                        websocket.send_json(data), timeout=_SEND_TIMEOUT_S
                    )
                except asyncio.TimeoutError:
                    logger.warning(
                        "WS send timed out for request_id=%s; closing connection",
                        request_id,
                    )
                    return
                except Exception as exc:
                    logger.warning(
                        "WS send failed for request_id=%s: %s", request_id, exc
                    )
                    return
                if data.get("status") in ("completed", "failed"):
                    return

        async def send_heartbeats() -> None:
            elapsed = 0.0
            while elapsed < _IDLE_TIMEOUT_S:
                await asyncio.sleep(_PING_INTERVAL_S)
                elapsed += _PING_INTERVAL_S
                try:
                    await asyncio.wait_for(
                        websocket.send_json({"type": "ping"}), timeout=_SEND_TIMEOUT_S
                    )
                except Exception:
                    return  # client gone; cleanup happens in finally
            logger.info(
                "Idle timeout (%ss) reached for request_id=%s; closing WebSocket",
                _IDLE_TIMEOUT_S, request_id,
            )

        async def recv_loop() -> None:
            try:
                while True:
                    await websocket.receive_text()
            except WebSocketDisconnect:
                pass

        redis_task = asyncio.create_task(listen_redis(), name=f"ws-redis-{request_id}")
        heartbeat_task = asyncio.create_task(
            send_heartbeats(), name=f"ws-hb-{request_id}"
        )
        recv_task = asyncio.create_task(recv_loop(), name=f"ws-recv-{request_id}")

        # Block until any of: generation done, idle timeout, client disconnect
        await asyncio.wait(
            {redis_task, heartbeat_task, recv_task},
            return_when=asyncio.FIRST_COMPLETED,
        )

    except Exception as e:
        logger.error("WebSocket error for request_id=%s: %s", request_id, e)
    finally:
        # Cancel and drain every background task so nothing leaks.
        for task in filter(None, [redis_task, heartbeat_task, recv_task]):
            if not task.done():
                task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass

        # Explicitly unsubscribe and close the Redis pub/sub handle.
        if pubsub is not None:
            try:
                await pubsub.unsubscribe(channel)
                await pubsub.aclose()
            except Exception as exc:
                logger.debug(
                    "pubsub cleanup error for channel=%s: %s", channel, exc
                )

        manager.disconnect(websocket, request_id)
