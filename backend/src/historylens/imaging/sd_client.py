import base64
import uuid
from pathlib import Path

import httpx

from historylens.config import settings
from historylens.imaging.base import ImageGenerator, ImageResult


class StableDiffusionClient(ImageGenerator):
    name = "stable_diffusion"

    def __init__(self):
        self.base_url = settings.sd_api_url

    async def generate(
        self,
        prompt: str,
        output_dir: Path,
        width: int = 512,
        height: int = 512,
        negative_prompt: str = "blurry, bad anatomy, modern clothing, anachronistic",
        steps: int = 30,
        cfg_scale: float = 7.5,
        **kwargs,
    ) -> ImageResult:
        output_dir.mkdir(parents=True, exist_ok=True)

        payload = {
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "width": width,
            "height": height,
            "steps": steps,
            "cfg_scale": cfg_scale,
        }

        async with httpx.AsyncClient(timeout=300.0) as client:
            resp = await client.post(f"{self.base_url}/sdapi/v1/txt2img", json=payload)
            resp.raise_for_status()
            data = resp.json()

        image_data = base64.b64decode(data["images"][0])
        filename = f"{uuid.uuid4().hex}.png"
        filepath = output_dir / filename
        filepath.write_bytes(image_data)

        return ImageResult(
            file_path=str(filepath),
            width=width,
            height=height,
            provider=self.name,
            generation_params=payload,
        )

    async def is_available(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.base_url}/sdapi/v1/sd-models")
                return resp.status_code == 200
        except Exception:
            return False
