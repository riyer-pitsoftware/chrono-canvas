"""Projection logic for building the admin validation review queue."""

from __future__ import annotations

from chronocanvas.api.schemas.admin import (
    ValidationQueueCategory,
    ValidationQueueItem,
    ValidationQueueResponse,
)
from chronocanvas.db.models.image import GeneratedImage
from chronocanvas.db.models.request import GenerationRequest
from chronocanvas.db.models.validation import ValidationResult
from chronocanvas.services.path_utils import file_path_to_url
from chronocanvas.services.validation import compute_validation_overall


class ValidationQueueProjector:
    """Builds ValidationQueueResponse from DB models."""

    def build_item(
        self,
        req: GenerationRequest,
        val_rows: list[ValidationResult],
        threshold: float,
        img: GeneratedImage | None,
        *,
        enforce_threshold: bool = True,
    ) -> ValidationQueueItem | None:
        """Return None if the request passes the threshold (not in review queue)."""
        if not val_rows:
            return None

        scores = [r.score for r in val_rows]
        overall = compute_validation_overall(scores)
        if enforce_threshold and overall >= threshold:
            return None

        figure_name: str | None = None
        if req.extracted_data and isinstance(req.extracted_data, dict):
            figure_name = req.extracted_data.get("figure_name")

        categories = [
            ValidationQueueCategory(
                category=r.category,
                rule_name=r.rule_name,
                score=r.score,
                passed=r.passed,
                details=r.details,
            )
            for r in val_rows
        ]

        return ValidationQueueItem(
            request_id=req.id,
            input_text=req.input_text,
            figure_name=figure_name,
            overall_score=round(overall, 1),
            categories=categories,
            image_url=file_path_to_url(img.file_path) if img else None,
            human_review_status=req.human_review_status,
            created_at=req.created_at,
        )

    def build_response(self, items: list[ValidationQueueItem]) -> ValidationQueueResponse:
        return ValidationQueueResponse(items=items, total=len(items))
