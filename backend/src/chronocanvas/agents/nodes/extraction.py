# ruff: noqa: E501 — LLM prompt template contains long natural-language lines
import json
import logging
import time

from chronocanvas.agents.state import AgentState, ExtractionState
from chronocanvas.llm.base import TaskType
from chronocanvas.llm.router import get_llm_router

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """Extract comprehensive historical figure information from the following text.
Return a JSON object with these fields:
- figure_name: string (full canonical name of the historical figure)
- time_period: string (era or century, e.g. "15th century" or "Renaissance era")
- region: string (geographic region/country)
- occupation: string (primary role or title)
- alternative_names: list of strings (aliases, nicknames, titles, transliterations, e.g. ["Cleopatra VII Philopator", "Queen of the Nile"])
- birth_year: string (specific or approximate, e.g. "69 BC" or "c. 1450")
- death_year: string (specific or approximate, e.g. "30 BC" or "c. 1519")
- notable_features: string (known physical characteristics — scars, height, complexion, distinctive traits)
- cultural_context: string (religion, social class, dynasty, movement, or cultural milieu)
- historical_significance: string (1-2 sentences on why this figure matters historically)
- associated_locations: list of strings (cities, courts, battlefields, kingdoms associated with them)
- attributes: object (any additional attributes not covered above)

Text: {input_text}

Respond with valid JSON only."""


async def extraction_node(state: AgentState) -> AgentState:
    logger.info("Extraction agent: extracting figure details")

    input_text = state.get("input_text", "")

    rc = state.get("runtime_config")
    response = await get_llm_router().generate(
        prompt=EXTRACTION_PROMPT.format(input_text=input_text),
        task_type=TaskType.EXTRACTION,
        temperature=0.3,
        json_mode=True,
        agent_name="extraction",
        runtime_config=rc,
    )

    try:
        data = json.loads(response.content)
    except json.JSONDecodeError:
        data = {
            "figure_name": input_text.strip(),
            "time_period": "Unknown",
            "region": "Unknown",
            "occupation": "Historical figure",
            "alternative_names": [],
            "birth_year": "",
            "death_year": "",
            "notable_features": "",
            "cultural_context": "",
            "historical_significance": "",
            "associated_locations": [],
            "attributes": {},
        }

    # Ensure figure_name is never empty — fall back to raw input
    if not data.get("figure_name"):
        data["figure_name"] = input_text.strip() or "Unknown Figure"

    trace = state.get("agent_trace", [])
    trace.append(
        {
            "agent": "extraction",
            "timestamp": time.time(),
            "extracted": data,
            "llm_cost": response.cost,
        }
    )

    llm_calls = list(state.get("llm_calls", []))
    llm_calls.append(
        {
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
            "requested_provider": response.requested_provider,
            "fallback": response.fallback,
        }
    )

    return {
        "current_agent": "extraction",
        "extraction": ExtractionState(
            figure_name=data.get("figure_name", input_text),
            time_period=data.get("time_period", "Unknown"),
            region=data.get("region", "Unknown"),
            occupation=data.get("occupation", "Historical figure"),
            extracted_attributes=data.get("attributes", {}),
            alternative_names=data.get("alternative_names", []),
            birth_year=data.get("birth_year", ""),
            death_year=data.get("death_year", ""),
            notable_features=data.get("notable_features", ""),
            cultural_context=data.get("cultural_context", ""),
            historical_significance=data.get("historical_significance", ""),
            associated_locations=data.get("associated_locations", []),
        ),
        "agent_trace": trace,
        "llm_calls": llm_calls,
    }
