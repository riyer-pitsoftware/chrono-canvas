"""Tests for agents.checkpointer — ensure Postgres init failure falls back gracefully.

Run with:
    cd backend
    PYTHONPATH=src pytest tests/test_checkpointer.py -v
"""
import logging
import os

import pytest

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://x:x@localhost/x")
os.environ.setdefault("REDIS_URL", "redis://localhost/0")

from chronocanvas.agents.checkpointer import init_checkpointer  # noqa: E402


@pytest.mark.asyncio
async def test_init_checkpointer_warns_on_failure(caplog):
    """init_checkpointer must warn and fall back when Postgres is unreachable."""
    with caplog.at_level(logging.WARNING):
        await init_checkpointer()
    assert "Failed to initialise Postgres checkpointer" in caplog.text
    assert "falling back to MemorySaver" in caplog.text
