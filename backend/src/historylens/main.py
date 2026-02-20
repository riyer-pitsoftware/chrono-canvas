import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from historylens.api.middleware import AuditLoggingMiddleware
from historylens.api.router import api_router
from historylens.api.websocket import generation_websocket
from historylens.config import settings
from historylens.redis_client import close_redis

logging.basicConfig(level=getattr(logging, settings.log_level))
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("HistoryLens starting up")
    # Ensure output directories exist
    import os
    os.makedirs(settings.output_dir, exist_ok=True)
    os.makedirs(settings.upload_dir, exist_ok=True)
    yield
    logger.info("HistoryLens shutting down")
    await close_redis()


def create_app() -> FastAPI:
    app = FastAPI(
        title="HistoryLens",
        description="Agentic historical education toolkit",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(AuditLoggingMiddleware)

    # API routes
    app.include_router(api_router)

    # WebSocket
    app.websocket("/ws/generation/{request_id}")(generation_websocket)

    # Static files for generated images and uploads
    app.mount("/output", StaticFiles(directory=settings.output_dir, check_dir=False), name="output")
    app.mount("/uploads", StaticFiles(directory=settings.upload_dir, check_dir=False), name="uploads")

    return app


app = create_app()
