"""Image-to-Story node — Gemini multimodal extracts a story concept from an uploaded image.

This node is OPTIONAL: it only runs when `reference_image_path` is set in state.
When active, it sends the image (+ optional text guidance) to Gemini and sets
`input_text` to the extracted synopsis so the rest of the pipeline proceeds unchanged.
"""

import json
import logging
import time
from pathlib import Path

from google import genai
from google.genai import types

from chronocanvas.agents.story.state import StoryState
from chronocanvas.config import settings
from chronocanvas.llm.providers.gemini import GEMINI_PRICING

logger = logging.getLogger(__name__)

IMAGE_TO_STORY_PROMPT = """\
You are a creative story director. Analyze this image and create a rich story concept \
inspired by what you see. Extract:

- A compelling title
- A 2-3 paragraph synopsis that could be turned into a visual storyboard (4-6 scenes)
- Key characters visible or implied (with physical descriptions)
- Settings and locations
- The mood and atmosphere
- Suggested number of scenes (4-6)

The story should be cinematic and visually driven — think graphic novel or film storyboard.

Output ONLY valid JSON:
{
  "title": "Story title",
  "synopsis": "Full story synopsis (2-3 paragraphs)...",
  "characters": [
    {"name": "Character Name", "description": "Physical and personality description"}
  ],
  "settings": ["Setting 1", "Setting 2"],
  "mood": "Overall mood",
  "num_scenes": 5
}"""


async def image_to_story_node(state: StoryState) -> StoryState:
    request_id = state.get("request_id", "unknown")
    image_path = state.get("reference_image_path", "")
    image_mime = state.get("reference_image_mime", "image/png")
    original_text = state.get("input_text", "")

    logger.info(
        "Image-to-Story: analyzing uploaded image [request_id=%s]",
        request_id,
    )

    trace = list(state.get("agent_trace", []))
    llm_calls = list(state.get("llm_calls", []))

    if not image_path or not Path(image_path).exists():
        logger.warning(
            "Image-to-Story: image not found at %s, skipping [request_id=%s]",
            image_path, request_id,
        )
        trace.append({
            "agent": "image_to_story",
            "timestamp": time.time(),
            "skipped": True,
            "reason": "Image file not found",
        })
        return {
            "current_agent": "image_to_story",
            "agent_trace": trace,
            "llm_calls": llm_calls,
        }

    image_bytes = Path(image_path).read_bytes()

    parts: list[types.Part] = [
        types.Part.from_text(text=IMAGE_TO_STORY_PROMPT),
        types.Part.from_bytes(data=image_bytes, mime_type=image_mime),
    ]
    if original_text.strip():
        parts.append(types.Part.from_text(
            text=f"\nUser guidance: {original_text}"
        ))

    client = genai.Client(api_key=settings.google_api_key)
    model = settings.gemini_model

    start = time.perf_counter()
    try:
        response = await client.aio.models.generate_content(
            model=model,
            contents=types.Content(role="user", parts=parts),
            config=types.GenerateContentConfig(
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
        concept = json.loads(raw_text[json_start:json_end]) if json_start >= 0 else {}

        synopsis = concept.get("synopsis", original_text)
        title = concept.get("title", "")

        # Prepend title to synopsis for a richer input_text
        enriched_text = f"{title}\n\n{synopsis}" if title else synopsis

        llm_calls.append({
            "agent": "image_to_story",
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
            "agent": "image_to_story",
            "timestamp": time.time(),
            "title": title,
            "num_characters": len(concept.get("characters", [])),
            "num_scenes": concept.get("num_scenes", 0),
            "mood": concept.get("mood", ""),
        })

        logger.info(
            "Image-to-Story: extracted concept '%s' with %d characters [request_id=%s]",
            title, len(concept.get("characters", [])), request_id,
        )

        return {
            "current_agent": "image_to_story",
            "input_text": enriched_text,
            "story_concept": concept,
            "agent_trace": trace,
            "llm_calls": llm_calls,
        }

    except Exception as e:
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.warning(
            "Image-to-Story failed [request_id=%s]: %s", request_id, e,
        )
        trace.append({
            "agent": "image_to_story",
            "timestamp": time.time(),
            "error": str(e),
        })
        # Non-fatal: fall through with original text
        return {
            "current_agent": "image_to_story",
            "agent_trace": trace,
            "llm_calls": llm_calls,
        }
