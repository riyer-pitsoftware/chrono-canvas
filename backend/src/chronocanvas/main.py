import logging
from contextlib import asynccontextmanager

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from chronocanvas.agents.checkpointer import close_checkpointer, init_checkpointer
from chronocanvas.agents.graph import recompile_graph
from chronocanvas.api.middleware import AuditLoggingMiddleware, AuthGateMiddleware
from chronocanvas.api.router import api_router
from chronocanvas.api.websocket import generation_websocket
from chronocanvas.config import settings
from chronocanvas.llm.router import GeminiUnavailableError
from chronocanvas.logging_config import setup_logging
from chronocanvas.redis_client import close_redis
from chronocanvas.service_registry import init_registry

setup_logging()
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

    # Connect to Redis with retry (Cloud SQL proxy / VPC may need a moment)
    import asyncio

    for attempt in range(5):
        try:
            app.state.arq_pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
            break
        except Exception as e:
            if attempt == 4:
                logger.error("Redis connection failed after 5 attempts: %s", e)
                raise
            logger.warning("Redis not ready (attempt %d/5): %s", attempt + 1, e)
            await asyncio.sleep(2)

    init_registry()

    try:
        await init_checkpointer()
    except Exception as e:
        logger.warning("Checkpointer init failed (falling back to memory): %s", e)

    recompile_graph()
    if settings.hackathon_mode:
        from chronocanvas.api.routes.health import validate_hackathon_requirements

        failures = validate_hackathon_requirements()
        for f in failures:
            logger.error("HACKATHON PREFLIGHT FAIL: %s", f)
        if failures:
            logger.error(
                "Hackathon mode is ON but critical services"
                " are misconfigured. Fix the above issues."
            )
    yield
    logger.info("ChronoCanvas shutting down")
    await close_checkpointer()
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
    app.add_middleware(AuthGateMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)

    # Exception handlers
    @app.exception_handler(GeminiUnavailableError)
    async def gemini_unavailable_handler(request: Request, exc: GeminiUnavailableError):
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    # API routes
    app.include_router(api_router)

    # WebSocket
    app.websocket("/ws/generation/{request_id}")(generation_websocket)

    # Static files for generated images and uploads (dirs created in lifespan)
    # On Cloud Run, /output/ paths proxy from GCS; locally, serve from disk
    from chronocanvas.services.storage import get_storage_backend

    storage = get_storage_backend()
    logger.info("Storage backend: %s (is_cloud=%s)", type(storage).__name__, storage.is_cloud())
    if storage.is_cloud():
        from fastapi.responses import Response

        @app.get("/output/{file_path:path}")
        async def serve_output_via_gcs(file_path: str):
            """Proxy GCS blob content — avoids signed URL auth issues on Cloud Run."""
            from pathlib import Path

            data = await storage.download(file_path)
            if data is None:
                logger.warning("GCS blob not found: %s", file_path)
                return Response(status_code=404, content="Not found")
            suffix = Path(file_path).suffix.lower()
            content_types = {
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".wav": "audio/wav",
                ".mp4": "video/mp4",
                ".json": "application/json",
            }
            ct = content_types.get(suffix, "application/octet-stream")
            return Response(
                content=data,
                media_type=ct,
                headers={
                    "Cache-Control": "public, max-age=3600",
                },
            )
    else:
        app.mount("/output", StaticFiles(directory=settings.output_dir), name="output")
    app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")

    # Eval run assets (images, etc.) — only mount if eval/runs exists
    import os

    eval_runs_dir = os.path.join(settings.eval_dir, "runs")
    if os.path.isdir(eval_runs_dir):
        app.mount("/eval-assets", StaticFiles(directory=eval_runs_dir), name="eval-assets")

    return app


app = create_app()
