"""Per-request configuration overrides from the UI ConfigHUD.

Values of None mean 'use global Settings default'.
The effective() helper merges runtime overrides with global Settings.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RuntimeConfig:
    # Mode
    mode: str | None = None  # "gcp" or "local"

    # LLM
    llm_provider: str | None = None
    llm_model: str | None = None
    strict_gemini: bool | None = None
    agent_routing: dict[str, str] = field(default_factory=dict)

    # Image Generation
    image_provider: str | None = None
    image_model: str | None = None
    portrait_width: int | None = None
    portrait_height: int | None = None

    # Search & Reference
    face_search_enabled: bool | None = None
    research_cache_enabled: bool | None = None
    research_cache_threshold: float | None = None

    # Voice & TTS
    tts_enabled: bool | None = None
    tts_voice: str | None = None
    voice_input_enabled: bool | None = None

    # Vision & Multimodal
    image_to_story_enabled: bool | None = None
    vision_narration_enabled: bool | None = None
    conversation_mode_enabled: bool | None = None

    # Compositing & Post
    facefusion_enabled: bool | None = None
    validation_retry_enabled: bool | None = None
    content_moderation_enabled: bool | None = None
    video_assembly_enabled: bool | None = None
    scene_editing_enabled: bool | None = None

    def effective(self, key: str, default: Any = None) -> Any:
        """Return runtime override if set, otherwise global Settings value."""
        val = getattr(self, key, None)
        if val is not None:
            return val
        from chronocanvas.config import settings

        return getattr(settings, key, default)

    @classmethod
    def from_request_payload(cls, payload: dict | None) -> RuntimeConfig:
        """Parse the config section of a generation request."""
        rc = cls()
        if not payload:
            return rc

        rc.mode = payload.get("mode")

        llm = payload.get("llm", {})
        rc.llm_provider = llm.get("provider")
        rc.llm_model = llm.get("model")
        rc.strict_gemini = llm.get("strict_gemini")
        rc.agent_routing = llm.get("agent_routing", {})

        image = payload.get("image", {})
        rc.image_provider = image.get("provider")
        rc.image_model = image.get("model")
        rc.portrait_width = image.get("width")
        rc.portrait_height = image.get("height")

        search = payload.get("search", {})
        rc.face_search_enabled = search.get("face_search")
        rc.research_cache_enabled = search.get("research_cache")
        rc.research_cache_threshold = search.get("cache_threshold")

        voice = payload.get("voice", {})
        rc.tts_enabled = voice.get("tts_enabled")
        rc.tts_voice = voice.get("tts_voice")
        rc.voice_input_enabled = voice.get("voice_input")

        vision = payload.get("vision", {})
        rc.image_to_story_enabled = vision.get("image_to_story")
        rc.vision_narration_enabled = vision.get("vision_narration")
        rc.conversation_mode_enabled = vision.get("conversation_mode")

        post = payload.get("post", {})
        rc.facefusion_enabled = post.get("facefusion")
        rc.validation_retry_enabled = post.get("validation_retry")
        rc.content_moderation_enabled = post.get("content_moderation")
        rc.video_assembly_enabled = post.get("video_assembly")
        rc.scene_editing_enabled = post.get("scene_editing")

        return rc
