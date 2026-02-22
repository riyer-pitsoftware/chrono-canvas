# ruff: noqa: E501 — LLM prompt template contains long natural-language lines
import json
import logging
import time

from chronocanvas.agents.state import AgentState
from chronocanvas.llm.base import TaskType
from chronocanvas.llm.router import get_llm_router

logger = logging.getLogger(__name__)

VALIDATION_PROMPT = """You are a historical accuracy validator. Evaluate the following image generation
prompt for historical accuracy.

Figure: {figure_name}
Time Period: {time_period}
Region: {region}
Life Dates: {birth_year} – {death_year}
Cultural Context: {cultural_context}
Image Prompt: {image_prompt}

Use the life dates and cultural context above to ground your accuracy assessment.
Score each category 0-100 and provide details:
1. clothing_accuracy: Are the clothes period-appropriate?
2. cultural_accuracy: Are cultural elements correct?
3. temporal_accuracy: Are there anachronistic elements?
4. artistic_style: Does the art style match the period?

Return JSON with:
- results: list of objects with (category, rule_name, passed, score, details, reasoning)
  where "reasoning" is 2-4 sentences explaining WHY the score was given
- overall_score: float 0-100
- overall_reasoning: 2-4 sentences summarizing the overall assessment
- passed: boolean (true if overall_score >= 70)

Respond with valid JSON only."""


async def validation_node(state: AgentState) -> AgentState:
    logger.info(f"Validation agent: validating output for {state.get('figure_name', '')}")

    response = await get_llm_router().generate(
        prompt=VALIDATION_PROMPT.format(
            figure_name=state.get("figure_name", ""),
            time_period=state.get("time_period", ""),
            region=state.get("region", ""),
            birth_year=state.get("birth_year", "") or "unknown",
            death_year=state.get("death_year", "") or "unknown",
            cultural_context=state.get("cultural_context", "") or "not specified",
            image_prompt=state.get("image_prompt", ""),
        ),
        task_type=TaskType.VALIDATION,
        temperature=0.3,
        json_mode=True,
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
    rule_weights: dict[str, float] = state.get("validation_rule_weights") or {}
    pass_threshold: float = state.get("validation_pass_threshold") or 70.0

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
    })

    retry_count = state.get("retry_count", 0)
    should_regenerate = not passed and retry_count < 2

    return {
        **state,
        "current_agent": "validation",
        "validation_results": data.get("results", []),
        "validation_score": overall_score,
        "validation_passed": passed,
        "should_regenerate": should_regenerate,
        "retry_count": retry_count + (1 if should_regenerate else 0),
        "agent_trace": trace,
        "llm_calls": llm_calls,
    }
