import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from chronocanvas.api.schemas.validation import ValidationResponse, ValidationSummary
from chronocanvas.db.models.validation import ValidationResult
from chronocanvas.db.repositories.validations import ValidationRepository


def build_summary(
    request_id: uuid.UUID,
    results: list[ValidationResult],
    threshold: float,
) -> ValidationSummary:
    """Build a ValidationSummary from DB result rows and the configured pass threshold."""
    scores = [r.score for r in results] if results else [0.0]
    overall = sum(scores) / len(scores)
    return ValidationSummary(
        request_id=request_id,
        overall_score=overall,
        passed=overall >= threshold,
        results=[ValidationResponse.model_validate(r) for r in results],
    )


async def save_validation_results(
    session: AsyncSession,
    request_id: uuid.UUID,
    results: list[dict],
) -> None:
    repo = ValidationRepository(session)
    await repo.delete_by_request(request_id)
    for result in results:
        await repo.create(
            request_id=request_id,
            category=result.get("category", "general"),
            rule_name=result.get("rule_name", "unknown"),
            passed=result.get("passed", False),
            score=result.get("score", 0.0),
            details=result.get("details"),
            suggestions=result.get("suggestions", []),
        )
    await session.flush()
