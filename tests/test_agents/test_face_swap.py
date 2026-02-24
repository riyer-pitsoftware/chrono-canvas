import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from chronocanvas.agents.nodes.facial_compositing import facial_compositing_node
from chronocanvas.imaging.base import ImageResult


def _base_state(tmp_path: str, **overrides) -> dict:
    return {
        "request_id": "test-req-1",
        "input_text": "Julius Caesar",
        "extraction": {"figure_name": "Julius Caesar"},
        "image": {"image_path": ""},
        "face": {},
        "agent_trace": [],
        "error": None,
        **overrides,
    }


@pytest.mark.asyncio
async def test_skip_when_no_source_face():
    state = _base_state("/tmp")
    result = await facial_compositing_node(state)

    assert result["current_agent"] == "facial_compositing"
    trace = result["agent_trace"]
    assert len(trace) == 1
    assert trace[0]["agent"] == "facial_compositing"
    assert trace[0]["skipped"] is True
    assert "compositing" not in result


@pytest.mark.asyncio
async def test_skip_when_no_image_path():
    state = _base_state("/tmp", face={"source_face_path": "/tmp/face.jpg"}, image={"image_path": ""})
    result = await facial_compositing_node(state)

    trace = result["agent_trace"]
    assert trace[0]["skipped"] is True
    assert trace[0].get("reason") == "no_image"


@pytest.mark.asyncio
async def test_skip_when_image_path_missing_file():
    state = _base_state(
        "/tmp",
        face={"source_face_path": "/tmp/face.jpg"},
        image={"image_path": "/tmp/nonexistent_image.png"},
    )
    result = await facial_compositing_node(state)

    trace = result["agent_trace"]
    assert trace[0]["skipped"] is True
    assert trace[0].get("reason") == "no_image"


@pytest.mark.asyncio
async def test_success_path(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        image_file = Path(tmpdir) / "generated.png"
        image_file.write_bytes(b"fake png data")

        face_file = Path(tmpdir) / "face.jpg"
        face_file.write_bytes(b"fake face data")

        state = _base_state(
            tmpdir,
            face={"source_face_path": str(face_file)},
            image={"image_path": str(image_file)},
        )

        with patch(
            "chronocanvas.agents.nodes.facial_compositing._get_compositing_client"
        ) as mock_get_client:
            mock_client = AsyncMock()
            mock_result = ImageResult(
                file_path=str(Path(tmpdir) / "swapped.png"),
                width=512,
                height=512,
                provider="facefusion",
                generation_params={},
            )
            mock_client.generate.return_value = mock_result
            mock_get_client.return_value = mock_client

            result = await facial_compositing_node(state)

        comp = result["compositing"]
        assert "swapped_image_path" in comp
        assert "original_" in comp["original_image_path"]
        assert result["current_agent"] == "facial_compositing"

        trace = result["agent_trace"]
        assert len(trace) == 1
        assert trace[0]["skipped"] is False
        assert trace[0]["source_face"] == str(face_file)

        assert Path(comp["original_image_path"]).exists()

        mock_client.generate.assert_called_once()
        call_kwargs = mock_client.generate.call_args
        assert call_kwargs.kwargs["source_image"] == str(face_file)
        assert call_kwargs.kwargs["target_image"] == str(image_file)


@pytest.mark.asyncio
async def test_graceful_degradation_on_exception():
    with tempfile.TemporaryDirectory() as tmpdir:
        image_file = Path(tmpdir) / "generated.png"
        image_file.write_bytes(b"fake png data")

        state = _base_state(
            tmpdir,
            face={"source_face_path": "/tmp/face.jpg"},
            image={"image_path": str(image_file)},
        )

        with patch(
            "chronocanvas.agents.nodes.facial_compositing._get_compositing_client"
        ) as mock_get_client:
            mock_client = AsyncMock()
            mock_client.generate.side_effect = RuntimeError("FaceFusion server down")
            mock_get_client.return_value = mock_client

            result = await facial_compositing_node(state)

        assert result.get("error") is None or result.get("error") == state.get("error")
        assert "compositing" not in result
        assert result["current_agent"] == "facial_compositing"

        trace = result["agent_trace"]
        assert trace[0]["error"] is True
        assert trace[0]["skipped"] is False
