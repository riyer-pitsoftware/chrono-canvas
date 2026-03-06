from unittest.mock import patch

from chronocanvas.runtime_config import RuntimeConfig


def test_from_empty_payload():
    rc = RuntimeConfig.from_request_payload({})
    assert rc.mode is None
    assert rc.llm_provider is None
    assert rc.image_provider is None
    assert rc.tts_enabled is None
    assert rc.agent_routing == {}


def test_from_none_payload():
    rc = RuntimeConfig.from_request_payload(None)
    assert rc.llm_provider is None


FULL_PAYLOAD = {
    "mode": "gcp",
    "llm": {
        "provider": "gemini",
        "model": "gemini-2.5-flash",
        "strict_gemini": True,
        "agent_routing": {"extraction": "claude"},
    },
    "image": {
        "provider": "imagen",
        "model": "imagen-4.0-fast-generate-001",
        "width": 512,
        "height": 512,
    },
    "search": {
        "face_search": True,
        "research_cache": True,
        "cache_threshold": 0.9,
    },
    "voice": {
        "tts_enabled": True,
        "tts_voice": "Kore",
        "voice_input": False,
    },
    "vision": {
        "image_to_story": True,
        "vision_narration": False,
        "conversation_mode": False,
    },
    "post": {
        "facefusion": False,
        "validation_retry": True,
        "content_moderation": True,
        "video_assembly": True,
        "scene_editing": True,
    },
}


def test_from_full_payload():
    rc = RuntimeConfig.from_request_payload(FULL_PAYLOAD)
    assert rc.mode == "gcp"
    assert rc.llm_provider == "gemini"
    assert rc.llm_model == "gemini-2.5-flash"
    assert rc.strict_gemini is True
    assert rc.agent_routing == {"extraction": "claude"}
    assert rc.image_provider == "imagen"
    assert rc.image_model == "imagen-4.0-fast-generate-001"
    assert rc.portrait_width == 512
    assert rc.portrait_height == 512
    assert rc.face_search_enabled is True
    assert rc.research_cache_threshold == 0.9
    assert rc.tts_enabled is True
    assert rc.tts_voice == "Kore"
    assert rc.voice_input_enabled is False
    assert rc.image_to_story_enabled is True
    assert rc.vision_narration_enabled is False
    assert rc.facefusion_enabled is False
    assert rc.video_assembly_enabled is True


def test_effective_uses_override():
    rc = RuntimeConfig(llm_provider="claude", tts_enabled=False)
    assert rc.effective("llm_provider") == "claude"
    assert rc.effective("tts_enabled") is False


def test_effective_falls_back_to_settings():
    rc = RuntimeConfig()  # all None
    # Mock the settings import to avoid needing a real .env
    mock_settings = type("S", (), {"default_llm_provider": "gemini", "tts_enabled": True})()
    with patch("chronocanvas.runtime_config.settings", mock_settings, create=True):
        # effective() imports settings inside the function, so we patch at module level
        from chronocanvas import runtime_config
        with patch.object(runtime_config, "settings", mock_settings, create=True):
            # Direct fallback: llm_provider is None, but settings has default_llm_provider
            # The key must match the settings attribute name
            assert rc.effective("default_llm_provider") == "gemini"
            assert rc.effective("tts_enabled") is True
