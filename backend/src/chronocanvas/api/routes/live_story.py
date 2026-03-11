"""Live Story — interleaved text+image generation via Gemini 2.0 Flash.

The mandatory track feature for the hackathon: true interleaved multimodal
output where text and images arrive together in a single response.
"""

import base64
import json
import logging
import time

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from google import genai
from google.genai import types
from pydantic import BaseModel

from chronocanvas.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/live-story", tags=["live-story"])

# Models to try in order — first one that supports TEXT+IMAGE wins
_MODEL_CHAIN = [
    "gemini-2.5-flash-image",
]

DASH_SYSTEM_INSTRUCTION = """\
You are Dash, a noir creative director and cinematographer.

OUTPUT FORMAT:
1. Tell a complete short story in 3-5 scenes.
2. ALTERNATE text and images: text → image → text → image → text (→ image).
3. Each text paragraph: 2-4 sentences, noir prose, present tense.
4. End with a line that lingers.

Voice: clipped, direct, occasionally lyrical. Every word earns its place."""

# Injected into every prompt to force photorealistic image output
_PHOTO_STYLE_PREFIX = """\
IMAGE STYLE REQUIREMENT: Generate all images as photorealistic photographs. \
Shot on 35mm film, Canon EOS R5, 50mm f/1.4 lens. Shallow depth of field, \
natural film grain, practical lighting only. Real people, real places, real textures. \
The images must look like still frames from a real movie — NOT illustrations, \
NOT drawings, NOT comics, NOT cartoons, NOT digital art, NOT paintings. \
Photorealistic only.

"""


class HistoryPart(BaseModel):
    """A previously generated part — text or image reference."""

    type: str  # "text" or "image"
    content: str  # text content or base64 image data
    mime_type: str | None = None


class LiveStoryRequest(BaseModel):
    prompt: str
    style: str | None = None
    era: str | None = None
    num_scenes: int = 4
    history: list[HistoryPart] | None = None  # prior turns for continuation
    original_prompt: str | None = None  # original prompt (for continuation)


def _build_prompt(req: LiveStoryRequest) -> str:
    parts = [_PHOTO_STYLE_PREFIX]
    if req.style:
        parts.append(f"Art style: {req.style}.")
    if req.era:
        parts.append(f"Historical era: {req.era}.")
    parts.append(f"Number of scenes: {req.num_scenes}.")
    parts.append(f"\nStory prompt: {req.prompt}")
    return "\n".join(parts)


def _build_contents(
    req: LiveStoryRequest,
) -> list[types.Content]:
    """Build multi-turn contents array for Gemini.

    For initial generation: single user turn with the prompt.
    For continuation: user prompt → model response (history) → user continuation.
    """
    if not req.history:
        # First generation — simple single-turn
        return _build_prompt(req)

    # Multi-turn: reconstruct conversation
    # Build the original prompt for turn 1
    orig = LiveStoryRequest(
        prompt=req.original_prompt or req.prompt,
        style=req.style,
        era=req.era,
        num_scenes=req.num_scenes,
    )
    initial_prompt = _build_prompt(orig)

    # Turn 1: original user prompt
    contents: list[types.Content] = [
        types.Content(role="user", parts=[types.Part.from_text(text=initial_prompt)])
    ]

    # Turn 2: model's previous response (the history parts)
    model_parts = []
    for hp in req.history:
        if hp.type == "text":
            model_parts.append(types.Part.from_text(text=hp.content))
        elif hp.type == "image" and hp.content:
            image_bytes = base64.b64decode(hp.content)
            model_parts.append(
                types.Part.from_bytes(
                    data=image_bytes, mime_type=hp.mime_type or "image/png"
                )
            )

    if model_parts:
        contents.append(types.Content(role="model", parts=model_parts))

    # Turn 3: user's continuation prompt
    continuation = (
        f"Continue the story. The audience says: {req.prompt}\n"
        f"Generate 2-3 more scenes continuing from where you left off. "
        f"Maintain the same characters, setting, and noir tone."
    )
    contents.append(
        types.Content(role="user", parts=[types.Part.from_text(text=continuation)])
    )

    return contents


@router.post("")
async def live_story(req: LiveStoryRequest):
    """Stream interleaved text+image story as SSE events."""
    if not settings.google_api_key:
        raise HTTPException(status_code=503, detail="GOOGLE_API_KEY not configured")

    client = genai.Client(api_key=settings.google_api_key)
    contents = _build_contents(req)
    is_continuation = req.history is not None and len(req.history) > 0

    async def event_stream():
        start_time = time.perf_counter()
        model_used = None
        text_count = 0
        image_count = 0

        # Status: starting
        status_msg = (
            "Dash picks up the thread..."
            if is_continuation
            else "Dash is setting the scene..."
        )
        yield _sse({"type": "status", "content": status_msg})

        # Try models in order
        response = None
        last_error = None
        for model in _MODEL_CHAIN:
            try:
                response = await client.aio.models.generate_content(
                    model=model,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=DASH_SYSTEM_INSTRUCTION,
                        response_modalities=["TEXT", "IMAGE"],
                        temperature=1.0,
                        max_output_tokens=8192,
                    ),
                )
                model_used = model
                break
            except Exception as e:
                last_error = e
                logger.warning("Model %s failed for live story: %s", model, e)
                continue

        if response is None:
            yield _sse({"type": "error", "content": f"All models failed: {last_error}"})
            return

        # Validate response
        if not response.candidates or not response.candidates[0].content.parts:
            yield _sse({"type": "error", "content": "Gemini returned empty response"})
            return

        yield _sse({"type": "status", "content": "The story unfolds..."})

        # Stream parts
        for i, part in enumerate(response.candidates[0].content.parts):
            if part.text is not None:
                text_count += 1
                yield _sse({"type": "text", "content": part.text})
            elif part.inline_data is not None:
                image_count += 1
                b64 = base64.b64encode(part.inline_data.data).decode("ascii")
                yield _sse(
                    {
                        "type": "image",
                        "content": b64,
                        "mime_type": part.inline_data.mime_type or "image/png",
                    }
                )

        elapsed = time.perf_counter() - start_time
        yield _sse(
            {
                "type": "done",
                "model": model_used,
                "elapsed_s": round(elapsed, 1),
                "text_parts": text_count,
                "image_parts": image_count,
            }
        )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"
