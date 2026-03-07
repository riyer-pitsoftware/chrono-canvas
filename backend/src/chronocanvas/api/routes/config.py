"""Config validation endpoint — validates a ConfigHUD payload before orchestration.

Enforces the server-side ``DEPLOYMENT_MODE`` setting so that GCP deployments
cannot accidentally use local-only providers (Ollama, ComfyUI, FaceFusion) and
local deployments cannot accidentally require cloud API keys they don't have.
"""

import logging

from fastapi import APIRouter

from chronocanvas.api.routes.health import _build_service_map
from chronocanvas.config import settings
from chronocanvas.runtime_config import RuntimeConfig

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/config", tags=["config"])

# Providers that require local services (unavailable in GCP mode)
_LOCAL_ONLY_PROVIDERS = {
    "llm": {"ollama"},
    "image": {"comfyui", "stable_diffusion"},
}


def _is_gcp_locked() -> bool:
    """True when the server enforces GCP-only providers."""
    return settings.deployment_mode == "gcp"


@router.post("/validate")
async def validate_config(payload: dict):
    """Validate a config payload against available keys and mode constraints.

    Returns {"valid": true} or {"valid": false, "errors": [...]}.
    """
    errors: list[dict] = []

    rc = RuntimeConfig.from_request_payload(payload)
    services = await _build_service_map()
    gcp_locked = _is_gcp_locked()

    # Enforce deployment_mode: reject "local" mode on GCP deployments
    if gcp_locked and rc.mode == "local":
        errors.append({
            "channel": "system",
            "provider": "",
            "error": "This deployment only supports GCP mode (DEPLOYMENT_MODE=gcp)",
        })

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
        if (gcp_locked or rc.mode == "gcp") and rc.llm_provider in _LOCAL_ONLY_PROVIDERS["llm"]:
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
        if (gcp_locked or rc.mode == "gcp") and rc.image_provider in _LOCAL_ONLY_PROVIDERS["image"]:
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
        if gcp_locked or rc.mode == "gcp":
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
        if gcp_locked and provider in _LOCAL_ONLY_PROVIDERS["llm"]:
            errors.append({
                "channel": "llm",
                "provider": provider,
                "error": f"Agent '{agent}' cannot use '{provider}' in GCP mode",
            })

    return {"valid": len(errors) == 0, "errors": errors}
