import asyncio
import json
import logging
import time

from chronocanvas.agents.story.state import StoryState, get_runtime_config
from chronocanvas.llm.base import TaskType
from chronocanvas.llm.router import get_llm_router

logger = logging.getLogger(__name__)

VALIDATION_PROMPT = """\
You're a noir creative director checking a shot list. Every prompt needs to paint a picture \
sharp enough for a cinematographer to frame.

Review this image generation prompt and score it on four axes (0.0 to 1.0 each):

IMAGE PROMPT:
{image_prompt}

SCENE CONTEXT:
- Description: {description}
- Characters: {characters}
- Mood: {mood}
- Setting: {setting}

Score each axis:
- identity_clarity: Are characters described with enough physical specificity (face, build, \
clothing, distinguishing features) that an artist could draw them without guessing? Score low \
if characters are generic ("a woman") or missing visual anchors.
- era_plausibility: Do the described objects, clothing, architecture, and technology match the \
time period implied by the setting? Score low if anachronisms are present.
- composition_completeness: Does the prompt specify camera angle, lens choice, lighting setup, \
and framing? Score low if any of these are missing or vague.
- contradiction_free: Are there conflicting descriptors? (e.g., "bright sunny day" + "rain-slicked \
streets", "close-up" + "wide establishing shot"). Score low if contradictions exist.

Output ONLY valid JSON:
{{
  "identity_clarity": 0.0,
  "era_plausibility": 0.0,
  "composition_completeness": 0.0,
  "contradiction_free": 0.0,
  "overall": 0.0,
  "issues": ["list of specific problems found"]
}}

The "overall" score is the average of the four axes."""

REPAIR_PROMPT = """\
You're a noir creative director. A shot prompt failed quality review. Rewrite it to fix the \
issues below while preserving the original creative intent and mood.

ORIGINAL PROMPT:
{image_prompt}

SCENE CONTEXT:
- Description: {description}
- Characters: {characters}
- Mood: {mood}
- Setting: {setting}

ISSUES FOUND:
{issues}

Rewrite the prompt to fix every listed issue. Keep the noir visual grammar — chiaroscuro, \
deep shadows, hard light, cinematic framing. Make characters physically specific, fix any \
anachronisms, ensure camera/lighting are explicit, and remove contradictions.

Output ONLY valid JSON:
{{
  "image_prompt": "the rewritten prompt..."
}}"""


