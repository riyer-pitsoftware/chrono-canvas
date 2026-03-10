"""Historical research node — uses Google Search grounding to enrich story context."""

import logging
import time

from chronocanvas.agents.story.state import StoryState, get_runtime_config
from chronocanvas.llm.base import TaskType
from chronocanvas.llm.router import get_llm_router

logger = logging.getLogger(__name__)

RESEARCH_PROMPT = """\
You are a historical research assistant for a noir storytelling project.

Given the following story and its characters, research the historical context to ensure \
accuracy. Identify key historical facts, locations, time periods, cultural details, and \
any real events or figures referenced. Provide a concise historical context summary that \
a storytelling AI can use to generate historically grounded scenes.

STORY:
{story_text}

CHARACTERS:
{characters_summary}

SCENES:
{scenes_summary}

Provide a 2-4 paragraph historical context summary covering:
1. Time period and key historical events happening at that time
2. Cultural and social context relevant to the characters
3. Geographical/architectural details of the settings
4. Any real historical figures or events referenced, with accurate details

Be concise but specific. Focus on details that would make the visual storytelling more authentic.
"""


def _characters_summary(characters: list[dict]) -> str:
    if not characters:
        return "No specific characters identified."
    lines = []
    for c in characters:
        name = c.get("name", "Unknown")
        desc_parts = []
        if c.get("age"):
            desc_parts.append(c["age"])
        if c.get("ethnicity"):
            desc_parts.append(c["ethnicity"])
        if c.get("role"):
            desc_parts.append(c["role"])
        desc = ", ".join(desc_parts) if desc_parts else "no details"
        lines.append(f"- {name}: {desc}")
    return "\n".join(lines)


def _scenes_summary(scenes: list[dict]) -> str:
    if not scenes:
        return "No scenes decomposed yet."
    lines = []
    for s in scenes:
        idx = s.get("scene_index", "?")
        desc = s.get("description", "no description")
        setting = s.get("setting", "unknown setting")
        lines.append(f"- Scene {idx}: {desc} ({setting})")
    return "\n".join(lines)


async def historical_research_node(state: StoryState) -> StoryState:
    """Research historical context using Google Search grounding. Non-fatal on failure."""
    request_id = state.get("request_id", "unknown")
    input_text = state.get("input_text", "")
    characters = state.get("characters", [])
    scenes = state.get("scenes", [])

    logger.info("Historical research: grounding story context [request_id=%s]", request_id)

    trace = list(state.get("agent_trace", []))
    llm_calls = list(state.get("llm_calls", []))

    prompt = RESEARCH_PROMPT.format(
        story_text=input_text,
        characters_summary=_characters_summary(characters),
        scenes_summary=_scenes_summary(scenes),
    )

    rc = get_runtime_config(state)
    router = get_llm_router()

    try:
        response = await router.generate_with_search(
            prompt=prompt,
            task_type=TaskType.RESEARCH,
            request_id=request_id,
            agent_name="historical_research",
            temperature=0.3,
            max_tokens=2000,
            runtime_config=rc,
        )

        historical_context = response.content
        grounding_citations = response.metadata.get("grounding_citations", [])

        # Normalize citations to a clean format
        grounding_sources = [
            {
                "title": c.get("title", ""),
                "url": c.get("url", ""),
                "snippet": c.get("quote_snippet", ""),
            }
            for c in grounding_citations
            if c.get("url")  # only keep citations with actual URLs
        ]

        logger.info(
            "Historical research complete: %d sources found [request_id=%s]",
            len(grounding_sources),
            request_id,
        )

        trace.append(
            {
                "agent": "historical_research",
                "timestamp": time.time(),
                "sources_count": len(grounding_sources),
            }
        )

        llm_calls.append(
            {
                "agent": "historical_research",
                "timestamp": time.time(),
                "user_prompt": prompt,
                "raw_response": historical_context[:500],  # truncate for storage
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
            "current_agent": "historical_research",
            "historical_context": historical_context,
            "grounding_sources": grounding_sources,
            "agent_trace": trace,
            "llm_calls": llm_calls,
        }

    except Exception as e:
        # Non-fatal — pipeline continues without grounding
        logger.warning(
            "Historical research failed (non-fatal), continuing without grounding "
            "[request_id=%s]: %s",
            request_id,
            e,
        )
        trace.append(
            {
                "agent": "historical_research",
                "timestamp": time.time(),
                "error": str(e),
                "non_fatal": True,
            }
        )
        return {
            "current_agent": "historical_research",
            "historical_context": "",
            "grounding_sources": [],
            "agent_trace": trace,
            "llm_calls": llm_calls,
        }
