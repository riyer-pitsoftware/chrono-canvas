import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from historylens.db.repositories.validations import ValidationRepository


async def save_validation_results(
    session: AsyncSession,
    request_id: uuid.UUID,
    results: list[dict],
) -> None:
    repo = ValidationRepository(session)
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
