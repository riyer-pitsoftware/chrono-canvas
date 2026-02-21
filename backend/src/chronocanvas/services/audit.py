"""Projection logic for building AuditDetailResponse from DB models."""

from __future__ import annotations

from chronocanvas.api.schemas.generation import (
    AuditDetailResponse,
    ImageResponse,
    LLMCallDetail,
    StateSnapshot,
    ValidationCategoryDetail,
)
from chronocanvas.db.models.image import GeneratedImage
from chronocanvas.db.models.request import GenerationRequest


class AuditProjector:
    """Builds AuditDetailResponse from a GenerationRequest and its images."""

    def project(
        self,
        request: GenerationRequest,
        images: list[GeneratedImage],
    ) -> AuditDetailResponse:
        raw_calls = request.llm_calls or []
        llm_calls = [LLMCallDetail(**c) for c in raw_calls]
        total_cost = sum(c.cost for c in llm_calls)
        total_duration = sum(c.duration_ms for c in llm_calls)

        validation_score = None
        validation_passed = None
        validation_reasoning = None
        validation_categories: list[ValidationCategoryDetail] = []

        for call in reversed(raw_calls):
            if call.get("agent") == "validation" and isinstance(call.get("parsed_output"), dict):
                parsed = call["parsed_output"]
                validation_score = parsed.get("overall_score")
                validation_passed = parsed.get("passed")
                validation_reasoning = parsed.get("overall_reasoning")
                for r in parsed.get("results", []):
                    validation_categories.append(
                        ValidationCategoryDetail(
                            category=r.get("category", ""),
                            rule_name=r.get("rule_name", ""),
                            passed=r.get("passed", False),
                            score=r.get("score", 0.0),
                            details=r.get("details"),
                            reasoning=r.get("reasoning"),
                        )
                    )
                break

        figure_name = None
        if request.extracted_data:
            figure_name = request.extracted_data.get("figure_name")

        state_snapshots = [
            StateSnapshot(agent=entry["agent"], snapshot=entry["state_snapshot"])
            for entry in (request.agent_trace or [])
            if "state_snapshot" in entry
        ]

        return AuditDetailResponse(
            id=request.id,
            input_text=request.input_text,
            status=request.status,
            current_agent=request.current_agent,
            figure_name=figure_name,
            created_at=request.created_at,
            updated_at=request.updated_at,
            extracted_data=request.extracted_data,
            research_data=request.research_data,
            generated_prompt=request.generated_prompt,
            error_message=request.error_message,
            total_cost=total_cost,
            total_duration_ms=total_duration,
            llm_calls=llm_calls,
            validation_score=validation_score,
            validation_passed=validation_passed,
            validation_reasoning=validation_reasoning,
            validation_categories=validation_categories,
            images=[ImageResponse.model_validate(img) for img in images],
            state_snapshots=state_snapshots,
            agent_trace=request.agent_trace or [],
        )
