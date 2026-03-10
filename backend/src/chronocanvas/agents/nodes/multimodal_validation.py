# ruff: noqa: E501 — LLM prompt template contains long natural-language lines
"""Multimodal image validation — uses Gemini vision to validate generated images.

Sends the generated image + prompt + research context to Gemini vision for
visual validation. Checks actual image content against expected attributes
(clothing, environment, cultural markers) rather than just text-based scoring.

Non-fatal: if Gemini vision is unavailable, the node returns without error.
"""

import json
import logging
import time
from pathlib import Path

from google import genai
from google.genai import types

from chronocanvas.agents.state import AgentState
from chronocanvas.config import settings
from chronocanvas.llm.providers.gemini import GEMINI_PRICING

logger = logging.getLogger(__name__)

VISION_VALIDATION_PROMPT = """\
You are a historical accuracy expert reviewing a generated portrait image.

Compare the generated image against the expected attributes below and score each category.

Figure: {figure_name}
Time Period: {time_period}
Region: {region}
Expected Clothing: {clothing_details}
Expected Physical Description: {physical_description}
Cultural Context: {cultural_context}
Image Prompt Used: {image_prompt}

Evaluate the image on these criteria:
1. CLOTHING ACCURACY: Does the clothing match the described period/region? (0-100)
2. FACIAL FEATURES: Do features align with described ethnicity/heritage? (0-100)
3. ENVIRONMENTAL CONTEXT: Is the background/setting period-appropriate? (0-100)
4. CULTURAL MARKERS: Are accessories, hairstyle, and adornments historically correct? (0-100)
5. ANACHRONISM CHECK: Are there any modern or out-of-period elements visible? (0-100, higher = fewer anachronisms)
6. OVERALL QUALITY: Image quality, composition, and realism. (0-100)

Output ONLY valid JSON:
{{
  "scores": {{
    "clothing_accuracy": 85,
    "facial_features": 80,
    "environmental_context": 75,
    "cultural_markers": 82,
    "anachronism_check": 90,
    "overall_quality": 88
  }},
  "overall_score": 83.3,
  "issues": ["list of specific issues found"],
  "strengths": ["list of what the image got right"],
  "recommendation": "pass" or "review" or "regenerate"
}}
"""

_MIME_MAP = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}


def _estimate_cost(
    input_tokens: int,
    output_tokens: int,
    model: str,
) -> float:
    pricing = GEMINI_PRICING.get(
        model,
        GEMINI_PRICING.get("gemini-2.5-flash", {}),
    )
    in_cost = (input_tokens / 1_000_000) * pricing.get("input", 0)
    out_cost = (output_tokens / 1_000_000) * pricing.get("output", 0)
    return in_cost + out_cost


def _skip_result(trace, llm_calls):
    return {
        "current_agent": "multimodal_validation",
        "agent_trace": trace,
        "llm_calls": llm_calls,
    }


async def multimodal_validation_node(state: AgentState) -> AgentState:
    """Validate the generated image using Gemini vision (multimodal)."""
    request_id = state.get("request_id", "unknown")
    ext = state.get("extraction", {})
    res = state.get("research", {})
    prompt_state = state.get("prompt", {})
    img = state.get("image", {})
    image_path = img.get("image_path", "")

    trace = list(state.get("agent_trace", []))
    llm_calls = list(state.get("llm_calls", []))

    # Skip if no image or no API key
    if not image_path or not Path(image_path).exists():
        logger.info(
            "Multimodal validation: no image [request_id=%s]",
            request_id,
        )
        trace.append(
            {
                "agent": "multimodal_validation",
                "timestamp": time.time(),
                "skipped": True,
                "reason": "no_image",
            }
        )
        return _skip_result(trace, llm_calls)

    if not settings.google_api_key:
        if settings.hackathon_mode:
            raise RuntimeError(
                "HACKATHON MODE: Multimodal validation cannot run — GOOGLE_API_KEY is not set"
            )
        logger.info(
            "Multimodal validation: no GOOGLE_API_KEY [request_id=%s]",
            request_id,
        )
        trace.append(
            {
                "agent": "multimodal_validation",
                "timestamp": time.time(),
                "skipped": True,
                "reason": "no_api_key",
            }
        )
        return _skip_result(trace, llm_calls)

    figure_name = ext.get("figure_name", "Unknown")
    logger.info(
        "Multimodal validation: %s [request_id=%s]",
        figure_name,
        request_id,
    )

    # Read image bytes
    image_bytes = Path(image_path).read_bytes()
    suffix = Path(image_path).suffix.lower()
    mime_type = _MIME_MAP.get(suffix, "image/png")

    prompt_text = VISION_VALIDATION_PROMPT.format(
        figure_name=figure_name,
        time_period=ext.get("time_period", "Unknown"),
        region=ext.get("region", "Unknown"),
        clothing_details=res.get("clothing_details", "Not specified"),
        physical_description=res.get("physical_description", "Not specified"),
        cultural_context=ext.get("cultural_context", "Not specified"),
        image_prompt=prompt_state.get("image_prompt", ""),
    )

    model_id = "gemini-2.5-flash"
    start = time.perf_counter()

    try:
        client = genai.Client(api_key=settings.google_api_key)
        response = client.models.generate_content(
            model=model_id,
            contents=[
                types.Part.from_bytes(
                    data=image_bytes,
                    mime_type=mime_type,
                ),
                types.Part.from_text(text=prompt_text),
            ],
            config=types.GenerateContentConfig(
                temperature=0.3,
                max_output_tokens=1000,
                response_mime_type="application/json",
            ),
        )

        elapsed_ms = (time.perf_counter() - start) * 1000
        raw = response.text or "{}"
        usage = getattr(response, "usage_metadata", None)
        in_tok = getattr(usage, "prompt_token_count", 0) if usage else 0
        out_tok = getattr(usage, "candidates_token_count", 0) if usage else 0
        cost = _estimate_cost(in_tok, out_tok, model_id)

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = {
                "overall_score": 0,
                "issues": ["Failed to parse vision response"],
                "recommendation": "review",
            }

        trace.append(
            {
                "agent": "multimodal_validation",
                "timestamp": time.time(),
                "overall_score": data.get("overall_score", 0),
                "recommendation": data.get("recommendation", "review"),
                "issues": data.get("issues", []),
                "strengths": data.get("strengths", []),
                "scores": data.get("scores", {}),
                "cost": cost,
            }
        )

        llm_calls.append(
            {
                "agent": "multimodal_validation",
                "timestamp": time.time(),
                "system_prompt": None,
                "user_prompt": prompt_text[:500],
                "raw_response": raw,
                "parsed_output": data,
                "provider": "gemini",
                "model": model_id,
                "input_tokens": in_tok,
                "output_tokens": out_tok,
                "cost": cost,
                "duration_ms": elapsed_ms,
                "requested_provider": "gemini",
                "fallback": False,
            }
        )

        # Store vision validation results alongside existing validation
        val = dict(state.get("validation", {}))
        val["vision_validation"] = data

        return {
            "current_agent": "multimodal_validation",
            "validation": val,
            "agent_trace": trace,
            "llm_calls": llm_calls,
        }

    except Exception as e:
        if settings.hackathon_mode:
            raise
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.warning(
            "Multimodal validation failed (non-fatal) [request_id=%s]: %s",
            request_id,
            e,
        )
        trace.append(
            {
                "agent": "multimodal_validation",
                "timestamp": time.time(),
                "skipped": False,
                "error": str(e),
            }
        )
        return _skip_result(trace, llm_calls)
