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
        "tts": settings.tts_enabled and bool(settings.google_api_key),
        "facefusion": settings.facefusion_enabled,
    }


@router.get("/health")
async def health_check():
    services = await _build_service_map()
    return {
        "status": "ok",
        "service": "chronocanvas",
        "hackathon_mode": settings.hackathon_mode,
        "services": services,
    }
