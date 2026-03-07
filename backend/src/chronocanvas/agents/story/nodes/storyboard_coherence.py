"""Storyboard coherence node — uses Gemini multimodal to review visual consistency.

After all scene images are generated, this node sends every image + its description
to Gemini for a holistic coherence assessment.  It evaluates character consistency,
art style uniformity, color palette harmony, and narrative flow — then annotates
each panel with a coherence score and flags for potential re-generation.
"""

import json
import logging
import time
from pathlib import Path

from google import genai
from google.genai import types

from chronocanvas.agents.story.state import StoryState
from chronocanvas.config import settings
from chronocanvas.llm.providers.gemini import GEMINI_PRICING, gemini_generate_with_timeout

logger = logging.getLogger(__name__)

COHERENCE_SYSTEM_PROMPT = """\
You are a visual storyboard director reviewing a sequence of generated images for \
narrative coherence and visual consistency.

Analyze ALL the provided scene images together as a single storyboard. Evaluate:

1. CHARACTER CONSISTENCY: Do recurring characters look the same across scenes \
   (clothing, features, proportions)?
2. ART STYLE UNIFORMITY: Is the visual style (rendering, detail level, medium) \
   consistent across all panels?
3. COLOR PALETTE HARMONY: Do the scenes share a cohesive color language, or do \
   some panels clash?
4. NARRATIVE FLOW: Do the scenes visually tell a story when viewed in sequence? \
   Would reordering improve the arc?

For each scene, provide a coherence_score (0.0-1.0) and a list of issues found.
Then provide an overall assessment with a narrative_flow_score and optional \
reordering suggestion.

Output ONLY valid JSON with this structure:
{
  "overall": {
    "narrative_flow_score": 0.85,
    "style_consistency_score": 0.9,
    "character_consistency_score": 0.8,
    "palette_harmony_score": 0.85,
    "summary": "Brief overall assessment...",
    "suggested_order": [0, 1, 2, 3],
    "reorder_reason": "null or explanation if reorder suggested"
  },
  "panels": [
    {
      "scene_index": 0,
      "coherence_score": 0.9,
      "issues": [],
      "suggestion": ""
    }
  ]
}"""


def _build_multimodal_content(panels: list[dict]) -> list[types.Part]:
    """Build a list of Gemini content parts: text descriptions interleaved with images."""
    parts: list[types.Part] = []

    parts.append(types.Part.from_text(
        text=f"I have a storyboard with {len(panels)} scenes. "
        "Review each image and its description for visual coherence:\n\n"
    ))

    for panel in panels:
        scene_idx = panel.get("scene_index", "?")
        description = panel.get("description", "No description")
        mood = panel.get("mood", "")
        setting = panel.get("setting", "")
        image_path = panel.get("image_path", "")

        # Add text context for this scene
        parts.append(types.Part.from_text(
            text=f"\n--- Scene {scene_idx} ---\n"
            f"Description: {description}\n"
            f"Mood: {mood}\n"
            f"Setting: {setting}\n"
        ))

        # Add the image if it exists
        if image_path and Path(image_path).exists():
            image_bytes = Path(image_path).read_bytes()
            parts.append(types.Part.from_bytes(data=image_bytes, mime_type="image/png"))
        else:
            parts.append(types.Part.from_text(text="[Image not available]\n"))

    parts.append(types.Part.from_text(
        text="\n\nNow analyze all scenes together for coherence. "
        "Output ONLY the JSON structure described in your instructions."
    ))

    return parts


