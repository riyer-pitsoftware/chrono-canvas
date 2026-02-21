import asyncio
import os
import tempfile
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Use SQLite and a real (but isolated) Redis DB index for tests.
# OUTPUT_DIR / UPLOAD_DIR are set to auto-cleaned temp dirs by the
# `test_dirs` session fixture below; we set them here too so that
# module-level imports that read settings at import time get a value,
# but the fixture will override them before any test runs.
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///test.db"
os.environ["REDIS_URL"] = "redis://localhost:6379/1"
os.environ["IMAGE_PROVIDER"] = "mock"
os.environ["OUTPUT_DIR"] = tempfile.mkdtemp(prefix="cc_test_output_")
os.environ["UPLOAD_DIR"] = tempfile.mkdtemp(prefix="cc_test_uploads_")

from chronocanvas.db.base import Base
from chronocanvas.db.models import *  # noqa


@pytest.fixture(scope="session", autouse=True)
def test_dirs():
    """Create isolated temp directories for OUTPUT_DIR and UPLOAD_DIR and
    clean them up automatically when the session ends."""
    import shutil
    from chronocanvas.config import settings

    output_dir = tempfile.mkdtemp(prefix="cc_test_output_")
    upload_dir = tempfile.mkdtemp(prefix="cc_test_uploads_")
    # Also create the faces sub-directory the upload handler expects
    Path(upload_dir, "faces").mkdir(parents=True, exist_ok=True)

    os.environ["OUTPUT_DIR"] = output_dir
    os.environ["UPLOAD_DIR"] = upload_dir
    settings.output_dir = output_dir
    settings.upload_dir = upload_dir

    yield output_dir, upload_dir

    shutil.rmtree(output_dir, ignore_errors=True)
    shutil.rmtree(upload_dir, ignore_errors=True)

    # Also clean up the dirs that were created at import time before the
    # fixture ran (they may be empty; ignore errors if they're already gone)
    for key in ("OUTPUT_DIR", "UPLOAD_DIR"):
        old = os.environ.get(key, "")
        if old and old not in (output_dir, upload_dir):
            shutil.rmtree(old, ignore_errors=True)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    session_factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
