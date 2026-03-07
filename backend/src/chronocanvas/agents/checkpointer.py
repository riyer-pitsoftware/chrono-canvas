"""LangGraph checkpointer — durable Postgres storage.

In production the checkpointer is backed by PostgreSQL via
``langgraph-checkpoint-postgres``.  It is initialised asynchronously during
application startup (see :func:`init_checkpointer`) and torn down on
shutdown (see :func:`close_checkpointer`).

At import time the module uses ``MemorySaver`` so the graph can be compiled
without a live database connection, but ``init_checkpointer`` **must**
succeed before any pipeline runs — it raises on failure to prevent silent
data loss from in-memory fallback.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver

if TYPE_CHECKING:
    from psycopg import AsyncConnection

logger = logging.getLogger(__name__)

# Module-level checkpointer; starts as MemorySaver and is replaced by
# AsyncPostgresSaver when ``init_checkpointer`` is called during startup.
checkpointer: BaseCheckpointSaver = MemorySaver()

# Hold a reference to the psycopg connection so it can be closed cleanly.
_pg_conn: AsyncConnection | None = None


class CheckpointerInitError(RuntimeError):
    """Raised when the durable Postgres checkpointer fails to initialise."""


def _pg_conninfo() -> str:
    """Derive a psycopg-compatible connection string from the SQLAlchemy URL.

    The project's ``database_url`` uses the ``postgresql+asyncpg://`` scheme
    required by SQLAlchemy, but ``langgraph-checkpoint-postgres`` needs a plain
    ``postgresql://`` (libpq) URI understood by psycopg3.
    """
    from chronocanvas.config import settings

    url = settings.database_url
    # Strip the SQLAlchemy dialect prefix
    for prefix in ("postgresql+asyncpg://", "postgres+asyncpg://"):
        if url.startswith(prefix):
            return "postgresql://" + url[len(prefix):]
    # Already a plain psycopg URL
    return url


async def init_checkpointer() -> None:
    """Create the durable Postgres checkpointer and run schema migrations.

    Call this once during application startup (lifespan or worker init).
    After this call, :data:`checkpointer` is an ``AsyncPostgresSaver`` backed
    by PostgreSQL and will survive process restarts.

    Raises :class:`CheckpointerInitError` if the Postgres connection or
    schema setup fails, preventing the app from starting with a silent
    in-memory fallback that would lose pipeline state on restart.
    """
    global checkpointer, _pg_conn

    try:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        from psycopg import AsyncConnection as PsycopgAsyncConnection

        conninfo = _pg_conninfo()
        conn = await PsycopgAsyncConnection.connect(
            conninfo,
            autocommit=True,
        )
        saver = AsyncPostgresSaver(conn)
        await saver.setup()

        _pg_conn = conn
        checkpointer = saver
        logger.info("Durable Postgres checkpointer initialised")
    except Exception as exc:
        raise CheckpointerInitError(
            f"Failed to initialise Postgres checkpointer: {exc}"
        ) from exc


async def close_checkpointer() -> None:
    """Close the psycopg connection backing the checkpointer."""
    global _pg_conn
    if _pg_conn is not None:
        await _pg_conn.close()
        _pg_conn = None
        logger.info("Postgres checkpointer connection closed")
