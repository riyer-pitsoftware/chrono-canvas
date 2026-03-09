import logging

from fastapi import APIRouter

from chronocanvas.config import settings
from chronocanvas.service_registry import get_registry

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


async def _build_service_map() -> dict:
    """Build availability map for all configurable services.

    Reports boolean availability only — never exposes key values.
    """
    # LLM providers — use the router's built-in check
    llm_avail = {}
    registry = get_registry()
    if registry.llm_router is not None:
        try:
            llm_avail = await registry.llm_router.check_availability()
        except Exception:
            logger.warning("Failed to check LLM availability", exc_info=True)

    if not llm_avail:
        # Fallback: infer from key presence (before registry is initialised)
        llm_avail = {
            "gemini": bool(settings.google_api_key),
            "claude": bool(settings.anthropic_api_key),
            "openai": bool(settings.openai_api_key),
            "ollama": False,
        }

    # Image providers — check key/config presence (no live health checks)
    image_avail = {
        "imagen": bool(settings.google_api_key),
        "comfyui": bool(settings.comfyui_api_url),
        "stable_diffusion": bool(settings.sd_api_url),
    }

    # Search services — check key presence
    search_avail = {
        "serpapi": bool(settings.serpapi_key),
        "pexels": bool(settings.pexels_api_key),
        "unsplash": bool(settings.unsplash_access_key),
    }

    return {
        "llm": llm_avail,
        "image": image_avail,
        "search": search_avail,
        "tts": bool(settings.google_api_key),
        "facefusion": settings.facefusion_enabled,
    }


def validate_hackathon_requirements() -> list[str]:
    """Check that all critical services are available for hackathon mode.

    Returns a list of failure messages (empty = all good).
    """
    failures = []
    if not settings.google_api_key:
        failures.append("GOOGLE_API_KEY not set — Gemini LLM, Imagen, TTS, and multimodal validation will fail")
    if settings.image_provider == "mock":
        failures.append("IMAGE_PROVIDER is 'mock' — judges will see placeholder images")
    if not settings.hackathon_strict_gemini:
        failures.append("HACKATHON_STRICT_GEMINI is not enabled — Gemini-only enforcement is off")
    return failures


@router.get("/health")
async def health_check():
    services = await _build_service_map()

    # Check GCS connectivity if in cloud mode
    gcs_status = None
    try:
        from chronocanvas.services.storage import get_storage_backend
        backend = get_storage_backend()
        if backend.is_cloud():
            gcs_status = "connected"
            services["gcs"] = True
        else:
            services["gcs"] = False
    except Exception as e:
        gcs_status = f"error: {e}"
        services["gcs"] = False

    result = {
        "status": "ok",
        "service": "chronocanvas",
        "deployment_mode": settings.deployment_mode,
        "hackathon_mode": settings.hackathon_mode,
        "services": services,
    }
    if gcs_status and gcs_status != "connected":
        result["gcs_status"] = gcs_status
    if settings.hackathon_mode:
        failures = validate_hackathon_requirements()
        if failures:
            result["hackathon_warnings"] = failures
            result["status"] = "degraded"
    return result
