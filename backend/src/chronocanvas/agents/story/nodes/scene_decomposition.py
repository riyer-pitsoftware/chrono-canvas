import json
import logging
import time

from chronocanvas.agents.story.state import StoryState
from chronocanvas.llm.base import TaskType
from chronocanvas.llm.router import get_llm_router

logger = logging.getLogger(__name__)

SCENE_DECOMPOSITION_PROMPT = """\
You are a visual storyboard planner. \
Break the following story into 3-8 distinct visual scenes suitable for image generation.

For each scene, provide:
1. A vivid visual description (2-3 sentences) focusing on what would be seen in an image
2. Which characters appear in the scene
3. The mood/atmosphere
4. The setting/location

STORY:
{story_text}

CHARACTERS FOUND:
{characters_summary}

Output ONLY valid JSON in this exact format:
{{
  "scenes": [
    {{
      "scene_index": 0,
      "description": "Visual description of what is happening in this scene",
      "characters": ["Character Name 1", "Character Name 2"],
      "mood": "tense, atmospheric",
      "setting": "rain-soaked street at night"
    }}
  ]
}}"""


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
        if c.get("gender"):
            desc_parts.append(c["gender"])
        if c.get("clothing"):
            desc_parts.append(f'wearing {c["clothing"]}')
        desc = ", ".join(desc_parts) if desc_parts else "no details"
        lines.append(f"- {name}: {desc}")
    return "\n".join(lines)


async def scene_decomposition_node(state: StoryState) -> StoryState:
    request_id = state.get("request_id", "unknown")
    input_text = state.get("input_text", "")
    characters = state.get("characters", [])
    logger.info("Scene decomposition: processing [request_id=%s]", request_id)

    trace = list(state.get("agent_trace", []))
    llm_calls = list(state.get("llm_calls", []))

    prompt = SCENE_DECOMPOSITION_PROMPT.format(
        story_text=input_text,
        characters_summary=_characters_summary(characters),
    )

    try:
        router = get_llm_router()
        response = await router.generate(
            prompt=prompt,
            task_type=TaskType.EXTRACTION,
            temperature=0.5,
            max_tokens=4000,
            json_mode=True,
        )

        # Parse JSON from response
        content = response.content
        json_start = content.find("{")
        json_end = content.rfind("}") + 1
        if json_start == -1 or json_end == 0:
            raise ValueError("No JSON found in scene decomposition response")

        parsed = json.loads(content[json_start:json_end])
        scenes = parsed.get("scenes", [])

        # Ensure scene_index is set
        for i, scene in enumerate(scenes):
            scene["scene_index"] = i

        logger.info("Decomposed into %d scenes [request_id=%s]", len(scenes), request_id)

        trace.append({
            "agent": "scene_decomposition",
            "timestamp": time.time(),
            "scenes_count": len(scenes),
        })

        llm_calls.append({
            "agent": "scene_decomposition",
            "timestamp": time.time(),
            "user_prompt": prompt,
            "raw_response": content,
            "parsed_output": parsed,
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
            "current_agent": "scene_decomposition",
            "scenes": scenes,
            "total_scenes": len(scenes),
            "agent_trace": trace,
            "llm_calls": llm_calls,
        }

    except Exception as e:
        logger.exception("Scene decomposition failed [request_id=%s]", request_id)
        trace.append({
            "agent": "scene_decomposition",
            "timestamp": time.time(),
            "error": str(e),
        })
        return {
            "current_agent": "scene_decomposition",
            "scenes": [],
            "total_scenes": 0,
            "agent_trace": trace,
            "llm_calls": llm_calls,
            "error": f"Scene decomposition failed: {e}",
        }
