import json
import logging
import time

from chronocanvas.agents.state import AgentState
from chronocanvas.llm.base import TaskType
from chronocanvas.llm.router import llm_router

logger = logging.getLogger(__name__)

RESEARCH_PROMPT = """You are a historical research expert. Research the following historical figure
for the purpose of generating an accurate portrait.

Figure: {figure_name}
Time Period: {time_period}
Region: {region}
Occupation: {occupation}

Provide detailed information as JSON with these fields:
- historical_context: string (2-3 sentences about their life and significance)
- clothing_details: string (accurate period clothing they would wear, fabrics, colors)
- physical_description: string (known physical features, build, hair, complexion)
- art_style_reference: string (art style of their era, e.g., "Renaissance oil painting")
- sources: list of strings (reference descriptions)

Respond with valid JSON only."""


async def research_node(state: AgentState) -> AgentState:
    logger.info(f"Research agent: researching {state.get('figure_name', 'unknown')}")

    response = await llm_router.generate_stream(
        prompt=RESEARCH_PROMPT.format(
            figure_name=state.get("figure_name", ""),
            time_period=state.get("time_period", ""),
            region=state.get("region", ""),
            occupation=state.get("occupation", ""),
        ),
        task_type=TaskType.RESEARCH,
        request_id=state.get("request_id", ""),
        agent_name="research",
        temperature=0.5,
        max_tokens=3000,
        json_mode=True,
    )

    try:
        data = json.loads(response.content)
    except json.JSONDecodeError:
        data = {
            "historical_context": f"Historical figure from {state.get('time_period', 'unknown era')}.",
            "clothing_details": "Period-appropriate attire.",
            "physical_description": "No specific physical description available.",
            "art_style_reference": "Classical portrait style.",
            "sources": [],
        }

    trace = state.get("agent_trace", [])
    trace.append({
        "agent": "research",
        "timestamp": time.time(),
        "llm_cost": response.cost,
    })

    llm_calls = list(state.get("llm_calls", []))
    llm_calls.append({
        "agent": "research",
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

    return {
        **state,
        "current_agent": "research",
        "historical_context": data.get("historical_context", ""),
        "clothing_details": data.get("clothing_details", ""),
        "physical_description": data.get("physical_description", ""),
        "art_style_reference": data.get("art_style_reference", "Classical portrait"),
        "research_sources": data.get("sources", []),
        "agent_trace": trace,
        "llm_calls": llm_calls,
    }
