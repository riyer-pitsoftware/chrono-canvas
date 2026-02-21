"""Tests for WebSocket lifecycle hardening.

Covers: pubsub cleanup, task cancellation, send-failure logging,
heartbeat delivery, and connection teardown paths.
"""
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

from chronocanvas.api.websocket import (
    ConnectionManager,
    _PING_INTERVAL_S,
    _SEND_TIMEOUT_S,
    generation_websocket,
)


# ---------------------------------------------------------------------------
# ConnectionManager unit tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_connect_and_disconnect():
    mgr = ConnectionManager()
    ws = MagicMock()
    ws.accept = AsyncMock()

    await mgr.connect(ws, "req-1")
    assert ws in mgr.active_connections["req-1"]

    mgr.disconnect(ws, "req-1")
    assert "req-1" not in mgr.active_connections


@pytest.mark.asyncio
async def test_send_to_request_logs_timeout(caplog):
    import logging
    mgr = ConnectionManager()
    ws = MagicMock()
    ws.accept = AsyncMock()

    async def slow_send(_):
        await asyncio.sleep(10)

    ws.send_json = slow_send
    await mgr.connect(ws, "req-2")

    with patch("chronocanvas.api.websocket._SEND_TIMEOUT_S", 0.01):
        with caplog.at_level(logging.WARNING, logger="chronocanvas.api.websocket"):
            await mgr.send_to_request("req-2", {"status": "running"})

    assert "timed out" in caplog.text
    # Slow client should have been disconnected
    assert "req-2" not in mgr.active_connections


@pytest.mark.asyncio
async def test_send_to_request_logs_exception(caplog):
    import logging
    mgr = ConnectionManager()
    ws = MagicMock()
    ws.accept = AsyncMock()
    ws.send_json = AsyncMock(side_effect=RuntimeError("connection reset"))
    await mgr.connect(ws, "req-3")

    with caplog.at_level(logging.WARNING, logger="chronocanvas.api.websocket"):
        await mgr.send_to_request("req-3", {"status": "running"})

    assert "send_json failed" in caplog.text
    assert "connection reset" in caplog.text


# ---------------------------------------------------------------------------
# generation_websocket lifecycle tests
# ---------------------------------------------------------------------------

def _make_pubsub(messages):
    """Return a mock pubsub that yields *messages* then blocks."""
    async def _listen():
        for msg in messages:
            yield msg
        # Block indefinitely to simulate waiting for more messages
        await asyncio.sleep(9999)

    pubsub = MagicMock()
    pubsub.listen = _listen
    pubsub.unsubscribe = AsyncMock()
    pubsub.aclose = AsyncMock()
    return pubsub


def _make_websocket(messages=None):
    """Return a mock WebSocket that accepts, yields receive_text items, then disconnects."""
    from fastapi import WebSocketDisconnect

    ws = MagicMock()
    ws.accept = AsyncMock()
    ws.send_json = AsyncMock()

    call_count = {"n": 0}
    items = list(messages or [])

    async def receive_text():
        if call_count["n"] < len(items):
            val = items[call_count["n"]]
            call_count["n"] += 1
            return val
        raise WebSocketDisconnect()

    ws.receive_text = receive_text
    return ws


@pytest.mark.asyncio
async def test_pubsub_unsubscribed_on_disconnect():
    """pubsub.unsubscribe + aclose must be called when the client disconnects."""
    ws = _make_websocket()  # immediately disconnects
    pubsub = _make_pubsub([])

    with patch("chronocanvas.api.websocket.subscribe", return_value=pubsub):
        await generation_websocket(ws, "req-10")

    pubsub.unsubscribe.assert_awaited_once_with("generation:req-10")
    pubsub.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_connection_closes_on_completed_message():
    """Connection should close cleanly after receiving a 'completed' status."""
    ws = _make_websocket()  # disconnects immediately after redis task finishes
    messages = [
        {"type": "message", "data": json.dumps({"status": "completed", "agent": "export"})},
    ]
    pubsub = _make_pubsub(messages)

    with patch("chronocanvas.api.websocket.subscribe", return_value=pubsub):
        await generation_websocket(ws, "req-11")

    # The completed message should have been sent to the client
    ws.send_json.assert_any_call({"status": "completed", "agent": "export"})
    # Cleanup must have run
    pubsub.unsubscribe.assert_awaited_once()
    pubsub.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_send_failure_closes_relay(caplog):
    """A send failure during the Redis relay should log and close the connection."""
    import logging
    ws = _make_websocket()
    ws.send_json = AsyncMock(side_effect=RuntimeError("broken pipe"))

    messages = [
        {"type": "message", "data": json.dumps({"status": "running", "agent": "extraction"})},
    ]
    pubsub = _make_pubsub(messages)

    with patch("chronocanvas.api.websocket.subscribe", return_value=pubsub):
        with caplog.at_level(logging.WARNING, logger="chronocanvas.api.websocket"):
            await generation_websocket(ws, "req-12")

    assert "WS send failed" in caplog.text
    pubsub.unsubscribe.assert_awaited_once()


@pytest.mark.asyncio
async def test_heartbeat_ping_is_sent():
    """A ping message should be sent after _PING_INTERVAL_S seconds."""
    from fastapi import WebSocketDisconnect

    ping_sent = asyncio.Event()
    original_send = None

    ws = MagicMock()
    ws.accept = AsyncMock()

    async def send_json(data):
        if data.get("type") == "ping":
            ping_sent.set()
        if original_send:
            pass  # just track it

    ws.send_json = send_json

    disconnect_after = asyncio.Event()

    async def receive_text():
        await disconnect_after.wait()
        raise WebSocketDisconnect()

    ws.receive_text = receive_text

    pubsub = _make_pubsub([])  # no messages

    async def run():
        with patch("chronocanvas.api.websocket.subscribe", return_value=pubsub):
            with patch("chronocanvas.api.websocket._PING_INTERVAL_S", 0.05):
                await generation_websocket(ws, "req-13")

    task = asyncio.create_task(run())

    # Wait for ping to be sent, then disconnect client
    await asyncio.wait_for(ping_sent.wait(), timeout=2.0)
    disconnect_after.set()
    await asyncio.wait_for(task, timeout=2.0)

    assert ping_sent.is_set()
    pubsub.unsubscribe.assert_awaited_once()


@pytest.mark.asyncio
async def test_malformed_redis_message_is_skipped(caplog):
    """Malformed JSON from Redis should be logged and skipped, not crash the relay."""
    import logging
    from fastapi import WebSocketDisconnect

    ws = _make_websocket()
    ws.send_json = AsyncMock()

    messages = [
        {"type": "message", "data": "not-valid-json"},
        {"type": "message", "data": json.dumps({"status": "completed"})},
    ]
    pubsub = _make_pubsub(messages)

    with patch("chronocanvas.api.websocket.subscribe", return_value=pubsub):
        with caplog.at_level(logging.WARNING, logger="chronocanvas.api.websocket"):
            await generation_websocket(ws, "req-14")

    assert "Malformed" in caplog.text
    # The completed message should still have been delivered
    ws.send_json.assert_any_call({"status": "completed"})
