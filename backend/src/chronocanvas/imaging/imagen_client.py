"""Google Imagen image generator.

Uses the google-genai SDK's native async support to call Imagen
via ``client.aio.models.generate_images()``.  The same
``GOOGLE_API_KEY`` that powers Gemini LLM calls works here.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from pathlib import Path

from google import genai
from google.genai import types

from chronocanvas.config import settings
from chronocanvas.imaging.base import ImageGenerator, ImageResult

logger = logging.getLogger(__name__)

# Imagen supported aspect ratios and the (w, h) ranges that map to each.
# We pick the closest match based on the requested width/height ratio.
_ASPECT_RATIOS: list[tuple[str, float]] = [
    ("1:1", 1.0),
    ("3:4", 3 / 4),
    ("4:3", 4 / 3),
    ("9:16", 9 / 16),
    ("16:9", 16 / 9),
]

# Imagen 4 pricing (generate, fast model)
_COST_PER_IMAGE = 0.02


def _pick_aspect_ratio(width: int, height: int) -> str:
    """Map requested (width, height) to the nearest Imagen aspect ratio."""
    ratio = width / height if height else 1.0
    best = min(_ASPECT_RATIOS, key=lambda ar: abs(ar[1] - ratio))
    return best[0]


class ImagenGenerator(ImageGenerator):
    name = "imagen"

    def __init__(self) -> None:
        self._client: genai.Client | None = None

    def _get_client(self) -> genai.Client:
        if self._client is None:
            self._client = genai.Client(api_key=settings.google_api_key)
        return self._client

    async def generate(
        self,
        prompt: str,
        output_dir: Path,
        width: int = 512,
        height: int = 512,
        **kwargs,
    ) -> ImageResult:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        aspect_ratio = _pick_aspect_ratio(width, height)
        model = settings.imagen_model
        client = self._get_client()

        logger.info(
            "Imagen request: model=%s aspect=%s prompt=%.80s",
            model,
            aspect_ratio,
            prompt,
        )

        # Retry with exponential backoff for transient errors
        # (rate limits on free tier + 503 service unavailable)
        max_retries = 3
        request_timeout = 120  # seconds per attempt
        _RETRYABLE = {"rate", "resource_exhausted", "429", "503", "unavailable", "timeout"}
        for attempt in range(max_retries + 1):
            try:
                response = await asyncio.wait_for(
                    client.aio.models.generate_images(
                        model=model,
                        prompt=prompt,
                        config=types.GenerateImagesConfig(
                            number_of_images=1,
                            aspect_ratio=aspect_ratio,
                        ),
                    ),
                    timeout=request_timeout,
                )
                break
            except asyncio.TimeoutError:
                if attempt < max_retries:
                    wait = 2 ** (attempt + 1)
                    logger.warning(
                        "Imagen timeout after %ds (attempt %d/%d), retrying in %ds",
                        request_timeout,
                        attempt + 1,
                        max_retries,
                        wait,
                    )
                    await asyncio.sleep(wait)
                    continue
                raise TimeoutError(
                    f"Imagen API did not respond after {max_retries + 1} attempts "
                    f"({request_timeout}s timeout each)"
                )
            except Exception as exc:
                err_str = str(exc).lower()
                if any(tok in err_str for tok in _RETRYABLE):
                    if attempt < max_retries:
                        wait = 2 ** (attempt + 1)  # 2, 4, 8 seconds
                        logger.warning(
                            "Imagen transient error (attempt %d/%d), retrying in %ds: %s",
                            attempt + 1,
                            max_retries,
                            wait,
                            exc,
                        )
                        await asyncio.sleep(wait)
                        continue
                raise

        if not response.generated_images:
            raise RuntimeError("Imagen returned no images (content may have been filtered)")

        image_bytes = response.generated_images[0].image.image_bytes
        filename = f"{uuid.uuid4().hex}.png"
        filepath = output_dir / filename
        filepath.write_bytes(image_bytes)

        logger.info("Imagen image saved: %s", filepath)

        return ImageResult(
            file_path=str(filepath),
            width=width,
            height=height,
            provider=self.name,
            generation_params={
                "prompt": prompt,
                "model": model,
                "aspect_ratio": aspect_ratio,
                "cost_usd": _COST_PER_IMAGE,
            },
        )

    async def is_available(self) -> bool:
        return bool(settings.google_api_key)