async def storyboard_coherence_node(state: StoryState) -> StoryState:
    request_id = state.get("request_id", "unknown")
    panels = list(state.get("panels", []))
    logger.info(
        "Storyboard coherence: reviewing %d panels [request_id=%s]",
        len(panels), request_id,
    )

    trace = list(state.get("agent_trace", []))
    llm_calls = list(state.get("llm_calls", []))

    # Only review completed panels that have images
    completed_panels = [p for p in panels if p.get("status") == "completed" and p.get("image_path")]

    if len(completed_panels) < 2:
        # Not enough panels to assess coherence — skip
        logger.info("Skipping coherence check: only %d completed panels", len(completed_panels))
        trace.append({
            "agent": "storyboard_coherence",
            "timestamp": time.time(),
            "skipped": True,
            "reason": f"Only {len(completed_panels)} completed panels",
        })
        return {
            "current_agent": "storyboard_coherence",
            "agent_trace": trace,
            "llm_calls": llm_calls,
        }

    # Build multimodal content
    content_parts = _build_multimodal_content(completed_panels)

    # Call Gemini directly for multimodal (the LLM router only supports text)
    client = genai.Client(api_key=settings.google_api_key)
    model = settings.gemini_model

    start = time.perf_counter()
    try:
        response = await gemini_generate_with_timeout(
            client,
            model=model,
            contents=types.Content(role="user", parts=content_parts),
            config=types.GenerateContentConfig(
                system_instruction=COHERENCE_SYSTEM_PROMPT,
                temperature=0.3,
                max_output_tokens=2000,
                response_mime_type="application/json",
            ),
        )
        elapsed_ms = (time.perf_counter() - start) * 1000

        input_tokens = response.usage_metadata.prompt_token_count or 0
        output_tokens = response.usage_metadata.candidates_token_count or 0
        pricing = GEMINI_PRICING.get(model, {"input": 0, "output": 0})
        cost = input_tokens * pricing["input"] + output_tokens * pricing["output"]

        # Parse the coherence response
        raw_text = response.text or "{}"
        json_start = raw_text.find("{")
        json_end = raw_text.rfind("}") + 1
        coherence_data = json.loads(raw_text[json_start:json_end]) if json_start >= 0 else {}

        overall = coherence_data.get("overall", {})
        panel_assessments = {
            p.get("scene_index"): p
            for p in coherence_data.get("panels", [])
        }

        # Annotate panels with coherence scores
        for panel in panels:
            scene_idx = panel.get("scene_index")
            assessment = panel_assessments.get(scene_idx, {})
            panel["coherence_score"] = assessment.get("coherence_score")
            panel["coherence_issues"] = assessment.get("issues", [])
            panel["coherence_suggestion"] = assessment.get("suggestion", "")

        llm_calls.append({
            "agent": "storyboard_coherence",
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
        })

        trace.append({
            "agent": "storyboard_coherence",
            "timestamp": time.time(),
            "panels_reviewed": len(completed_panels),
            "narrative_flow_score": overall.get("narrative_flow_score"),
            "style_consistency_score": overall.get("style_consistency_score"),
            "character_consistency_score": overall.get("character_consistency_score"),
            "palette_harmony_score": overall.get("palette_harmony_score"),
            "summary": overall.get("summary", ""),
            "suggested_order": overall.get("suggested_order"),
        })

        # Check if character consistency warrants regeneration
        char_score = overall.get("character_consistency_score", 1.0)
        retry_count = state.get("coherence_retry_count", 0)
        regen_scenes: list[int] = []

        if char_score < 0.6 and retry_count < 1:
            # Identify worst-scoring scenes for regeneration
            scored = [
                (p.get("scene_index", i), p.get("coherence_score", 1.0))
                for i, p in enumerate(coherence_data.get("panels", []))
            ]
            scored.sort(key=lambda x: x[1])
            # Regen the bottom half (at least 1 scene)
            n_regen = max(1, len(scored) // 2)
            regen_scenes = [idx for idx, _score in scored[:n_regen]]
            logger.info(
                "Character consistency %.2f < 0.6 — flagging scenes %s for regen [request_id=%s]",
                char_score, regen_scenes, request_id,
            )

        logger.info(
            "Coherence review complete: flow=%.2f style=%.2f chars=%.2f [request_id=%s]",
            overall.get("narrative_flow_score", 0),
            overall.get("style_consistency_score", 0),
            char_score,
            request_id,
        )

    except Exception as e:
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.warning(
            "Storyboard coherence check failed [request_id=%s]: %s",
            request_id, e,
        )
        regen_scenes = []
        # Non-fatal: coherence is additive, don't fail the pipeline
        trace.append({
            "agent": "storyboard_coherence",
            "timestamp": time.time(),
            "error": str(e),
            "panels_reviewed": len(completed_panels),
        })

    result: dict = {
        "current_agent": "storyboard_coherence",
        "panels": panels,
        "agent_trace": trace,
        "llm_calls": llm_calls,
    }

    if regen_scenes:
        result["regen_scenes"] = regen_scenes
        result["coherence_retry_count"] = state.get("coherence_retry_count", 0) + 1

    return result
