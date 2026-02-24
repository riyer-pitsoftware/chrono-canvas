import uuid
from typing import Any

from chronocanvas.db.models.image import GeneratedImage


class ImageAttemptRecorder:
    """Accumulates image generation attempts and flushes them as DB rows at pipeline end."""

    def __init__(self) -> None:
        self._attempts: list[dict[str, Any]] = []

    def on_image_generated(self, node_state: dict[str, Any]) -> None:
        """Record a new image attempt when the image_generation node completes."""
        img = node_state.get("image", {})
        prompt_state = node_state.get("prompt", {})
        self._attempts.append({
            "image_path": img.get("image_path", ""),
            "provider": img.get("image_provider", "mock"),
            "prompt": prompt_state.get("image_prompt", ""),
            "validation_score": None,
        })

    def on_validation(self, node_state: dict[str, Any]) -> None:
        """Associate the validation score with the most recent attempt."""
        if self._attempts:
            val = node_state.get("validation", {})
            self._attempts[-1]["validation_score"] = val.get("validation_score")

    async def flush(self, session: Any, request_id: str, final_state: dict[str, Any]) -> None:
        """Persist all recorded attempts as GeneratedImage rows.

        Handles three cases:
        - Normal: one or more recorded attempts from streaming events.
        - Composited: a facial_compositing result is also persisted.
        - Fallback: no streaming events captured (e.g. resumed checkpoint) — use final_state.
        """
        rid = uuid.UUID(request_id)
        img = final_state.get("image", {})
        comp = final_state.get("compositing", {})
        prompt_state = final_state.get("prompt", {})
        val = final_state.get("validation", {})

        if self._attempts:
            for i, attempt in enumerate(self._attempts):
                is_last = i == len(self._attempts) - 1
                # For the last attempt, use original_image_path if compositing saved a copy
                file_path = (
                    (comp.get("original_image_path") or attempt["image_path"])
                    if is_last
                    else attempt["image_path"]
                )
                session.add(GeneratedImage(
                    request_id=rid,
                    figure_id=None,
                    file_path=file_path,
                    prompt_used=attempt["prompt"],
                    provider=attempt["provider"],
                    width=512,
                    height=512,
                    validation_score=attempt["validation_score"],
                ))
            if comp.get("swapped_image_path"):
                session.add(GeneratedImage(
                    request_id=rid,
                    figure_id=None,
                    file_path=comp["swapped_image_path"],
                    prompt_used=prompt_state.get("image_prompt", ""),
                    provider="facefusion",
                    width=512,
                    height=512,
                    validation_score=val.get("validation_score"),
                ))

        elif img.get("image_path"):
            # Fallback: streaming loop missed events (e.g. resumed checkpoint)
            original_path = comp.get("original_image_path") or img["image_path"]
            session.add(GeneratedImage(
                request_id=rid,
                figure_id=None,
                file_path=original_path,
                prompt_used=prompt_state.get("image_prompt", ""),
                provider=img.get("image_provider", "mock"),
                width=512,
                height=512,
                validation_score=val.get("validation_score"),
            ))
            if comp.get("swapped_image_path"):
                session.add(GeneratedImage(
                    request_id=rid,
                    figure_id=None,
                    file_path=comp["swapped_image_path"],
                    prompt_used=prompt_state.get("image_prompt", ""),
                    provider="facefusion",
                    width=512,
                    height=512,
                    validation_score=val.get("validation_score"),
                ))
