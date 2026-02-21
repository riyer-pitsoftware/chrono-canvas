import tempfile

import pytest
from httpx import ASGITransport, AsyncClient

from chronocanvas.main import app


@pytest.fixture(autouse=True)
def _set_upload_dir(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.setattr("chronocanvas.api.routes.faces.settings.upload_dir", tmpdir)
        monkeypatch.setattr("chronocanvas.config.settings.upload_dir", tmpdir)
        yield tmpdir


@pytest.mark.asyncio
async def test_upload_jpeg():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/faces/upload",
            files={"file": ("face.jpg", b"\xff\xd8\xff\xe0fake jpeg", "image/jpeg")},
        )
        assert response.status_code == 200
        data = response.json()
        assert "face_id" in data
        assert "file_path" in data
        assert data["file_path"].endswith(".jpg")


@pytest.mark.asyncio
async def test_upload_png():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/faces/upload",
            files={"file": ("face.png", b"\x89PNG\r\n\x1a\nfake png", "image/png")},
        )
        assert response.status_code == 200
        assert response.json()["file_path"].endswith(".png")


@pytest.mark.asyncio
async def test_upload_webp():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/faces/upload",
            files={"file": ("face.webp", b"RIFFxxxxWEBP", "image/webp")},
        )
        assert response.status_code == 200
        assert response.json()["file_path"].endswith(".webp")


@pytest.mark.asyncio
async def test_reject_invalid_content_type():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/faces/upload",
            files={"file": ("doc.pdf", b"fake pdf content", "application/pdf")},
        )
        assert response.status_code == 400
        assert "Unsupported file type" in response.json()["detail"]


@pytest.mark.asyncio
async def test_reject_oversized_file():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # 11MB of data
        large_data = b"\x00" * (11 * 1024 * 1024)
        response = await client.post(
            "/api/faces/upload",
            files={"file": ("big.jpg", large_data, "image/jpeg")},
        )
        assert response.status_code == 400
        assert "10MB" in response.json()["detail"]
