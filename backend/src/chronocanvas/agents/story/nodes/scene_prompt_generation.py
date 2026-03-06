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

CHARACTER VISUAL ANCHORS (copy word-for-word into your prompt):
{character_details}

Requirements:
- Write in natural, descriptive prose — NOT comma-separated tags or weight syntax like (feature:1.2)
- Write 100-200 words describing exactly what a camera would capture in this moment
- You MUST include each character's Visual Anchor description word-for-word. Do not paraphrase.
- The MOOD tag MUST be the primary driver of character expressions, body language, and lighting. For 'humorous': characters smile/laugh, bright warm lighting, playful composition. For 'tense': characters show worry, dramatic shadows, tight framing. For 'sad': downcast eyes, muted colors, soft diffused light. Map every mood to specific visual cues — expressions, posture, lighting quality, and color temperature.
- Every character must maintain IDENTICAL physical proportions, skin tone, and facial features across all scenes
- Describe character heights relative to each other — maintain these ratios
- Use consistent camera distance and framing conventions for recurring characters
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
- Match the mood tag to character expressions, lighting, and atmosphere
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


CHARACTER_ANCHOR_PROMPT = """\
You are a character design consultant for a visual storyboard. Given the character data below, \
produce a canonical Visual Anchor for each character — a precise 2-3 sentence physical description \
that an image generator can reproduce identically across multiple scenes.

For each character, specify:
- Exact height descriptor relative to other characters (e.g. "noticeably taller than X", "same height as Y")
- Body build (slim, stocky, muscular, etc.)
- Exact skin tone (use specific descriptors like "deep brown", "pale olive", "warm tan")
- Hair: style, length, color (be precise — "shoulder-length wavy auburn hair")
- Distinguishing marks or features (scars, glasses, jewelry, tattoos)
- Clothing: assign gender-appropriate clothing based on the character's gender, cultural context, and time period. Be specific about garment types (e.g., "fitted bodice with flowing skirt" vs "tailored waistcoat with trousers"). Include specific fabrics, colors, and fit.

CHARACTERS:
{character_json}

Output ONLY valid JSON — a list of objects:
[
  {{"name": "CharName", "visual_anchor": "2-3 sentence canonical description..."}}
]"""


async def _build_character_anchors(
    characters: list[dict],
    router,
    request_id: str,
    runtime_config=None,
) -> tuple[dict[str, str], dict | None]:
    """Generate canonical visual anchor descriptions for all characters.

    Returns (name→anchor mapping, llm_call_record or None).
    """
    if not characters:
        return {}, None

    char_json = json.dumps(
        [{k: v for k, v in c.items() if k != "visual_anchor"} for c in characters],
        indent=2,
    )
    prompt = CHARACTER_ANCHOR_PROMPT.format(character_json=char_json)

    try:
        response = await router.generate(
            prompt=prompt,
            task_type=TaskType.PROMPT_GENERATION,
            temperature=0.3,
            max_tokens=4000,
            json_mode=True,
            agent_name="character_anchor_generation",
            runtime_config=runtime_config,
        )

        content = response.content
        json_start = content.find("[")
        json_end = content.rfind("]") + 1
        anchors_list = json.loads(content[json_start:json_end])

        anchors = {a["name"]: a["visual_anchor"] for a in anchors_list if "name" in a}

        llm_record = {
            "agent": "character_anchor_generation",
            "timestamp": time.time(),
            "user_prompt": prompt,
            "raw_response": content,
            "parsed_output": anchors,
            "provider": response.provider,
            "model": response.model,
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
            "cost": response.cost,
            "duration_ms": response.duration_ms,
            "requested_provider": response.requested_provider,
            "fallback": response.fallback,
        }
        return anchors, llm_record

    except Exception as e:
        logger.warning(
            "Character anchor generation failed [request_id=%s]: %s",
            request_id, e,
        )
        return {}, None


