# ruff: noqa: E501 — LLM prompt template contains long natural-language lines
import json
import logging
import time

from chronocanvas.agents.state import AgentState, ValidationState
from chronocanvas.config import settings
from chronocanvas.llm.base import TaskType
from chronocanvas.llm.router import get_llm_router

logger = logging.getLogger(__name__)

VALIDATION_PROMPT = """You are a historical plausibility evaluator. Assess the following image generation
prompt for historical plausibility. Your scores are heuristic judgments, not ground-truth fact-checking.

Figure: {figure_name}
Time Period: {time_period}
Region: {region}
Life Dates: {birth_year} – {death_year}
Cultural Context: {cultural_context}
Image Prompt: {image_prompt}

Use the life dates and cultural context above to ground your plausibility assessment.
Score each category 0-100 and provide details:
{category_list}

Return JSON with:
- results: list of objects with (category, rule_name, passed, score, details, reasoning)
  where "reasoning" is 2-4 sentences explaining WHY the score was given
- overall_score: float 0-100
- overall_reasoning: 2-4 sentences summarizing the overall assessment
- passed: boolean (true if overall_score >= 70)

Respond with valid JSON only."""

# Fallback category descriptions when rule_weights don't carry descriptions
_DEFAULT_CATEGORY_DESCRIPTIONS: dict[str, str] = {
    "clothing_plausibility": "Are the clothes period-appropriate?",
    "cultural_plausibility": "Are cultural elements plausible for the setting?",
    "temporal_plausibility": "Are there anachronistic elements?",
    "artistic_plausibility": "Does the art style match the period?",
    "pose_plausibility": "Is the stance/gesture appropriate for the figure's role and era?",
    "lighting_plausibility": "Are light sources consistent with what was available in the era?",
    "color_palette_plausibility": "Are the pigments and dyes historically available for this period?",
}


def _build_category_list(rule_weights: dict[str, float]) -> str:
    """Build a numbered list of categories for the validation prompt."""
    if not rule_weights:
        rule_weights = {k: 0.25 for k in list(_DEFAULT_CATEGORY_DESCRIPTIONS)[:4]}
    lines = []
    for i, category in enumerate(rule_weights, 1):
        desc = _DEFAULT_CATEGORY_DESCRIPTIONS.get(category, f"Evaluate {category.replace('_', ' ')}")
        lines.append(f"{i}. {category}: {desc}")
    return "\n".join(lines)


async def validation_node(state: AgentState) -> AgentState:
    ext = state.get("extraction", {})
    prompt_state = state.get("prompt", {})
    val = state.get("validation", {})
    figure_name = ext.get("figure_name", "")
    logger.info(f"Validation agent: validating output for {figure_name}")

    rule_weights: dict[str, float] = val.get("rule_weights") or {}
    category_list = _build_category_list(rule_weights)

    rc = state.get("runtime_config")
    response = await get_llm_router().generate(
        prompt=VALIDATION_PROMPT.format(
            figure_name=figure_name,
            time_period=ext.get("time_period", ""),
            region=ext.get("region", ""),
            birth_year=ext.get("birth_year", "") or "unknown",
            death_year=ext.get("death_year", "") or "unknown",
            cultural_context=ext.get("cultural_context", "") or "not specified",
            image_prompt=prompt_state.get("image_prompt", ""),
            category_list=category_list,
        ),
        task_type=TaskType.VALIDATION,
        temperature=0.3,
        json_mode=True,
        agent_name="validation",
        runtime_config=rc,
    )

    try:
        data = json.loads(response.content)
    except json.JSONDecodeError:
        data = {
            "results": [
                {"category": "overall", "rule_name": "parse_error", "passed": True, "score": 75.0,
                 "details": "Could not parse validation; defaulting to pass."}
            ],
            "overall_score": 75.0,
            "passed": True,
        }

    # Use weighted scoring if rule weights are present in state; fallback to simple average
    pass_threshold: float = val.get("pass_threshold") or 70.0

    llm_overall = data.get("overall_score", 75.0)
    results_list = data.get("results", [])
    if rule_weights and results_list:
        weighted_sum = 0.0
        weight_total = 0.0
        for r in results_list:
            w = rule_weights.get(r.get("category", ""), 0.25)
            weighted_sum += r.get("score", 0.0) * w
            weight_total += w
        overall_score = weighted_sum / weight_total if weight_total > 0 else llm_overall
    else:
        overall_score = llm_overall

    passed = overall_score >= pass_threshold

    trace = state.get("agent_trace", [])
    trace.append({
        "agent": "validation",
        "timestamp": time.time(),
        "score": overall_score,
        "passed": passed,
        "llm_cost": response.cost,
    })

    llm_calls = list(state.get("llm_calls", []))
    llm_calls.append({
        "agent": "validation",
        "timestamp": time.time(),
        "system_prompt": response.system_prompt,
        "user_prompt": response.user_prompt,
        "raw_response": response.content,
        "parsed_output": data,
        "provider": response.provider,
        "model": response.model,
        "input_tokens": response.input_tokens,
        "output_tokens": response.output_tokens,
        "cost": response.cost,
        "duration_ms": response.duration_ms,
        "requested_provider": response.requested_provider,
        "fallback": response.fallback,
    })

    retry_count = state.get("retry_count", 0)
    retry_enabled = (
        rc.validation_retry_enabled if rc and rc.validation_retry_enabled is not None
        else settings.validation_retry_enabled
    )
    should_regenerate = (
        not passed
        and retry_count < 2
        and retry_enabled
    )

    return {
        "current_agent": "validation",
        "validation": ValidationState(
            validation_results=data.get("results", []),
            validation_score=overall_score,
            validation_passed=passed,
            rule_weights=rule_weights,
            pass_threshold=pass_threshold,
        ),
        "should_regenerate": should_regenerate,
        "retry_count": retry_count + (1 if should_regenerate else 0),
        "agent_trace": trace,
        "llm_calls": llm_calls,
    }
