import asyncio
import json
import logging
import time

from chronocanvas.agents.story.state import StoryState, get_runtime_config
from chronocanvas.llm.base import TaskType
from chronocanvas.llm.router import get_llm_router

logger = logging.getLogger(__name__)

_MAX_DECOMPOSITION_RETRIES = 3
_RETRY_BACKOFF_BASE = 1.0  # seconds

SCENE_DECOMPOSITION_PROMPT = """\
You are Dash, a noir creative director with a seen-it-all attitude and a sharp eye for \
visual storytelling. Think Dashiell Hammett meets a seasoned cinematographer — clipped, \
direct, occasionally lyrical. Every story is a crime scene; your job is to break it into \
frames that hit like a confession.

Break the following story into 3-8 distinct visual scenes suitable for image generation. \
Think in shots, not paragraphs. Every scene needs a reason to exist.

For each scene, provide:
1. A vivid visual description (2-3 sentences) — what the camera captures in this moment
2. Which characters appear in the scene — only those visibly present
3. The mood/atmosphere — noir lives in tension, shadow, and the unsaid
4. The setting/location — be specific about light, time of day, weather
5. expected_state: What this scene inherits/expects from the previous scene — character \
appearances, wardrobe, time of day, weather, lighting. For the FIRST scene, use \
{{"note": "establishing shot — no prior state"}}.
6. established_state: What this scene locks in for the next scene — character positions, \
lighting changes, mood shifts, wardrobe changes, any new props or visual elements introduced.

STORY:
{story_text}

CHARACTERS FOUND:
{characters_summary}

CHARACTER SELECTION RULES:
- Include ONLY characters who are actively present or visible in each specific scene — do NOT list all known characters for every scene.
- If the story mentions a specific subset of characters in a scene, only list those characters — not the full cast.
- Pay attention to character counts — if the story says "two of the three pigs", list only those two.

Output ONLY valid JSON in this exact format:
{{
  "scenes": [
    {{
      "scene_index": 0,
      "description": "Visual description of what is happening in this scene",
      "characters": ["Character Name 1", "Character Name 2"],
      "mood": "tense, atmospheric",
      "setting": "rain-soaked street at night",
      "expected_state": {{"note": "establishing shot — no prior state"}},
      "established_state": {{"lighting": "neon-reflected wet asphalt", "time_of_day": "night", "weather": "rain", "characters_visible": ["Character Name 1", "Character Name 2"]}}
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

    rc = get_runtime_config(state)
    router = get_llm_router()

    last_error: Exception | None = None
    for attempt in range(_MAX_DECOMPOSITION_RETRIES):
        try:
            response = await router.generate(
                prompt=prompt,
                task_type=TaskType.EXTRACTION,
                temperature=0.5,
                max_tokens=4000,
                json_mode=True,
                agent_name="scene_decomposition",
                runtime_config=rc,
            )

            # Parse JSON from response
            content = response.content
            json_start = content.find("{")
            json_end = content.rfind("}") + 1
            if json_start == -1 or json_end == 0:
                raise ValueError("No JSON found in scene decomposition response")

            parsed = json.loads(content[json_start:json_end])
            scenes = parsed.get("scenes", [])

            # Ensure scene_index is set and continuity fields have defaults
            for i, scene in enumerate(scenes):
                scene["scene_index"] = i
                if "expected_state" not in scene:
                    if i == 0:
                        scene["expected_state"] = {"note": "establishing shot — no prior state"}
                    else:
                        scene["expected_state"] = {}
                if "established_state" not in scene:
                    scene["established_state"] = {}

            logger.info("Decomposed into %d scenes [request_id=%s]", len(scenes), request_id)

            trace.append({
                "agent": "scene_decomposition",
                "timestamp": time.time(),
                "scenes_count": len(scenes),
                "retry_attempts": attempt,
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
                "retry_attempts": attempt,
            })

            return {
                "current_agent": "scene_decomposition",
                "scenes": scenes,
                "total_scenes": len(scenes),
                "agent_trace": trace,
                "llm_calls": llm_calls,
            }

        except Exception as e:
            last_error = e
            if attempt < _MAX_DECOMPOSITION_RETRIES - 1:
                backoff = _RETRY_BACKOFF_BASE * (2 ** attempt)
                logger.warning(
                    "Scene decomposition failed (attempt %d/%d), retrying in %.1fs [request_id=%s]: %s",
                    attempt + 1, _MAX_DECOMPOSITION_RETRIES, backoff, request_id, e,
                )
                await asyncio.sleep(backoff)

    # All retries exhausted
    logger.exception("Scene decomposition failed after %d attempts [request_id=%s]", _MAX_DECOMPOSITION_RETRIES, request_id)
    trace.append({
        "agent": "scene_decomposition",
        "timestamp": time.time(),
        "error": str(last_error),
        "retry_attempts": _MAX_DECOMPOSITION_RETRIES,
    })
    return {
        "current_agent": "scene_decomposition",
        "scenes": [],
        "total_scenes": 0,
        "agent_trace": trace,
        "llm_calls": llm_calls,
        "error": f"Scene decomposition failed: {last_error}",
    }
