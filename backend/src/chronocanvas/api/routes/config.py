"""Config validation endpoint — validates a ConfigHUD payload before orchestration."""

import logging

from fastapi import APIRouter

from chronocanvas.api.routes.health import _build_service_map
from chronocanvas.runtime_config import RuntimeConfig

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/config", tags=["config"])

# Providers that require cloud API keys (unavailable in local-only mode)
_CLOUD_ONLY_PROVIDERS = {
    "llm": {"gemini", "claude", "openai"},
    "image": {"imagen"},
}

# Providers that require local services (unavailable in GCP mode)
_LOCAL_ONLY_PROVIDERS = {
    "llm": {"ollama"},
    "image": {"comfyui", "stable_diffusion"},
}


@router.post("/validate")
async def validate_config(payload: dict):
    """Validate a config payload against available keys and mode constraints.

    Returns {"valid": true} or {"valid": false, "errors": [...]}.
    """
    errors: list[dict] = []

    rc = RuntimeConfig.from_request_payload(payload)
    services = await _build_service_map()
    mode = rc.mode  # "gcp" or "local" or None

    # Validate LLM provider
    if rc.llm_provider:
        llm_avail = services.get("llm", {})
        if not llm_avail.get(rc.llm_provider):
            errors.append({
                "channel": "llm",
                "provider": rc.llm_provider,
                "error": f"LLM provider '{rc.llm_provider}' is not available "
                         f"(missing API key or service down)",
            })
        if mode == "gcp" and rc.llm_provider in _LOCAL_ONLY_PROVIDERS.get("llm", set()):
            errors.append({
                "channel": "llm",
                "provider": rc.llm_provider,
                "error": f"Provider '{rc.llm_provider}' is not available in GCP mode",
            })

    # Validate image provider
    if rc.image_provider:
        image_avail = services.get("image", {})
        if not image_avail.get(rc.image_provider):
            errors.append({
                "channel": "image",
                "provider": rc.image_provider,
                "error": f"Image provider '{rc.image_provider}' is not available "
                         f"(missing API key or service down)",
            })
        if mode == "gcp" and rc.image_provider in _LOCAL_ONLY_PROVIDERS.get("image", set()):
            errors.append({
                "channel": "image",
                "provider": rc.image_provider,
                "error": f"Provider '{rc.image_provider}' is not available in GCP mode",
            })

    # Validate TTS requires Google API key
    if rc.tts_enabled:
        tts_avail = services.get("tts", False)
        if not tts_avail:
            errors.append({
                "channel": "voice",
                "provider": "gemini_tts",
                "error": "TTS requires GOOGLE_API_KEY",
            })

    # Validate FaceFusion requires local service
    if rc.facefusion_enabled:
        ff_avail = services.get("facefusion", False)
        if not ff_avail:
            errors.append({
                "channel": "compositing",
                "provider": "facefusion",
                "error": "FaceFusion is not enabled on this deployment",
            })
        if mode == "gcp":
            errors.append({
                "channel": "compositing",
                "provider": "facefusion",
                "error": "FaceFusion is not available in GCP mode",
            })

    # Validate per-agent routing references valid providers
    for agent, provider in rc.agent_routing.items():
        if provider not in {"gemini", "claude", "openai", "ollama"}:
            errors.append({
                "channel": "llm",
                "provider": provider,
                "error": f"Unknown LLM provider '{provider}' in agent routing for '{agent}'",
            })

    return {"valid": len(errors) == 0, "errors": errors}