def _character_details(characters_in_scene: list[str], all_characters: list[dict]) -> str:
    """Build character detail block, preferring visual_anchor if available."""
    char_map = {c.get("name", ""): c for c in all_characters}
    lines = []
    for name in characters_in_scene:
        char = char_map.get(name)
        if char:
            if char.get("visual_anchor"):
                lines.append(f"- {name} [Visual Anchor]: {char['visual_anchor']}")
            else:
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
    reference_context: str = "",
    runtime_config=None,
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
    if reference_context:
        prompt += reference_context

    try:
        response = await router.generate(
            prompt=prompt,
            task_type=TaskType.PROMPT_GENERATION,
            temperature=0.7,
            max_tokens=4000,
            json_mode=True,
            agent_name="scene_prompt_generation",
            runtime_config=runtime_config,
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


def _build_reference_context(reference_analysis: list[dict]) -> str:
    """Build a reference image context block for scene prompt generation."""
    if not reference_analysis:
        return ""
    lines = ["\nREFERENCE IMAGE ANALYSIS (match these visual qualities):"]
    for analysis in reference_analysis:
        style = analysis.get("visual_style", "")
        palette = ", ".join(analysis.get("color_palette", []))
        integration = analysis.get("suggested_integration", "")
        if style:
            lines.append(f"- Visual style: {style}")
        if palette:
            lines.append(f"- Color palette: {palette}")
        if integration:
            lines.append(f"- Integration: {integration}")
    return "\n".join(lines)


async def scene_prompt_generation_node(state: StoryState) -> StoryState:
    request_id = state.get("request_id", "unknown")
    scenes = state.get("scenes", [])
    characters = state.get("characters", [])
    reference_analysis = state.get("reference_analysis", [])
    logger.info(
        "Scene prompt generation: creating prompts for %d scenes in parallel [request_id=%s]",
        len(scenes), request_id,
    )

    trace = list(state.get("agent_trace", []))
    llm_calls = list(state.get("llm_calls", []))

    rc = state.get("runtime_config")
    router = get_llm_router()

    # Build canonical visual anchors for all characters (one LLM call)
    anchors, anchor_llm_record = await _build_character_anchors(
        characters, router, request_id, runtime_config=rc,
    )
    if anchor_llm_record:
        llm_calls.append(anchor_llm_record)

    # Inject visual anchors into character dicts
    for char in characters:
        name = char.get("name", "")
        if name in anchors:
            char["visual_anchor"] = anchors[name]

    trace.append({
        "agent": "character_anchor_generation",
        "timestamp": time.time(),
        "anchors_generated": len(anchors),
        "character_names": list(anchors.keys()),
    })

    # Determine which scenes to generate (all, or only regen targets)
    regen_scenes = state.get("regen_scenes", [])
    if regen_scenes:
        target_scenes = [s for s in scenes if s.get("scene_index") in regen_scenes]
        logger.info(
            "Regenerating prompts for %d scenes: %s [request_id=%s]",
            len(target_scenes), regen_scenes, request_id,
        )
    else:
        target_scenes = scenes

    # Build reference context from analysis (if any)
    ref_context = _build_reference_context(reference_analysis)

    # Generate all scene prompts concurrently
    results = await asyncio.gather(*(
        _generate_prompt_for_scene(scene, characters, router, request_id, ref_context, runtime_config=rc)
        for scene in target_scenes
    ))

    # Collect results — merge with existing panels if regenerating
    existing_panels = list(state.get("panels", []))
    new_panels: list[StoryPanel] = []
    for panel, llm_record in results:
        new_panels.append(panel)
        if llm_record:
            llm_calls.append(llm_record)

    if regen_scenes and existing_panels:
        # Replace only the regenerated scenes in the existing panel list
        regen_map = {p["scene_index"]: p for p in new_panels}
        panels = [
            regen_map.get(p.get("scene_index"), p)
            for p in existing_panels
        ]
    else:
        panels = new_panels

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
        "regen_scenes": [],  # clear after processing
    }
