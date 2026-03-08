"""Narration script node — generates cinematic voiceover text per panel.

When vision_narration_enabled=True and panel images exist, uses Gemini multimodal
to produce narration that references actual visual details in the images.
Falls back to text-only LLM router when images are unavailable or vision is disabled.

Non-fatal: if the LLM call fails, panels continue without narration text.
"""

import json
import logging
import time
from pathlib import Path

from chronocanvas.agents.story.state import StoryState, get_runtime_config
from chronocanvas.config import settings
from chronocanvas.llm.base import TaskType
from chronocanvas.llm.router import get_llm_router

logger = logging.getLogger(__name__)

NARRATION_SCRIPT_PROMPT = """\
You are Dash, a noir creative director narrating a visual storyboard. Write in the \
noir literary tradition — Hammett's economy, Chandler's poetry, every word earning \
its keep. Short sentences. Rhythmic. Punchy. The kind of voice that sounds like \
cigarette smoke and rain on a window.

For each scene below, write a short, evocative narration (1-3 sentences) that a \
narrator would speak over the image.  The narration should:
- Complement — not repeat — the visual description
- Set mood and atmosphere through tone and word choice — shadows, moral ambiguity, the unsaid
- Flow naturally from one scene to the next when read in sequence
- Be concise enough to read aloud in under 15 seconds per scene
- Sound like a character speaking, not a textbook describing

SCENES:
{scenes_json}

Output ONLY valid JSON:
{{
  "narrations": [
    {{"scene_index": 0, "narration_text": "The narration for scene 0..."}},
    {{"scene_index": 1, "narration_text": "The narration for scene 1..."}}
  ]
}}"""

VISION_NARRATION_SYSTEM_PROMPT = """\
You are Dash, a noir creative director narrating a visual storyboard. You can SEE \
the actual images. Write in the noir tradition — clipped, direct, occasionally lyrical. \
Hammett's economy, Chandler's poetry. Every word earns its keep.

Write narration that references specific visual details you observe — the way shadows \
fall, the tension in a posture, the color of light through a window.

For each scene, write a short, evocative narration (1-3 sentences) that a narrator \
would speak over the image. The narration should:
- Describe visual details you actually see in the image — shadows, light, composition
- Set mood through noir sensibility — tension, moral ambiguity, atmosphere
- Flow naturally from one scene to the next when read in sequence
- Be concise enough to read aloud in under 15 seconds per scene
- Sound like it belongs in a film noir voiceover, not a documentary

Output ONLY valid JSON:
{
  "narrations": [
    {"scene_index": 0, "narration_text": "The narration for scene 0..."},
    {"scene_index": 1, "narration_text": "The narration for scene 1..."}
  ]
}"""


async def _vision_narration(panels: list[dict], request_id: str) -> tuple[dict[int, str], dict]:
    """Use Gemini multimodal to generate narration from actual images."""
    from google import genai
    from google.genai import types
    from chronocanvas.llm.providers.gemini import GEMINI_PRICING, gemini_generate_with_timeout

    parts: list[types.Part] = []

    # Batch scenes in groups — include both text context and images
    for panel in panels:
        scene_idx = panel.get("scene_index", "?")
        description = panel.get("description", "")
        mood = panel.get("mood", "")
        image_path = panel.get("image_path", "")

        parts.append(types.Part.from_text(
            text=f"\n--- Scene {scene_idx} ---\n"
            f"Description: {description}\nMood: {mood}\n"
        ))

        if image_path and Path(image_path).exists():
            image_bytes = Path(image_path).read_bytes()
            parts.append(types.Part.from_bytes(data=image_bytes, mime_type="image/png"))
        else:
            parts.append(types.Part.from_text(text="[Image not available]\n"))

    client = genai.Client(api_key=settings.google_api_key)
    model = settings.gemini_model

    start = time.perf_counter()
    response = await gemini_generate_with_timeout(
        client,
        model=model,
        contents=types.Content(role="user", parts=parts),
        config=types.GenerateContentConfig(
            system_instruction=VISION_NARRATION_SYSTEM_PROMPT,
            temperature=0.7,
            max_output_tokens=2000,
            response_mime_type="application/json",
        ),
    )
    elapsed_ms = (time.perf_counter() - start) * 1000

    input_tokens = response.usage_metadata.prompt_token_count or 0
    output_tokens = response.usage_metadata.candidates_token_count or 0
    pricing = GEMINI_PRICING.get(model, {"input": 0, "output": 0})
    cost = input_tokens * pricing["input"] + output_tokens * pricing["output"]

    raw_text = response.text or "{}"
    json_start = raw_text.find("{")
    json_end = raw_text.rfind("}") + 1
    parsed = json.loads(raw_text[json_start:json_end]) if json_start >= 0 else {}

    narrations = {
        n["scene_index"]: n["narration_text"]
        for n in parsed.get("narrations", [])
    }

    llm_record = {
        "agent": "narration_script",
        "timestamp": time.time(),
        "provider": "gemini",
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost": cost,
        "duration_ms": elapsed_ms,
        "raw_response": raw_text[:500],
        "requested_provider": "gemini",
        "fallback": False,
        "vision_enhanced": True,
    }

    return narrations, llm_record


