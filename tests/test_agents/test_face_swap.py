import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from chronocanvas.agents.nodes.face_swap import face_swap_node
from chronocanvas.imaging.base import ImageResult


def _base_state(tmp_path: str, **overrides) -> dict:
    return {
        "request_id": "test-req-1",
        "input_text": "Julius Caesar",
        "figure_name": "Julius Caesar",
        "image_path": "",
        "agent_trace": [],
        "error": None,
        **overrides,
    }


@pytest.mark.asyncio
async def test_skip_when_no_source_face():
    state = _base_state("/tmp")
    result = await face_swap_node(state)

    assert result["current_agent"] == "face_swap"
    trace = result["agent_trace"]
    assert len(trace) == 1
    assert trace[0]["agent"] == "face_swap"
    assert trace[0]["skipped"] is True
    # Should not set swapped/original paths
    assert "swapped_image_path" not in result
    assert "original_image_path" not in result


@pytest.mark.asyncio
async def test_skip_when_no_image_path():
    state = _base_state("/tmp", source_face_path="/tmp/face.jpg", image_path="")
    result = await face_swap_node(state)

    trace = result["agent_trace"]
    assert trace[0]["skipped"] is True
    assert trace[0].get("reason") == "no_image"


@pytest.mark.asyncio
async def test_skip_when_image_path_missing_file():
    state = _base_state(
        "/tmp",
        source_face_path="/tmp/face.jpg",
        image_path="/tmp/nonexistent_image.png",
    )
    result = await face_swap_node(state)

    trace = result["agent_trace"]
    assert trace[0]["skipped"] is True
    assert trace[0].get("reason") == "no_image"


@pytest.mark.asyncio
async def test_success_path():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a fake source image
        image_file = Path(tmpdir) / "generated.png"
        image_file.write_bytes(b"fake png data")

        face_file = Path(tmpdir) / "face.jpg"
        face_file.write_bytes(b"fake face data")

        swapped_path = str(Path(tmpdir) / "swapped.png")

        mock_result = ImageResult(
            file_path=swapped_path,
            width=512,
            height=512,
            provider="facefusion",
            generation_params={},
        )

        state = _base_state(
            tmpdir,
            source_face_path=str(face_file),
            image_path=str(image_file),
        )

        with patch(
            "chronocanvas.agents.nodes.face_swap.FaceFusionClient"
        ) as mock_cls:
            mock_client = AsyncMock()
            mock_client.generate.return_value = mock_result
            mock_cls.return_value = mock_client

            result = await face_swap_node(state)

        assert result["swapped_image_path"] == swapped_path
        assert "original_" in result["original_image_path"]
        assert result["current_agent"] == "face_swap"

        trace = result["agent_trace"]
        assert len(trace) == 1
        assert trace[0]["skipped"] is False
        assert trace[0]["source_face"] == str(face_file)

        # Original image should have been copied
        assert Path(result["original_image_path"]).exists()

        # FaceFusionClient was called with correct args
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
            source_face_path="/tmp/face.jpg",
            image_path=str(image_file),
        )

        with patch(
            "chronocanvas.agents.nodes.face_swap.FaceFusionClient"
        ) as mock_cls:
            mock_client = AsyncMock()
            mock_client.generate.side_effect = RuntimeError("FaceFusion server down")
            mock_cls.return_value = mock_client

            result = await face_swap_node(state)

        # Should NOT set error — face swap failure is non-fatal
        assert result.get("error") is None or result.get("error") == state.get("error")
        assert "swapped_image_path" not in result
        assert result["current_agent"] == "face_swap"

        trace = result["agent_trace"]
        assert trace[0]["error"] is True
        assert trace[0]["skipped"] is False
