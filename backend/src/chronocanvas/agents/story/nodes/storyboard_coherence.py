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

from chronocanvas.agents.story.nodes.json_repair import extract_and_parse_json
from google import genai
from google.genai import types

from chronocanvas.agents.story.state import StoryState
from chronocanvas.config import settings
from chronocanvas.llm.providers.gemini import GEMINI_PRICING, gemini_generate_with_timeout

logger = logging.getLogger(__name__)

COHERENCE_SYSTEM_PROMPT = """\
You are Dash, a noir creative director reviewing a storyboard in a darkened screening room. \
You've watched a thousand films and made a hundred. You know when something works and when \
it doesn't, and you're not shy about saying so. Be direct. Be specific. Be occasionally wry.

Analyze ALL the provided scene images together as a single storyboard. Evaluate:

1. CHARACTER CONSISTENCY: Do recurring characters look the same across scenes? \
   Same face, same build, same wardrobe. Continuity errors are amateur hour.
2. ART STYLE & NOIR LANGUAGE: Is the visual style consistent? Are shadows deep enough? \
   Is the contrast doing its job? Noir isn't just dark — it's controlled darkness.
3. COLOR PALETTE: Do the scenes share a cohesive noir palette — deep blacks, amber \
   highlights, cool blues? Or do some panels look like they wandered in from a different film?
4. NARRATIVE FLOW: Do the scenes tell a story when viewed in sequence? Does each \
   frame earn its place? Would cutting or reordering improve the arc?
5. CONTINUITY TRACKING: For each scene (except the first), compare its expected_state \
   against the previous scene's established_state. Flag any breaks — wardrobe changes \
   that weren't established, lighting jumps, characters appearing or vanishing without \
   explanation, time-of-day contradictions. Continuity is the contract between frames; \
   breaking it breaks the audience's trust.

For each scene, provide a coherence_score (0.0-1.0), a list of issues found, and a list \
of continuity_breaks (empty if none).
Then provide an overall assessment with a narrative_flow_score, a continuity_score, \
and optional reordering suggestion.

Output ONLY valid JSON with this structure:
{
  "overall": {
    "narrative_flow_score": 0.85,
    "style_consistency_score": 0.9,
    "character_consistency_score": 0.8,
    "palette_harmony_score": 0.85,
    "continuity_score": 0.8,
    "summary": "Brief overall assessment...",
    "suggested_order": [0, 1, 2, 3],
    "reorder_reason": "null or explanation if reorder suggested"
  },
  "panels": [
    {
      "scene_index": 0,
      "coherence_score": 0.9,
      "issues": [],
      "continuity_breaks": [],
      "suggestion": ""
    }
  ]
}"""


def _build_multimodal_content(panels: list[dict]) -> list[types.Part]:
    """Build a list of Gemini content parts: text descriptions interleaved with images."""
    parts: list[types.Part] = []

    parts.append(
        types.Part.from_text(
            text=f"I have a storyboard with {len(panels)} scenes. "
            "Review each image and its description for visual coherence:\n\n"
        )
    )

    for panel in panels:
        scene_idx = panel.get("scene_index", "?")
        description = panel.get("description", "No description")
        mood = panel.get("mood", "")
        setting = panel.get("setting", "")
        image_path = panel.get("image_path", "")
        expected_state = panel.get("expected_state", {})
        established_state = panel.get("established_state", {})

        # Add text context for this scene
        parts.append(
            types.Part.from_text(
                text=f"\n--- Scene {scene_idx} ---\n"
                f"Description: {description}\n"
                f"Mood: {mood}\n"
                f"Setting: {setting}\n"
                f"Expected state (from prior scene): {json.dumps(expected_state)}\n"
                f"Established state (for next scene): {json.dumps(established_state)}\n"
            )
        )

        # Add the image if it exists
        if image_path and Path(image_path).exists():
            image_bytes = Path(image_path).read_bytes()
            parts.append(types.Part.from_bytes(data=image_bytes, mime_type="image/png"))
        else:
            parts.append(types.Part.from_text(text="[Image not available]\n"))

    parts.append(
        types.Part.from_text(
            text="\n\nNow analyze all scenes together for coherence. "
            "Pay special attention to continuity: compare each scene's expected_state "
            "against the previous scene's established_state and flag any breaks. "
            "Output ONLY the JSON structure described in your instructions."
        )
    )

    return parts


