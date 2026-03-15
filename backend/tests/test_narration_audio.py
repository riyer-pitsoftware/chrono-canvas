"""Tests for narration_audio_node — verifies parallel TTS, skip logic, and WAV output.

Run with:
    cd backend
    PYTHONPATH=src pytest tests/test_narration_audio.py -v
"""

import os

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-testing")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://x:x@localhost/x")
os.environ.setdefault("REDIS_URL", "redis://localhost/0")

import asyncio  # noqa: E402
import struct  # noqa: E402
from pathlib import Path  # noqa: E402
from types import SimpleNamespace  # noqa: E402
from unittest.mock import AsyncMock, MagicMock, patch  # noqa: E402

import pytest  # noqa: E402

from chronocanvas.agents.story.nodes.narration_audio import (
    _write_wav,
    narration_audio_node,
)


# ── _write_wav ───────────────────────────────────────────────────────────


def test_write_wav_creates_valid_header(tmp_path):
    pcm = b"\x00\x01" * 100  # 200 bytes of fake PCM
    out = tmp_path / "test.wav"
    _write_wav(pcm, sample_rate=24000, num_channels=1, sample_width=2, path=out)

    data = out.read_bytes()
    assert data[:4] == b"RIFF"
    assert data[8:12] == b"WAVE"
    assert data[12:16] == b"fmt "
    # PCM format = 1
    assert struct.unpack_from("<H", data, 20)[0] == 1
    # sample rate
    assert struct.unpack_from("<I", data, 24)[0] == 24000
    # data chunk
    assert data[36:40] == b"data"
    data_size = struct.unpack_from("<I", data, 40)[0]
    assert data_size == len(pcm)


def test_write_wav_creates_parent_dirs(tmp_path):
    out = tmp_path / "sub" / "dir" / "test.wav"
    _write_wav(b"\x00" * 10, 24000, 1, 2, out)
    assert out.exists()


# ── narration_audio_node ─────────────────────────────────────────────────


def _make_panel(scene_index, narration_text=None):
    p = {"scene_index": scene_index}
    if narration_text:
        p["narration_text"] = narration_text
    return p


def _fake_tts_response(pcm_data=b"\x00\x01" * 50):
    """Build a mock Gemini TTS response with inline audio data."""
    part = SimpleNamespace(
        inline_data=SimpleNamespace(
            mime_type="audio/L16",
            data=pcm_data,
        )
    )
    candidate = SimpleNamespace(content=SimpleNamespace(parts=[part]))
    usage = SimpleNamespace(prompt_token_count=10, candidates_token_count=20)
    return SimpleNamespace(candidates=[candidate], usage_metadata=usage)


@pytest.fixture
def _mock_settings(tmp_path):
    with patch("chronocanvas.agents.story.nodes.narration_audio.settings") as s:
        s.google_api_key = "fake-key"
        s.tts_model = "test-tts-model"
        s.tts_voice = "TestVoice"
        s.output_dir = str(tmp_path)
        yield s


@pytest.fixture
def _mock_gemini():
    with patch("chronocanvas.agents.story.nodes.narration_audio.genai") as g:
        g.Client.return_value = MagicMock()
        yield g


@pytest.fixture
def _mock_progress():
    with patch(
        "chronocanvas.agents.story.nodes.narration_audio.ProgressPublisher"
    ) as cls:
        cls.return_value.publish_artifact = AsyncMock()
        yield cls


@pytest.fixture
def _mock_tts():
    with patch(
        "chronocanvas.agents.story.nodes.narration_audio.gemini_generate_with_timeout",
        new_callable=AsyncMock,
    ) as m:
        m.return_value = _fake_tts_response()
        yield m


@pytest.mark.asyncio
async def test_skips_when_no_narration_text(_mock_settings, _mock_gemini, _mock_progress):
    state = {
        "request_id": "test-123",
        "panels": [_make_panel(0), _make_panel(1)],
        "agent_trace": [],
        "llm_calls": [],
    }
    result = await narration_audio_node(state)

    assert result["current_agent"] == "narration_audio"
    assert result["agent_trace"][-1]["skipped"] is True


@pytest.mark.asyncio
async def test_synthesizes_panels_in_parallel(
    _mock_settings, _mock_gemini, _mock_progress, _mock_tts, tmp_path
):
    panels = [
        _make_panel(0, "Scene zero narration"),
        _make_panel(1, "Scene one narration"),
        _make_panel(2),  # no narration — should be skipped
    ]
    state = {
        "request_id": "test-parallel",
        "panels": panels,
        "agent_trace": [],
        "llm_calls": [],
    }
    result = await narration_audio_node(state)

    # Two panels had narration text
    assert _mock_tts.call_count == 2
    assert len(result["narration_audio_paths"]) == 2
    assert result["agent_trace"][-1]["panels_synthesized"] == 2
    assert result["agent_trace"][-1]["total_with_text"] == 2

    # WAV files created
    for i in [0, 1]:
        wav = tmp_path / "test-parallel" / "audio" / f"scene_{i}.wav"
        assert wav.exists()


@pytest.mark.asyncio
async def test_handles_tts_failure_gracefully(
    _mock_settings, _mock_gemini, _mock_progress, _mock_tts
):
    _mock_tts.side_effect = [
        _fake_tts_response(),  # scene 0 succeeds
        Exception("TTS timeout"),  # scene 1 fails
    ]
    panels = [
        _make_panel(0, "Works fine"),
        _make_panel(1, "This one fails"),
    ]
    state = {
        "request_id": "test-fail",
        "panels": panels,
        "agent_trace": [],
        "llm_calls": [],
    }
    result = await narration_audio_node(state)

    assert len(result["narration_audio_paths"]) == 1
    assert result["agent_trace"][-1]["panels_synthesized"] == 1


@pytest.mark.asyncio
async def test_handles_no_audio_in_response(
    _mock_settings, _mock_gemini, _mock_progress, _mock_tts
):
    # Response with no audio part
    empty_response = SimpleNamespace(
        candidates=[SimpleNamespace(content=SimpleNamespace(parts=[]))],
        usage_metadata=None,
    )
    _mock_tts.return_value = empty_response

    state = {
        "request_id": "test-empty",
        "panels": [_make_panel(0, "Some text")],
        "agent_trace": [],
        "llm_calls": [],
    }
    result = await narration_audio_node(state)

    assert len(result["narration_audio_paths"]) == 0
    assert result["agent_trace"][-1]["panels_synthesized"] == 0


@pytest.mark.asyncio
async def test_records_llm_calls(
    _mock_settings, _mock_gemini, _mock_progress, _mock_tts
):
    state = {
        "request_id": "test-costs",
        "panels": [_make_panel(0, "Track this")],
        "agent_trace": [],
        "llm_calls": [],
    }
    result = await narration_audio_node(state)

    assert len(result["llm_calls"]) == 1
    call = result["llm_calls"][0]
    assert call["agent"] == "narration_audio"
    assert call["model"] == "test-tts-model"
    assert call["input_tokens"] == 10
    assert call["output_tokens"] == 20
