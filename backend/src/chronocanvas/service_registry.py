"""Lightweight service registry for explicit dependency wiring.

All cross-cutting singletons (LLM router, Redis client, image generator
factory, etc.) are registered here during application startup and accessed
via ``get_registry()``.  This replaces scattered module-level globals with
a single, inspectable, and replaceable composition root.

Nodes still call thin accessor functions (``get_llm_router``, etc.) because
LangGraph constrains node signatures to ``(state) -> dict``.  Those accessor
functions now delegate to this registry instead of managing their own globals.

Tests can replace the entire registry or individual fields before exercising
the code under test.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import redis.asyncio as aioredis

    from chronocanvas.imaging.base import ImageGenerator
    from chronocanvas.llm.router import LLMRouter
    from chronocanvas.memory.cache_service import ResearchCacheService

logger = logging.getLogger(__name__)


@dataclass
class ServiceRegistry:
    """Holds references to all application-scoped service instances."""

    llm_router: LLMRouter | None = None
    redis: aioredis.Redis | None = None
    research_cache: ResearchCacheService | None = None

    # Factory callables — return a fresh client each time (provider selection
    # is encapsulated here rather than scattered across node modules).
    image_generator_factory: Any = field(default=None)
    compositing_client_factory: Any = field(default=None)


# Module-level instance; starts empty and is populated during startup.
_registry: ServiceRegistry = ServiceRegistry()


def get_registry() -> ServiceRegistry:
    """Return the current service registry."""
    return _registry


def set_registry(registry: ServiceRegistry) -> None:
    """Replace the global registry (primarily for tests)."""
    global _registry
    _registry = registry


def init_registry() -> None:
    """Populate the registry with production service instances.

    Called during application startup (FastAPI lifespan / ARQ on_startup).
    """
    global _registry

    from chronocanvas.config import settings
    from chronocanvas.imaging.comfyui_client import ComfyUIClient
    from chronocanvas.imaging.facefusion_client import FaceFusionClient
    from chronocanvas.imaging.imagen_client import ImagenGenerator
    from chronocanvas.imaging.mock_face_swap import MockFaceSwapClient
    from chronocanvas.imaging.mock_generator import MockImageGenerator
    from chronocanvas.imaging.sd_client import StableDiffusionClient
    from chronocanvas.llm.router import LLMRouter
    from chronocanvas.memory.cache_service import ResearchCacheService

    def _image_generator_factory() -> ImageGenerator:
        if settings.image_provider == "stable_diffusion":
            return StableDiffusionClient()
        if settings.image_provider == "comfyui":
            return ComfyUIClient()
        if settings.image_provider == "mock":
            return MockImageGenerator()
        # Default: Imagen (requires GOOGLE_API_KEY)
        return ImagenGenerator()

    def _compositing_client_factory():
        if settings.facefusion_enabled:
            return FaceFusionClient()
        return MockFaceSwapClient()

    _registry.llm_router = LLMRouter()
    _registry.research_cache = ResearchCacheService()
    _registry.image_generator_factory = _image_generator_factory
    _registry.compositing_client_factory = _compositing_client_factory
    logger.info("Service registry initialised")