async def storyboard_coherence_node(state: StoryState) -> StoryState:
    request_id = state.get("request_id", "unknown")
    panels = list(state.get("panels", []))
    logger.info(
        "Storyboard coherence: reviewing %d panels [request_id=%s]",
        len(panels),
        request_id,
    )

    trace = list(state.get("agent_trace", []))
    llm_calls = list(state.get("llm_calls", []))

    # Only review completed panels that have images
    completed_panels = [p for p in panels if p.get("status") == "completed" and p.get("image_path")]

    if len(completed_panels) < 2:
        # Not enough panels to assess coherence — skip
        logger.info("Skipping coherence check: only %d completed panels", len(completed_panels))
        trace.append(
            {
                "agent": "storyboard_coherence",
                "timestamp": time.time(),
                "skipped": True,
                "reason": f"Only {len(completed_panels)} completed panels",
            }
        )
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
                max_output_tokens=8192,
                response_mime_type="application/json",
            ),
        )
        elapsed_ms = (time.perf_counter() - start) * 1000

        input_tokens = response.usage_metadata.prompt_token_count or 0
        output_tokens = response.usage_metadata.candidates_token_count or 0
        pricing = GEMINI_PRICING.get(model, {"input": 0, "output": 0})
        cost = input_tokens * pricing["input"] + output_tokens * pricing["output"]

        # Parse the coherence response
        raw_text = response.text or ""
        if not raw_text.strip():
            raise ValueError("Gemini returned empty coherence response")
        coherence_data = extract_and_parse_json(raw_text)

        overall = coherence_data.get("overall", {})
        panel_assessments = {p.get("scene_index"): p for p in coherence_data.get("panels", [])}

        # Annotate panels with coherence scores and continuity breaks
        for panel in panels:
            scene_idx = panel.get("scene_index")
            assessment = panel_assessments.get(scene_idx, {})
            panel["coherence_score"] = assessment.get("coherence_score")
            panel["coherence_issues"] = assessment.get("issues", [])
            panel["coherence_suggestion"] = assessment.get("suggestion", "")
            # Merge continuity breaks into issues for visibility
            continuity_breaks = assessment.get("continuity_breaks", [])
            if continuity_breaks:
                panel["coherence_issues"] = panel["coherence_issues"] + [
                    f"[continuity] {b}" for b in continuity_breaks
                ]

        llm_calls.append(
            {
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
            }
        )

        trace.append(
            {
                "agent": "storyboard_coherence",
                "timestamp": time.time(),
                "panels_reviewed": len(completed_panels),
                "narrative_flow_score": overall.get("narrative_flow_score"),
                "style_consistency_score": overall.get("style_consistency_score"),
                "character_consistency_score": overall.get("character_consistency_score"),
                "palette_harmony_score": overall.get("palette_harmony_score"),
                "continuity_score": overall.get("continuity_score"),
                "summary": overall.get("summary", ""),
                "suggested_order": overall.get("suggested_order"),
            }
        )

        # Check if character consistency or continuity warrants regeneration
        char_score = overall.get("character_consistency_score", 1.0)
        continuity_score = overall.get("continuity_score", 1.0)
        retry_count = state.get("coherence_retry_count", 0)
        regen_scenes: list[int] = []

        if (char_score < 0.6 or continuity_score < 0.5) and retry_count < 1:
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
                "Consistency scores (char=%.2f, continuity=%.2f) below threshold "
                "— flagging scenes %s for regen [request_id=%s]",
                char_score,
                continuity_score,
                regen_scenes,
                request_id,
            )

        logger.info(
            "Coherence review complete: flow=%.2f style=%.2f chars=%.2f continuity=%.2f [request_id=%s]",
            overall.get("narrative_flow_score", 0),
            overall.get("style_consistency_score", 0),
            char_score,
            continuity_score,
            request_id,
        )

    except Exception as e:
        # Coherence is additive — never kill the pipeline for it, even in hackathon mode.
        # Images are already generated; failing here would discard all completed work.
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.warning(
            "Storyboard coherence check failed [request_id=%s]: %s",
            request_id,
            e,
        )
        regen_scenes = []
        # Non-fatal: coherence is additive, don't fail the pipeline
        trace.append(
            {
                "agent": "storyboard_coherence",
                "timestamp": time.time(),
                "error": str(e),
                "panels_reviewed": len(completed_panels),
            }
        )

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
