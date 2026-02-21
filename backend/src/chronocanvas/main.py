import logging
from contextlib import asynccontextmanager

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from chronocanvas.api.middleware import AuditLoggingMiddleware
from chronocanvas.api.router import api_router
from chronocanvas.api.websocket import generation_websocket
from chronocanvas.config import settings
from chronocanvas.redis_client import close_redis

logging.basicConfig(level=getattr(logging, settings.log_level))
logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-XSS-Protection"] = "0"  # modern browsers use CSP instead
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("ChronoCanvas starting up")
    # Ensure output directories exist
    import os
    os.makedirs(settings.output_dir, exist_ok=True)
    os.makedirs(settings.upload_dir, exist_ok=True)
    app.state.arq_pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    yield
    logger.info("ChronoCanvas shutting down")
    await app.state.arq_pool.close()
    await close_redis()


def create_app() -> FastAPI:
    app = FastAPI(
        title="ChronoCanvas",
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
    app.add_middleware(SecurityHeadersMiddleware)

    # API routes
    app.include_router(api_router)

    # WebSocket
    app.websocket("/ws/generation/{request_id}")(generation_websocket)

    # Static files for generated images and uploads (dirs created in lifespan)
    app.mount("/output", StaticFiles(directory=settings.output_dir), name="output")
    app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")

    return app


app = create_app()
