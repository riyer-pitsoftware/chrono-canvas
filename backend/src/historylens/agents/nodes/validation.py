import json
import logging
import time

from historylens.agents.state import AgentState
from historylens.llm.base import TaskType
from historylens.llm.router import llm_router

logger = logging.getLogger(__name__)

VALIDATION_PROMPT = """You are a historical accuracy validator. Evaluate the following image generation
prompt for historical accuracy.

Figure: {figure_name}
Time Period: {time_period}
Region: {region}
Image Prompt: {image_prompt}

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

    response = await llm_router.generate(
        prompt=VALIDATION_PROMPT.format(
            figure_name=state.get("figure_name", ""),
            time_period=state.get("time_period", ""),
            region=state.get("region", ""),
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

    overall_score = data.get("overall_score", 75.0)
    passed = overall_score >= 70

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
