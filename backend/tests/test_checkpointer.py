"""Tests for agents.checkpointer — ensure Postgres init failure raises.

Run with:
    cd backend
    PYTHONPATH=src pytest tests/test_checkpointer.py -v
"""
import os

import pytest

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://x:x@localhost/x")
os.environ.setdefault("REDIS_URL", "redis://localhost/0")

from chronocanvas.agents.checkpointer import CheckpointerInitError, init_checkpointer  # noqa: E402


@pytest.mark.asyncio
async def test_init_checkpointer_raises_on_failure():
    """init_checkpointer must raise CheckpointerInitError when Postgres is unreachable."""
    with pytest.raises(CheckpointerInitError):
        await init_checkpointer()
