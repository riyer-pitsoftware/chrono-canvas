"""Live Story — interleaved text+image generation via Gemini 2.0 Flash."""

import base64
import json
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from google import genai
from google.genai import types
from pydantic import BaseModel

from chronocanvas.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/live-story", tags=["live-story"])


class LiveStoryRequest(BaseModel):
    prompt: str
    style: str | None = None
    era: str | None = None


def _build_prompt(req: LiveStoryRequest) -> str:
    parts = [
        "You are a noir-style visual storyteller. Generate a short illustrated story "
        "with interleaved text paragraphs and images. Each image should depict the scene "
        "described in the preceding text. Use a cinematic, dramatic tone."
    ]
    if req.style:
        parts.append(f"Art style: {req.style}.")
    if req.era:
        parts.append(f"Historical era: {req.era}.")
    parts.append(f"\nStory prompt: {req.prompt}")
    return "\n".join(parts)


@router.post("")
async def live_story(req: LiveStoryRequest):
    """Stream interleaved text+image story as SSE events."""
    if not settings.google_api_key:
        raise HTTPException(status_code=503, detail="GOOGLE_API_KEY not configured")

    client = genai.Client(api_key=settings.google_api_key)
    prompt = _build_prompt(req)

    async def event_stream():
        try:
            response = await client.aio.models.generate_content(
                model="gemini-2.0-flash-exp",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["TEXT", "IMAGE"],
                    temperature=1.0,
                    max_output_tokens=8192,
                ),
            )

            for part in response.candidates[0].content.parts:
                if part.text is not None:
                    event = {"type": "text", "content": part.text}
                    yield f"data: {json.dumps(event)}\n\n"
                elif part.inline_data is not None:
                    b64 = base64.b64encode(part.inline_data.data).decode("ascii")
                    event = {
                        "type": "image",
                        "content": b64,
                        "mime_type": part.inline_data.mime_type or "image/png",
                    }
                    yield f"data: {json.dumps(event)}\n\n"

            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except Exception as e:
            logger.error("Live story generation failed: %s", e)
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
