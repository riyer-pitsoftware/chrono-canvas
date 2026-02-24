# ruff: noqa: E501 — LLM prompt template contains long natural-language lines
import json
import logging
import time

from chronocanvas.agents.state import AgentState
from chronocanvas.config import settings
from chronocanvas.llm.base import TaskType
from chronocanvas.llm.router import get_llm_router
from chronocanvas.memory.cache_service import ResearchCacheService

logger = logging.getLogger(__name__)
_cache_service = ResearchCacheService()

RESEARCH_PROMPT = """You are a historical research expert. Research the following historical figure
for the purpose of generating an accurate portrait.

Figure: {figure_name}
Time Period: {time_period}
Region: {region}
Occupation: {occupation}
Life Dates: {birth_year} – {death_year}
Known Physical Traits: {notable_features}
Cultural Context: {cultural_context}

Provide detailed information as JSON with these fields:
- historical_context: string (2-3 sentences about their life and significance)
- clothing_details: string (accurate period clothing they would wear, fabrics, colors)
- physical_description: string (known physical features, build, hair, complexion — incorporate and expand on any known traits listed above)
- art_style_reference: string (art style of their era, e.g., "Renaissance oil painting")
- sources: list of strings (reference descriptions)

Respond with valid JSON only."""


async def research_node(state: AgentState) -> AgentState:
    figure_name = state.get("figure_name", "")
    time_period = state.get("time_period", "")
    region = state.get("region", "")
    logger.info(f"Research agent: researching {figure_name}")

    cache_hit = False
    data = None
    response = None

    # Check cache first
    if settings.research_cache_enabled:
        cached_data = await _cache_service.lookup(
            figure_name, time_period, region, settings.research_cache_threshold
        )
        if cached_data:
            cache_hit = True
            data = cached_data
            logger.info(f"Research: cache hit for {figure_name}")

    # If not in cache, call LLM
    if not cache_hit:
        response = await get_llm_router().generate_stream(
            prompt=RESEARCH_PROMPT.format(
                figure_name=figure_name,
                time_period=time_period,
                region=region,
                occupation=state.get("occupation", ""),
                birth_year=state.get("birth_year", "") or "unknown",
                death_year=state.get("death_year", "") or "unknown",
                notable_features=state.get("notable_features", "") or "none recorded",
                cultural_context=state.get("cultural_context", "") or "not specified",
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
                "historical_context": f"Historical figure from {time_period or 'unknown era'}.",
                "clothing_details": "Period-appropriate attire.",
                "physical_description": "No specific physical description available.",
                "art_style_reference": "Classical portrait style.",
                "sources": [],
            }

        # Store in cache
        if settings.research_cache_enabled:
            await _cache_service.store(
                figure_name, time_period, region, data, response.cost
            )

    trace = state.get("agent_trace", [])
    trace.append({
        "agent": "research",
        "timestamp": time.time(),
        "cache_hit": cache_hit,
        **({"llm_cost": response.cost} if response else {}),
    })

    llm_calls = list(state.get("llm_calls", []))
    if response:
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
            "requested_provider": response.requested_provider,
            "fallback": response.fallback,
        })

    return {
        **state,
        "current_agent": "research",
        "research_cache_hit": cache_hit,
        "historical_context": data.get("historical_context", ""),
        "clothing_details": data.get("clothing_details", ""),
        "physical_description": data.get("physical_description", ""),
        "art_style_reference": data.get("art_style_reference", "Classical portrait"),
        "research_sources": data.get("sources", []),
        "agent_trace": trace,
        "llm_calls": llm_calls,
    }
