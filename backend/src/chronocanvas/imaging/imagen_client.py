"""Google Imagen image generator.

Uses the google-genai SDK's native async support to call Imagen
via ``client.aio.models.generate_images()``.  The same
``GOOGLE_API_KEY`` that powers Gemini LLM calls works here.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from pathlib import Path
from typing import Any

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

# Error taxonomy for structured classification
_ERROR_CATEGORIES = {
    "content_filter": ["content", "filtered", "safety", "blocked", "policy", "responsible ai"],
    "rate_limit": ["rate", "resource_exhausted", "429", "quota"],
    "timeout": ["timeout", "deadline"],
    "unavailable": ["503", "unavailable", "service error"],
    "permission": ["403", "forbidden", "permission", "unauthorized", "401"],
    "invalid_request": ["400", "invalid", "bad request"],
}


def classify_imagen_error(exc: Exception) -> dict[str, Any]:
    """Classify an Imagen API error into a structured error dict."""
    err_str = str(exc).lower()
    err_type = type(exc).__name__

    category = "unknown"
    for cat, tokens in _ERROR_CATEGORIES.items():
        if any(tok in err_str for tok in tokens):
            category = cat
            break

    return {
        "category": category,
        "error_type": err_type,
        "message": str(exc),
        "retryable": category in ("rate_limit", "timeout", "unavailable"),
    }


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
        max_retries = 3
        request_timeout = 120  # seconds per attempt
        retry_history: list[dict[str, Any]] = []

        for attempt in range(max_retries + 1):
            attempt_start = time.time()
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
                elapsed = time.time() - attempt_start
                error_info = {
                    "category": "timeout",
                    "error_type": "TimeoutError",
                    "message": f"Imagen API did not respond within {request_timeout}s",
                    "retryable": True,
                }
                retry_history.append(
                    {
                        "attempt": attempt + 1,
                        "elapsed_s": round(elapsed, 2),
                        **error_info,
                    }
                )
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
                raise ImagenError(
                    f"Imagen API did not respond after {max_retries + 1} attempts "
                    f"({request_timeout}s timeout each)",
                    category="timeout",
                    retry_history=retry_history,
                )
            except Exception as exc:
                elapsed = time.time() - attempt_start
                error_info = classify_imagen_error(exc)
                retry_history.append(
                    {
                        "attempt": attempt + 1,
                        "elapsed_s": round(elapsed, 2),
                        **error_info,
                    }
                )
                if error_info["retryable"] and attempt < max_retries:
                    wait = 2 ** (attempt + 1)  # 2, 4, 8 seconds
                    logger.warning(
                        "Imagen %s error (attempt %d/%d), retrying in %ds: %s",
                        error_info["category"],
                        attempt + 1,
                        max_retries,
                        wait,
                        exc,
                    )
                    await asyncio.sleep(wait)
                    continue
                raise ImagenError(
                    str(exc),
                    category=error_info["category"],
                    retry_history=retry_history,
                ) from exc

        if not response.generated_images:
            retry_history.append(
                {
                    "attempt": len(retry_history) + 1,
                    "elapsed_s": 0,
                    "category": "content_filter",
                    "error_type": "EmptyResponse",
                    "message": "Imagen returned no images (content may have been filtered)",
                    "retryable": False,
                }
            )
            raise ImagenError(
                "Imagen returned no images (content may have been filtered)",
                category="content_filter",
                retry_history=retry_history,
            )

        image_bytes = response.generated_images[0].image.image_bytes
        filename = f"{uuid.uuid4().hex}.png"
        filepath = output_dir / filename
        filepath.write_bytes(image_bytes)

        logger.info(
            "Imagen image saved: %s (retries=%d)",
            filepath,
            len(retry_history),
        )

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
                "retry_history": retry_history,
            },
        )

    async def is_available(self) -> bool:
        return bool(settings.google_api_key)


class ImagenError(RuntimeError):
    """Structured Imagen API error with classification and retry history."""

    def __init__(
        self,
        message: str,
        *,
        category: str = "unknown",
        retry_history: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(message)
        self.category = category
        self.retry_history = retry_history or []

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "message": str(self),
            "retries_attempted": len(self.retry_history),
            "retry_history": self.retry_history,
        }
