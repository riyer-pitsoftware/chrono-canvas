import uuid
from pathlib import Path

import httpx

from historylens.config import settings
from historylens.imaging.base import ImageGenerator, ImageResult


class FaceFusionClient(ImageGenerator):
    name = "facefusion"

    def __init__(self):
        self.base_url = settings.facefusion_api_url

    async def generate(
        self,
        prompt: str,
        output_dir: Path,
        width: int = 512,
        height: int = 512,
        source_image: str | None = None,
        target_image: str | None = None,
        **kwargs,
    ) -> ImageResult:
        output_dir.mkdir(parents=True, exist_ok=True)

        payload = {
            "source_image": source_image,
            "target_image": target_image,
            "output_width": width,
            "output_height": height,
        }

        async with httpx.AsyncClient(timeout=300.0) as client:
            resp = await client.post(f"{self.base_url}/api/process", json=payload)
            resp.raise_for_status()
            image_data = resp.content

        filename = f"{uuid.uuid4().hex}.png"
        filepath = output_dir / filename
        filepath.write_bytes(image_data)

        return ImageResult(
            file_path=str(filepath),
            width=width,
            height=height,
            provider=self.name,
            generation_params={"source": source_image, "target": target_image},
        )

    async def is_available(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.base_url}/api/health")
                return resp.status_code == 200
        except Exception:
            return False
