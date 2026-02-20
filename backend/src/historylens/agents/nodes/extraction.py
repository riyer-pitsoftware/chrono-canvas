import json
import logging
import time

from historylens.agents.state import AgentState
from historylens.llm.base import TaskType
from historylens.llm.router import llm_router

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """Extract historical figure information from the following text.
Return a JSON object with these fields:
- figure_name: string (full name of the historical figure)
- time_period: string (era or century)
- region: string (geographic region/country)
- occupation: string (primary role or title)
- attributes: object (any additional attributes mentioned)

Text: {input_text}

Respond with valid JSON only."""


async def extraction_node(state: AgentState) -> AgentState:
    logger.info("Extraction agent: extracting figure details")

    input_text = state.get("input_text", "")

    response = await llm_router.generate(
        prompt=EXTRACTION_PROMPT.format(input_text=input_text),
        task_type=TaskType.EXTRACTION,
        temperature=0.3,
        json_mode=True,
    )

    try:
        data = json.loads(response.content)
    except json.JSONDecodeError:
        data = {
            "figure_name": input_text.strip(),
            "time_period": "Unknown",
            "region": "Unknown",
            "occupation": "Historical figure",
            "attributes": {},
        }

    trace = state.get("agent_trace", [])
    trace.append({
        "agent": "extraction",
        "timestamp": time.time(),
        "extracted": data,
        "llm_cost": response.cost,
    })

    llm_calls = list(state.get("llm_calls", []))
    llm_calls.append({
        "agent": "extraction",
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
        "current_agent": "extraction",
        "figure_name": data.get("figure_name", input_text),
        "time_period": data.get("time_period", "Unknown"),
        "region": data.get("region", "Unknown"),
        "occupation": data.get("occupation", "Historical figure"),
        "extracted_attributes": data.get("attributes", {}),
        "agent_trace": trace,
        "llm_calls": llm_calls,
    }
