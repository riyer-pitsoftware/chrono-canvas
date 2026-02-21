import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from chronocanvas.main import app


@pytest.fixture(autouse=True)
def _setup_dirs(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.setattr("chronocanvas.config.settings.upload_dir", tmpdir)
        monkeypatch.setattr("chronocanvas.config.settings.output_dir", tmpdir)
        monkeypatch.setattr("chronocanvas.api.routes.generation.settings.upload_dir", tmpdir)
        yield tmpdir


@pytest.mark.asyncio
async def test_create_generation_with_face_id(_setup_dirs):
    tmpdir = _setup_dirs
    # Create a face file
    faces_dir = Path(tmpdir) / "faces"
    faces_dir.mkdir()
    face_file = faces_dir / "abc123.jpg"
    face_file.write_bytes(b"fake face")

    with patch("chronocanvas.api.routes.generation.run_generation_pipeline") as mock_pipeline:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/generate",
                json={"input_text": "Julius Caesar", "face_id": "abc123"},
            )

        assert response.status_code == 201

        # Verify pipeline was called with source_face_path
        mock_pipeline.assert_called_once()
        call_kwargs = mock_pipeline.call_args
        assert call_kwargs.kwargs["source_face_path"] == str(face_file)


@pytest.mark.asyncio
async def test_create_generation_without_face_id():
    with patch("chronocanvas.api.routes.generation.run_generation_pipeline") as mock_pipeline:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/generate",
                json={"input_text": "Cleopatra"},
            )

        assert response.status_code == 201

        # Pipeline called without source_face_path
        mock_pipeline.assert_called_once()
        call_kwargs = mock_pipeline.call_args
        assert call_kwargs.kwargs.get("source_face_path") is None


@pytest.mark.asyncio
async def test_create_generation_face_not_found():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/generate",
            json={"input_text": "Caesar", "face_id": "nonexistent"},
        )

    assert response.status_code == 404
    assert "Face not found" in response.json()["detail"]
