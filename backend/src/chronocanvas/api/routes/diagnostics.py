"""Remote diagnostics endpoints for GCP Cloud Run debugging.

Auth-gated behind ADMIN_API_KEY. Provides:
- Recent failure inspection with structured error details
- Imagen-specific error analysis
- Deep health checks (live Imagen probe, DB ping, Redis queue depth)
- Retry failed requests
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from chronocanvas.config import settings
from chronocanvas.db.engine import get_session
from chronocanvas.db.models.request import GenerationRequest, RequestStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/diag", tags=["diagnostics"])


async def _require_admin_key(
    x_admin_key: str | None = Header(None, alias="X-Admin-Key"),
) -> None:
    """Verify admin API key. Rejects if key is unset or mismatched."""
    if not settings.admin_api_key:
        raise HTTPException(status_code=503, detail="Admin API key not configured on server")
    if x_admin_key != settings.admin_api_key:
        raise HTTPException(status_code=403, detail="Invalid admin key")


# ── Recent failures ─────────────────────────────────────────────────────────


@router.get("/failures", dependencies=[Depends(_require_admin_key)])
async def get_recent_failures(
    limit: int = Query(default=20, ge=1, le=100),
    hours: int = Query(default=24, ge=1, le=168),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Return recent failed generation requests with full error context."""
    from datetime import timedelta

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    stmt = (
        select(GenerationRequest)
        .where(
            GenerationRequest.status == RequestStatus.FAILED,
            GenerationRequest.updated_at >= cutoff,
        )
        .order_by(GenerationRequest.updated_at.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    failures = list(result.scalars().all())

    items = []
    for req in failures:
        # Extract imagen-specific error details from agent_trace if available
        imagen_error = _extract_imagen_error(req)
        items.append(
            {
                "id": str(req.id),
                "input_text": req.input_text[:100],
                "run_type": req.run_type or "portrait",
                "status": req.status,
                "current_agent": req.current_agent,
                "error_message": req.error_message,
                "imagen_error": imagen_error,
                "llm_calls_count": len(req.llm_calls or []),
                "llm_costs": req.llm_costs,
                "created_at": req.created_at.isoformat() if req.created_at else None,
                "updated_at": req.updated_at.isoformat() if req.updated_at else None,
            }
        )

    # Summary stats
    error_categories: dict[str, int] = {}
    for item in items:
        if item["imagen_error"]:
            cat = item["imagen_error"].get("category", "unknown")
        elif item["error_message"]:
            cat = _guess_error_category(item["error_message"])
        else:
            cat = "unknown"
        error_categories[cat] = error_categories.get(cat, 0) + 1

    return {
        "total_failures": len(items),
        "time_window_hours": hours,
        "error_summary": error_categories,
        "failures": items,
    }


# ── Imagen-specific errors ──────────────────────────────────────────────────


@router.get("/imagen-errors", dependencies=[Depends(_require_admin_key)])
async def get_imagen_errors(
    limit: int = Query(default=20, ge=1, le=100),
    hours: int = Query(default=24, ge=1, le=168),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Imagen-specific failure analysis: content filters, timeouts, rate limits."""
    from datetime import timedelta

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    stmt = (
        select(GenerationRequest)
        .where(
            GenerationRequest.status == RequestStatus.FAILED,
            GenerationRequest.updated_at >= cutoff,
        )
        .order_by(GenerationRequest.updated_at.desc())
        .limit(limit * 2)  # fetch more, filter to imagen
    )
    result = await session.execute(stmt)
    all_failed = list(result.scalars().all())

    imagen_failures = []
    for req in all_failed:
        err_msg = req.error_message or ""
        is_imagen = (
            "imagen" in err_msg.lower()
            or (req.current_agent and "image" in (req.current_agent or "").lower())
            or _extract_imagen_error(req) is not None
        )
        if is_imagen and len(imagen_failures) < limit:
            imagen_error = _extract_imagen_error(req)
            imagen_failures.append(
                {
                    "id": str(req.id),
                    "input_text": req.input_text[:100],
                    "error_message": req.error_message,
                    "imagen_error": imagen_error,
                    "current_agent": req.current_agent,
                    "created_at": req.created_at.isoformat() if req.created_at else None,
                }
            )

    # Category breakdown
    categories: dict[str, int] = {}
    for f in imagen_failures:
        cat = (f.get("imagen_error") or {}).get(
            "category", _guess_error_category(f.get("error_message", ""))
        )
        categories[cat] = categories.get(cat, 0) + 1

    return {
        "total_imagen_failures": len(imagen_failures),
        "time_window_hours": hours,
        "category_breakdown": categories,
        "failures": imagen_failures,
    }


# ── Deep health check ───────────────────────────────────────────────────────


@router.get("/health-deep", dependencies=[Depends(_require_admin_key)])
async def deep_health_check(
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Live health check — probes DB, Redis, and Imagen API."""
    checks: dict[str, Any] = {}

    # DB check
    t0 = time.time()
    try:
        await session.execute(text("SELECT 1"))
        checks["database"] = {"status": "ok", "latency_ms": round((time.time() - t0) * 1000, 1)}
    except Exception as e:
        checks["database"] = {"status": "error", "error": str(e)}

    # Redis check
    t0 = time.time()
    try:
        from chronocanvas.redis_client import get_redis

        redis = await get_redis()
        await redis.ping()
        # Get queue depth
        keys = await redis.keys("arq:job:*")
        checks["redis"] = {
            "status": "ok",
            "latency_ms": round((time.time() - t0) * 1000, 1),
            "queue_depth": len(keys),
        }
    except Exception as e:
        checks["redis"] = {"status": "error", "error": str(e)}

    # Imagen live probe (tiny test)
    t0 = time.time()
    try:
        from google import genai as genai_sdk

        client = genai_sdk.Client(api_key=settings.google_api_key)
        # Use list_models as a lightweight API ping instead of generating an image
        models = await asyncio.wait_for(
            asyncio.to_thread(lambda: list(client.models.list())),
            timeout=10,
        )
        imagen_models = [m.name for m in models if "imagen" in (m.name or "").lower()]
        checks["imagen"] = {
            "status": "ok",
            "latency_ms": round((time.time() - t0) * 1000, 1),
            "available_models": imagen_models[:5],
        }
    except Exception as e:
        checks["imagen"] = {
            "status": "error",
            "error": str(e),
            "latency_ms": round((time.time() - t0) * 1000, 1),
        }

    # Recent failure stats from DB
    try:
        from datetime import timedelta

        cutoff_1h = datetime.now(timezone.utc) - timedelta(hours=1)
        cutoff_24h = datetime.now(timezone.utc) - timedelta(hours=24)

        count_1h = await session.scalar(
            select(func.count())
            .select_from(GenerationRequest)
            .where(
                GenerationRequest.status == RequestStatus.FAILED,
                GenerationRequest.updated_at >= cutoff_1h,
            )
        )
        count_24h = await session.scalar(
            select(func.count())
            .select_from(GenerationRequest)
            .where(
                GenerationRequest.status == RequestStatus.FAILED,
                GenerationRequest.updated_at >= cutoff_24h,
            )
        )
        total_24h = await session.scalar(
            select(func.count())
            .select_from(GenerationRequest)
            .where(
                GenerationRequest.updated_at >= cutoff_24h,
            )
        )
        checks["failure_rate"] = {
            "last_1h": count_1h or 0,
            "last_24h": count_24h or 0,
            "total_requests_24h": total_24h or 0,
        }
    except Exception as e:
        checks["failure_rate"] = {"status": "error", "error": str(e)}

    overall = (
        "ok"
        if all(
            c.get("status") == "ok"
            for c in checks.values()
            if isinstance(c, dict) and "status" in c
        )
        else "degraded"
    )

    return {"status": overall, "checks": checks}


# ── Show single request ─────────────────────────────────────────────────────


@router.get("/request/{request_id}", dependencies=[Depends(_require_admin_key)])
async def get_request_detail(
    request_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Full audit detail for a single request — errors, LLM calls, agent trace."""
    from chronocanvas.db.repositories.images import ImageRepository
    from chronocanvas.db.repositories.requests import RequestRepository
    from chronocanvas.services.audit import AuditProjector

    repo = RequestRepository(session)
    request = await repo.get(request_id)
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")

    image_repo = ImageRepository(session)
    images = await image_repo.list_by_request(request_id)

    projector = AuditProjector()
    audit = projector.project(request, images)

    # Add imagen-specific error info
    imagen_error = _extract_imagen_error(request)

    result = audit.model_dump()
    result["imagen_error"] = imagen_error
    return result


# ── Retry a failed request ──────────────────────────────────────────────────


@router.post("/retry/{request_id}", dependencies=[Depends(_require_admin_key)])
async def retry_request(
    request_id: uuid.UUID,
    from_step: str = Query(default="orchestrator"),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Re-enqueue a failed request to the arq worker queue."""
    from chronocanvas.db.repositories.requests import RequestRepository
    from chronocanvas.services.generation import VALID_RETRY_STEPS

    repo = RequestRepository(session)
    request = await repo.get(request_id)
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")

    if from_step not in VALID_RETRY_STEPS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid from_step '{from_step}'. Valid: {sorted(VALID_RETRY_STEPS)}",
        )

    # Route to correct pipeline based on run_type
    run_type = request.run_type or "portrait"
    is_story = run_type in ("creative_story", "story")

    try:
        from arq import create_pool
        from arq.connections import RedisSettings

        pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
        if is_story:
            # Story pipeline: re-run from scratch (no mid-pipeline retry support)
            job = await pool.enqueue_job(
                "run_story_pipeline_task",
                str(request_id),
                request.input_text,
            )
        else:
            job = await pool.enqueue_job(
                "retry_generation_pipeline_task",
                str(request_id),
                from_step,
            )
        await pool.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to enqueue retry: {e}")

    return {
        "status": "enqueued",
        "request_id": str(request_id),
        "run_type": run_type,
        "from_step": from_step if not is_story else "full_rerun",
        "job_id": job.job_id if job else None,
    }


# ── Request stats ────────────────────────────────────────────────────────────


@router.get("/stats", dependencies=[Depends(_require_admin_key)])
async def get_request_stats(
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Aggregate request stats: counts by status, recent activity."""
    from datetime import timedelta

    status_counts = {}
    for status in RequestStatus:
        count = await session.scalar(
            select(func.count())
            .select_from(GenerationRequest)
            .where(
                GenerationRequest.status == status,
            )
        )
        status_counts[status.value] = count or 0

    cutoff_24h = datetime.now(timezone.utc) - timedelta(hours=24)
    recent_count = await session.scalar(
        select(func.count())
        .select_from(GenerationRequest)
        .where(
            GenerationRequest.created_at >= cutoff_24h,
        )
    )

    return {
        "status_counts": status_counts,
        "total": sum(status_counts.values()),
        "last_24h": recent_count or 0,
    }


# ── Helpers ──────────────────────────────────────────────────────────────────


def _extract_imagen_error(req: GenerationRequest) -> dict[str, Any] | None:
    """Extract structured Imagen error from error_message or agent_trace."""
    err = req.error_message or ""
    if not err:
        return None

    # Check if the error message looks imagen-related
    err_lower = err.lower()
    imagen_keywords = ["imagen", "image", "content", "filtered", "generate_images"]
    if not any(kw in err_lower for kw in imagen_keywords):
        # Also check if pipeline died at image_generation node
        if req.current_agent not in ("image_generation", "scene_image_generation"):
            return None

    return {
        "category": _guess_error_category(err),
        "message": err,
        "failed_at_node": req.current_agent,
    }


def _guess_error_category(error_message: str) -> str:
    """Best-effort classification of an error string."""
    if not error_message:
        return "unknown"
    msg = error_message.lower()
    if any(t in msg for t in ["content", "filtered", "safety", "blocked"]):
        return "content_filter"
    if any(t in msg for t in ["rate", "resource_exhausted", "429", "quota"]):
        return "rate_limit"
    if any(t in msg for t in ["timeout", "deadline"]):
        return "timeout"
    if any(t in msg for t in ["503", "unavailable"]):
        return "unavailable"
    if any(t in msg for t in ["403", "permission", "unauthorized"]):
        return "permission"
    return "unknown"
