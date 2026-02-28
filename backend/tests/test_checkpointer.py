"""Tests for agents.checkpointer — ensure Postgres init failure is fatal.

Run with:
    cd backend
    PYTHONPATH=src pytest tests/test_checkpointer.py -v
"""
import os

import pytest

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://x:x@localhost/x")
os.environ.setdefault("REDIS_URL", "redis://localhost/0")

from chronocanvas.agents.checkpointer import (  # noqa: E402
    CheckpointerInitError,
    init_checkpointer,
)


@pytest.mark.asyncio
async def test_init_checkpointer_raises_on_failure():
    """init_checkpointer must raise CheckpointerInitError when Postgres is unreachable."""
    with pytest.raises(CheckpointerInitError, match="Failed to initialise Postgres checkpointer"):
        await init_checkpointer()


@pytest.mark.asyncio
async def test_init_checkpointer_error_chains_cause():
    """The raised error should chain the original exception as __cause__."""
    with pytest.raises(CheckpointerInitError) as exc_info:
        await init_checkpointer()
    assert exc_info.value.__cause__ is not None
