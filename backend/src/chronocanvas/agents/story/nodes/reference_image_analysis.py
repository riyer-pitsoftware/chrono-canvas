"""Reference Image Analysis node — Gemini multimodal extracts style/visual info from references.

OPTIONAL: only runs when `reference_images` list is non-empty in state.
Analysis results are injected into scene prompt generation for style matching.
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

REFERENCE_ANALYSIS_PROMPT = """\
Analyze these reference images for a visual storyboard. For each image, extract:

1. Visual style (art style, rendering technique, medium)
2. Era/time period suggested
3. Color palette (dominant colors, temperature, saturation)
4. Key visual elements (architecture, clothing, objects, landscape features)
5. How this reference should influence scene generation

Output ONLY valid JSON — a list of analyses:
[
  {
    "ref_index": 0,
    "visual_style": "description...",
    "era_period": "description...",
    "color_palette": ["color1", "color2", "color3"],
    "key_elements": ["element1", "element2"],
    "suggested_integration": "How to use this reference in scene prompts..."
  }
]"""


async def reference_image_analysis_node(state: StoryState) -> StoryState:
    request_id = state.get("request_id", "unknown")
    reference_images = state.get("reference_images", [])

    logger.info(
        "Reference image analysis: %d images [request_id=%s]",
        len(reference_images),
        request_id,
    )

    trace = list(state.get("agent_trace", []))
    llm_calls = list(state.get("llm_calls", []))

    if not reference_images:
        trace.append(
            {
                "agent": "reference_image_analysis",
                "timestamp": time.time(),
                "skipped": True,
                "reason": "No reference images",
            }
        )
        return {
            "current_agent": "reference_image_analysis",
            "agent_trace": trace,
            "llm_calls": llm_calls,
        }

    parts: list[types.Part] = [
        types.Part.from_text(text=REFERENCE_ANALYSIS_PROMPT),
    ]

    loaded_count = 0
    for i, ref in enumerate(reference_images):
        file_path = ref.get("file_path", "")
        mime_type = ref.get("mime_type", "image/png")
        desc = ref.get("description", "")
        ref_type = ref.get("ref_type", "style_reference")

        if file_path and Path(file_path).exists():
            parts.append(
                types.Part.from_text(
                    text=f"\n--- Reference {i} (type: {ref_type}) ---\nDescription: {desc}\n"
                    if desc
                    else f"\n--- Reference {i} (type: {ref_type}) ---\n"
                )
            )
            image_bytes = Path(file_path).read_bytes()
            parts.append(types.Part.from_bytes(data=image_bytes, mime_type=mime_type))
            loaded_count += 1

    if loaded_count == 0:
        trace.append(
            {
                "agent": "reference_image_analysis",
                "timestamp": time.time(),
                "skipped": True,
                "reason": "No readable reference image files",
            }
        )
        return {
            "current_agent": "reference_image_analysis",
            "agent_trace": trace,
            "llm_calls": llm_calls,
        }

    client = genai.Client(api_key=settings.google_api_key)
    model = settings.gemini_model

    start = time.perf_counter()
    try:
        response = await gemini_generate_with_timeout(
            client,
            model=model,
            contents=types.Content(role="user", parts=parts),
            config=types.GenerateContentConfig(
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

        raw_text = response.text or "[]"
        json_start = raw_text.find("[")
        json_end = raw_text.rfind("]") + 1
        analyses = json.loads(raw_text[json_start:json_end]) if json_start >= 0 else []

        llm_calls.append(
            {
                "agent": "reference_image_analysis",
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
                "agent": "reference_image_analysis",
                "timestamp": time.time(),
                "images_analyzed": loaded_count,
                "analyses_returned": len(analyses),
            }
        )

        logger.info(
            "Reference analysis: %d images → %d analyses [request_id=%s]",
            loaded_count,
            len(analyses),
            request_id,
        )

        return {
            "current_agent": "reference_image_analysis",
            "reference_analysis": analyses,
            "agent_trace": trace,
            "llm_calls": llm_calls,
        }

    except Exception as e:
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.warning(
            "Reference image analysis failed [request_id=%s]: %s",
            request_id,
            e,
        )
        trace.append(
            {
                "agent": "reference_image_analysis",
                "timestamp": time.time(),
                "error": str(e),
            }
        )
        return {
            "current_agent": "reference_image_analysis",
            "agent_trace": trace,
            "llm_calls": llm_calls,
        }