async def _validate_panel(panel, router, request_id, runtime_config):
    """Validate a single panel's image_prompt. Returns (updated_panel, llm_calls)."""
    image_prompt = panel.get("image_prompt", "")
    if not image_prompt:
        return panel, []

    llm_calls = []
    characters = panel.get("characters", [])

    # --- Step 1: Score the prompt ---
    val_prompt = VALIDATION_PROMPT.format(
        image_prompt=image_prompt,
        description=panel.get("description", ""),
        characters=", ".join(characters) if characters else "none",
        mood=panel.get("mood", ""),
        setting=panel.get("setting", ""),
    )

    try:
        response = await router.generate(
            prompt=val_prompt,
            task_type=TaskType.GENERAL,
            temperature=0.2,
            max_tokens=1000,
            json_mode=True,
            request_id=request_id,
            agent_name="prompt_validation",
            runtime_config=runtime_config,
        )

        content = response.content.strip()
        json_start = content.find("{")
        json_end = content.rfind("}") + 1
        scores = json.loads(content[json_start:json_end])

        llm_calls.append(
            {
                "agent": "prompt_validation",
                "timestamp": time.time(),
                "user_prompt": val_prompt,
                "raw_response": content,
                "parsed_output": scores,
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

        overall = float(scores.get("overall", 1.0))
        issues = scores.get("issues", [])

    except Exception as e:
        logger.warning(
            "Prompt validation scoring failed for scene %s [request_id=%s]: %s",
            panel.get("scene_index", "?"),
            request_id,
            e,
        )
        # Non-fatal: let the prompt through unmodified
        return panel, llm_calls

    # --- Step 2: Repair if below threshold ---
    if overall >= 0.7:
        logger.info(
            "Prompt validation passed for scene %s (score=%.2f) [request_id=%s]",
            panel.get("scene_index", "?"),
            overall,
            request_id,
        )
        return panel, llm_calls

    logger.info(
        "Prompt validation failed for scene %s (score=%.2f), repairing [request_id=%s]",
        panel.get("scene_index", "?"),
        overall,
        request_id,
    )

    repair_prompt = REPAIR_PROMPT.format(
        image_prompt=image_prompt,
        description=panel.get("description", ""),
        characters=", ".join(characters) if characters else "none",
        mood=panel.get("mood", ""),
        setting=panel.get("setting", ""),
        issues="\n".join(f"- {i}" for i in issues)
        if issues
        else "- General quality below threshold",
    )

    try:
        repair_response = await router.generate(
            prompt=repair_prompt,
            task_type=TaskType.PROMPT_GENERATION,
            temperature=0.5,
            max_tokens=2000,
            json_mode=True,
            request_id=request_id,
            agent_name="prompt_validation_repair",
            runtime_config=runtime_config,
        )

        repair_content = repair_response.content.strip()
        rj_start = repair_content.find("{")
        rj_end = repair_content.rfind("}") + 1
        repaired = json.loads(repair_content[rj_start:rj_end])

        new_prompt = repaired.get("image_prompt", "")
        if new_prompt:
            panel = dict(panel)  # shallow copy to avoid mutating original
            panel["image_prompt"] = new_prompt

        llm_calls.append(
            {
                "agent": "prompt_validation_repair",
                "timestamp": time.time(),
                "user_prompt": repair_prompt,
                "raw_response": repair_content,
                "parsed_output": repaired,
                "provider": repair_response.provider,
                "model": repair_response.model,
                "input_tokens": repair_response.input_tokens,
                "output_tokens": repair_response.output_tokens,
                "cost": repair_response.cost,
                "duration_ms": repair_response.duration_ms,
                "requested_provider": repair_response.requested_provider,
                "fallback": repair_response.fallback,
            }
        )

    except Exception as e:
        logger.warning(
            "Prompt repair failed for scene %s [request_id=%s]: %s — keeping original",
            panel.get("scene_index", "?"),
            request_id,
            e,
        )

    return panel, llm_calls


async def prompt_validation_node(state: StoryState) -> StoryState:
    """Validate and optionally repair image prompts before image generation.

    Checks each panel's image_prompt for identity clarity, era plausibility,
    composition completeness, and contradictions. Prompts scoring below 0.7
    are rewritten inline by LLM.
    """
    request_id = state.get("request_id", "unknown")
    panels = list(state.get("panels", []))
    logger.info(
        "Prompt validation: checking %d panels [request_id=%s]",
        len(panels),
        request_id,
    )

    if not panels:
        return {"current_agent": "prompt_validation"}

    rc = get_runtime_config(state)
    router = get_llm_router()
    trace = list(state.get("agent_trace", []))
    llm_calls = list(state.get("llm_calls", []))

    results = await asyncio.gather(
        *(_validate_panel(panel, router, request_id, rc) for panel in panels)
    )

    validated_panels = []
    repaired_count = 0
    for updated_panel, panel_llm_calls in results:
        validated_panels.append(updated_panel)
        llm_calls.extend(panel_llm_calls)
        # If there were 2 LLM calls for this panel, it was repaired
        if len(panel_llm_calls) == 2:
            repaired_count += 1

    trace.append(
        {
            "agent": "prompt_validation",
            "timestamp": time.time(),
            "panels_checked": len(panels),
            "panels_repaired": repaired_count,
        }
    )

    return {
        "current_agent": "prompt_validation",
        "panels": validated_panels,
        "agent_trace": trace,
        "llm_calls": llm_calls,
    }
