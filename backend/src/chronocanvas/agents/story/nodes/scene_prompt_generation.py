import asyncio
import json
import logging
import time

from chronocanvas.agents.story.state import StoryPanel, StoryState
from chronocanvas.config import settings
from chronocanvas.llm.base import TaskType
from chronocanvas.llm.router import get_llm_router

logger = logging.getLogger(__name__)

# ── Imagen scene prompt template (natural language for photorealism) ──────────

IMAGEN_SCENE_PROMPT_TEMPLATE = """\
You are an expert at writing image generation prompts for Google Imagen, which produces photorealistic images from natural-language descriptions.

Generate a vivid, detailed prompt for the following scene from a story. The goal is a photorealistic, cinematic still frame.

SCENE DESCRIPTION: {description}
CHARACTERS IN SCENE: {characters}
MOOD: {mood}
SETTING: {setting}

CHARACTER DETAILS:
{character_details}

Requirements:
- Write in natural, descriptive prose — NOT comma-separated tags or weight syntax like (feature:1.2)
- Write 80-150 words describing exactly what a camera would capture in this moment
- Describe each character's physical appearance in detail: exact skin tone, facial features, body type, expression, posture, clothing fabrics and colors
- Specify the camera setup: lens focal length, angle (low/high/eye-level), framing (close-up/medium/wide), depth of field
- Specify lighting precisely: direction, quality (hard/soft), color temperature, shadows
- Describe the environment and atmosphere with sensory detail
- End with: "Cinematic still photograph, professional DSLR, RAW quality, 8K resolution, natural skin texture with visible pores"

Also provide a negative prompt to exclude unwanted elements.

Output ONLY valid JSON:
{{
  "image_prompt": "the detailed positive prompt...",
  "negative_prompt": "low quality, blurry, deformed, cartoon, illustration, painting, 3d render, plastic skin, airbrushed"
}}"""

# ── SDXL scene prompt template (weighted tags for ComfyUI/SD) ────────────────

SDXL_SCENE_PROMPT_TEMPLATE = """\
You are an expert at crafting image generation prompts for Stable Diffusion XL.

Generate a detailed image generation prompt for the following scene from a story.

SCENE DESCRIPTION: {description}
CHARACTERS IN SCENE: {characters}
MOOD: {mood}
SETTING: {setting}

CHARACTER DETAILS:
{character_details}

Requirements:
- Write a single detailed paragraph (80-120 words) describing the visual scene
- Include specific details about lighting, camera angle, composition
- Include character appearances if they are in the scene
- Style: cinematic, atmospheric, high detail, photorealistic
- End with quality tags: masterpiece, best quality, highly detailed, 8k

Also provide a negative prompt to exclude unwanted elements.

Output ONLY valid JSON:
{{
  "image_prompt": "the detailed positive prompt...",
  "negative_prompt": "low quality, blurry, deformed..."
}}"""


def _get_scene_prompt_template() -> str:
    """Select scene prompt template based on configured image provider."""
    if settings.image_provider == "imagen":
        return IMAGEN_SCENE_PROMPT_TEMPLATE
    return SDXL_SCENE_PROMPT_TEMPLATE


def _character_details(characters_in_scene: list[str], all_characters: list[dict]) -> str:
    char_map = {c.get("name", ""): c for c in all_characters}
    lines = []
    for name in characters_in_scene:
        char = char_map.get(name)
        if char:
            parts = []
            if char.get("age"):
                parts.append(f"age: {char['age']}")
            if char.get("ethnicity"):
                parts.append(f"ethnicity: {char['ethnicity']}")
            if char.get("gender"):
                parts.append(f"gender: {char['gender']}")
            if char.get("clothing"):
                parts.append(f"clothing: {char['clothing']}")
            if char.get("facial_features"):
                features = char["facial_features"]
                if isinstance(features, list):
                    parts.append(f"features: {', '.join(features)}")
            lines.append(f"- {name}: {', '.join(parts)}")
        else:
            lines.append(f"- {name}: (no details available)")
    return "\n".join(lines) if lines else "No specific character details."


async def _generate_prompt_for_scene(
    scene: dict,
    characters: list[dict],
    router,
    request_id: str,
) -> tuple[StoryPanel, dict | None]:
    """Generate prompt for a single scene. Returns (panel, llm_call_record)."""
    scene_index = scene.get("scene_index", 0)
    scene_chars = scene.get("characters", [])

    prompt = _get_scene_prompt_template().format(
        description=scene.get("description", ""),
        characters=", ".join(scene_chars) if scene_chars else "none",
        mood=scene.get("mood", ""),
        setting=scene.get("setting", ""),
        character_details=_character_details(scene_chars, characters),
    )

    try:
        response = await router.generate(
            prompt=prompt,
            task_type=TaskType.PROMPT_GENERATION,
            temperature=0.7,
            max_tokens=1000,
            json_mode=True,
            agent_name="scene_prompt_generation",
        )

        content = response.content
        json_start = content.find("{")
        json_end = content.rfind("}") + 1
        parsed = json.loads(content[json_start:json_end])

        panel: StoryPanel = {
            "scene_index": scene_index,
            "description": scene.get("description", ""),
            "characters": scene_chars,
            "mood": scene.get("mood", ""),
            "setting": scene.get("setting", ""),
            "image_prompt": parsed.get("image_prompt", ""),
            "negative_prompt": parsed.get(
                "negative_prompt",
                "low quality, blurry, deformed, ugly, bad anatomy",
            ),
            "image_path": "",
            "status": "pending",
        }

        llm_record = {
            "agent": "scene_prompt_generation",
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
        }
        return panel, llm_record

    except Exception as e:
        logger.warning(
            "Prompt generation failed for scene %d [request_id=%s]: %s",
            scene_index, request_id, e,
        )
        panel = {
            "scene_index": scene_index,
            "description": scene.get("description", ""),
            "characters": scene_chars,
            "mood": scene.get("mood", ""),
            "setting": scene.get("setting", ""),
            "image_prompt": "",
            "negative_prompt": "",
            "image_path": "",
            "status": "failed",
            "error": str(e),
        }
        return panel, None


async def scene_prompt_generation_node(state: StoryState) -> StoryState:
    request_id = state.get("request_id", "unknown")
    scenes = state.get("scenes", [])
    characters = state.get("characters", [])
    logger.info(
        "Scene prompt generation: creating prompts for %d scenes in parallel [request_id=%s]",
        len(scenes), request_id,
    )

    trace = list(state.get("agent_trace", []))
    llm_calls = list(state.get("llm_calls", []))

    router = get_llm_router()

    # Generate all scene prompts concurrently
    results = await asyncio.gather(*(
        _generate_prompt_for_scene(scene, characters, router, request_id)
        for scene in scenes
    ))

    # Collect results in scene order
    panels: list[StoryPanel] = []
    for panel, llm_record in results:
        panels.append(panel)
        if llm_record:
            llm_calls.append(llm_record)

    trace.append({
        "agent": "scene_prompt_generation",
        "timestamp": time.time(),
        "panels_created": len(panels),
        "panels_ok": sum(1 for p in panels if p.get("status") == "pending"),
    })

    return {
        "current_agent": "scene_prompt_generation",
        "panels": panels,
        "agent_trace": trace,
        "llm_calls": llm_calls,
    }