async def _text_only_narration(
    completed_panels: list[dict], request_id: str,
) -> tuple[dict[int, str], dict]:
    """Use text-only LLM router for narration (original behavior)."""
    scenes_for_prompt = [
        {
            "scene_index": p.get("scene_index"),
            "description": p.get("description", ""),
            "characters": p.get("characters", []),
            "mood": p.get("mood", ""),
            "setting": p.get("setting", ""),
        }
        for p in completed_panels
    ]

    prompt = NARRATION_SCRIPT_PROMPT.format(
        scenes_json=json.dumps(scenes_for_prompt, indent=2),
    )

    rc = get_runtime_config(state)
    router = get_llm_router()
    response = await router.generate(
        prompt=prompt,
        task_type=TaskType.EXTRACTION,
        temperature=0.7,
        max_tokens=2000,
        json_mode=True,
        agent_name="narration_script",
        runtime_config=rc,
    )

    content = response.content
    json_start = content.find("{")
    json_end = content.rfind("}") + 1
    if json_start == -1 or json_end == 0:
        raise ValueError("No JSON found in narration script response")

    parsed = json.loads(content[json_start:json_end])
    narrations = {
        n["scene_index"]: n["narration_text"]
        for n in parsed.get("narrations", [])
    }

    llm_record = {
        "agent": "narration_script",
        "timestamp": time.time(),
        "user_prompt": prompt,
        "raw_response": content[:500],
        "parsed_output": parsed,
        "provider": response.provider,
        "model": response.model,
        "input_tokens": response.input_tokens,
        "output_tokens": response.output_tokens,
        "cost": response.cost,
        "duration_ms": response.duration_ms,
        "requested_provider": response.requested_provider,
        "fallback": response.fallback,
        "vision_enhanced": False,
    }

    return narrations, llm_record


async def narration_script_node(state: StoryState) -> StoryState:
    request_id = state.get("request_id", "unknown")
    panels = list(state.get("panels", []))
    logger.info(
        "Narration script: generating for %d panels [request_id=%s]",
        len(panels), request_id,
    )

    trace = list(state.get("agent_trace", []))
    llm_calls = list(state.get("llm_calls", []))

    completed_panels = [p for p in panels if p.get("status") == "completed"]
    if not completed_panels:
        logger.info("Skipping narration script: no completed panels")
        trace.append({
            "agent": "narration_script",
            "timestamp": time.time(),
            "skipped": True,
            "reason": "No completed panels",
        })
        return {
            "current_agent": "narration_script",
            "agent_trace": trace,
            "llm_calls": llm_calls,
        }

    try:
        # Use vision-enhanced narration if enabled and images exist
        has_images = any(
            p.get("image_path") and Path(p["image_path"]).exists()
            for p in completed_panels
        )

        if settings.vision_narration_enabled and has_images:
            logger.info("Using vision-enhanced narration [request_id=%s]", request_id)
            narrations, llm_record = await _vision_narration(completed_panels, request_id)
        else:
            narrations, llm_record = await _text_only_narration(completed_panels, request_id)

        llm_calls.append(llm_record)

        # Annotate panels
        for panel in panels:
            scene_idx = panel.get("scene_index")
            if scene_idx in narrations:
                panel["narration_text"] = narrations[scene_idx]

        logger.info(
            "Generated narration for %d/%d panels (vision=%s) [request_id=%s]",
            len(narrations), len(panels),
            llm_record.get("vision_enhanced", False),
            request_id,
        )

        trace.append({
            "agent": "narration_script",
            "timestamp": time.time(),
            "panels_narrated": len(narrations),
            "vision_enhanced": llm_record.get("vision_enhanced", False),
        })

        return {
            "current_agent": "narration_script",
            "panels": panels,
            "agent_trace": trace,
            "llm_calls": llm_calls,
        }

    except Exception as e:
        logger.warning(
            "Narration script generation failed [request_id=%s]: %s",
            request_id, e,
        )
        trace.append({
            "agent": "narration_script",
            "timestamp": time.time(),
            "error": str(e),
        })
        # Non-fatal: continue without narration text
        return {
            "current_agent": "narration_script",
            "agent_trace": trace,
            "llm_calls": llm_calls,
        }
