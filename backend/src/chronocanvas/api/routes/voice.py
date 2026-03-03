"""Voice input — Gemini multimodal speech-to-text."""

import logging
import time

from fastapi import APIRouter, HTTPException, UploadFile
from google import genai
from google.genai import types

from chronocanvas.config import settings
from chronocanvas.llm.providers.gemini import GEMINI_PRICING

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/voice", tags=["voice"])

ALLOWED_AUDIO_TYPES = {
    "audio/webm", "audio/wav", "audio/wave", "audio/x-wav",
    "audio/ogg", "audio/mpeg", "audio/mp4",
}
MAX_AUDIO_SIZE = 25 * 1024 * 1024  # 25MB


@router.post("/transcribe")
async def transcribe_audio(file: UploadFile):
    if not settings.voice_input_enabled:
        raise HTTPException(status_code=503, detail="Voice input is disabled")

    content_type = file.content_type or "audio/webm"
    if content_type not in ALLOWED_AUDIO_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported audio type: {content_type}. Allowed: {sorted(ALLOWED_AUDIO_TYPES)}",
        )

    data = await file.read()
    if len(data) > MAX_AUDIO_SIZE:
        raise HTTPException(status_code=400, detail="Audio file exceeds 25MB limit")

    if len(data) < 100:
        raise HTTPException(status_code=400, detail="Audio file too small")

    client = genai.Client(api_key=settings.google_api_key)
    model = settings.gemini_model

    parts = [
        types.Part.from_bytes(data=data, mime_type=content_type),
        types.Part.from_text(
            text="Transcribe this audio. Return ONLY the transcription text, nothing else."
        ),
    ]

    start = time.perf_counter()
    try:
        response = await client.aio.models.generate_content(
            model=model,
            contents=types.Content(role="user", parts=parts),
            config=types.GenerateContentConfig(
                temperature=0.0,
                max_output_tokens=1000,
            ),
        )
        elapsed_ms = (time.perf_counter() - start) * 1000

        transcript = (response.text or "").strip()
        input_tokens = response.usage_metadata.prompt_token_count or 0
        output_tokens = response.usage_metadata.candidates_token_count or 0
        pricing = GEMINI_PRICING.get(model, {"input": 0, "output": 0})
        cost = input_tokens * pricing["input"] + output_tokens * pricing["output"]

        logger.info(
            "Voice transcription: %d chars, %.0fms, $%.4f",
            len(transcript), elapsed_ms, cost,
        )

        return {
            "transcript": transcript,
            "duration_ms": elapsed_ms,
            "cost": cost,
        }

    except Exception as e:
        logger.error("Voice transcription failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Transcription failed: {e}")
