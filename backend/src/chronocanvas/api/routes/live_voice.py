"""Live Voice — Gemini Live API for voice narration + voice prompt."""

import base64
import io
import logging
import struct
import time

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from google import genai
from google.genai import types
from pydantic import BaseModel

from chronocanvas.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/live-voice", tags=["live-voice"])

LIVE_MODEL = "gemini-2.0-flash-live-001"
SAMPLE_RATE = 24000  # Live API outputs 24kHz PCM16


class NarrateRequest(BaseModel):
    text: str
    voice_name: str | None = None


class VoicePromptRequest(BaseModel):
    audio_base64: str
    mime_type: str = "audio/webm"


def _pcm_to_wav(
    pcm_data: bytes, sample_rate: int = SAMPLE_RATE, channels: int = 1, bits: int = 16
) -> bytes:
    """Wrap raw PCM16 bytes in a WAV header."""
    data_size = len(pcm_data)
    buf = io.BytesIO()
    buf.write(b"RIFF")
    buf.write(struct.pack("<I", 36 + data_size))
    buf.write(b"WAVE")
    buf.write(b"fmt ")
    buf.write(struct.pack("<I", 16))
    buf.write(struct.pack("<H", 1))  # PCM
    buf.write(struct.pack("<H", channels))
    buf.write(struct.pack("<I", sample_rate))
    buf.write(struct.pack("<I", sample_rate * channels * bits // 8))
    buf.write(struct.pack("<H", channels * bits // 8))
    buf.write(struct.pack("<H", bits))
    buf.write(b"data")
    buf.write(struct.pack("<I", data_size))
    buf.write(pcm_data)
    return buf.getvalue()


@router.post("/narrate")
async def narrate(req: NarrateRequest):
    """Generate voice narration via Gemini Live API and return WAV audio."""
    if not settings.google_api_key:
        raise HTTPException(status_code=503, detail="GOOGLE_API_KEY not configured")

    client = genai.Client(api_key=settings.google_api_key)

    voice_config = None
    if req.voice_name:
        voice_config = types.VoiceConfig(
            prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=req.voice_name)
        )

    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        speech_config=types.SpeechConfig(voice_config=voice_config) if voice_config else None,
    )

    audio_chunks: list[bytes] = []

    try:
        async with client.aio.live.connect(model=LIVE_MODEL, config=config) as session:
            narrator_prompt = (
                "You are Dash, a noir narrator with a deep, gravelly voice. "
                "Read the following story text aloud with dramatic flair:\n\n"
                f"{req.text}"
            )
            await session.send(input=narrator_prompt, end_of_turn=True)

            async for response in session.receive():
                if response.server_content and response.server_content.model_turn:
                    for part in response.server_content.model_turn.parts:
                        if part.inline_data and part.inline_data.data:
                            audio_chunks.append(part.inline_data.data)
                if response.server_content and response.server_content.turn_complete:
                    break

    except Exception as e:
        logger.error("Live voice narration failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Narration failed: {e}")

    if not audio_chunks:
        raise HTTPException(status_code=500, detail="No audio generated")

    pcm_data = b"".join(audio_chunks)
    wav_data = _pcm_to_wav(pcm_data)

    return Response(content=wav_data, media_type="audio/wav")


@router.post("/prompt")
async def voice_prompt(req: VoicePromptRequest):
    """Transcribe voice input and generate a creative story response."""
    if not settings.google_api_key:
        raise HTTPException(status_code=503, detail="GOOGLE_API_KEY not configured")

    client = genai.Client(api_key=settings.google_api_key)
    start = time.monotonic()

    try:
        audio_bytes = base64.b64decode(req.audio_base64)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 audio data")

    config = types.LiveConnectConfig(
        response_modalities=["TEXT"],
    )

    transcript = ""
    response_text = ""

    try:
        async with client.aio.live.connect(model=LIVE_MODEL, config=config) as session:
            instruction = (
                "The user has spoken a story idea. First transcribe exactly what they said "
                "on a line starting with 'TRANSCRIPT: ', then on a new line starting with "
                "'RESPONSE: ' give a creative noir-style expansion of their idea in 2-3 sentences."
            )
            await session.send(input=instruction, end_of_turn=False)

            # Send audio as inline data
            audio_part = types.Part(
                inline_data=types.Blob(data=audio_bytes, mime_type=req.mime_type)
            )
            await session.send(input=audio_part, end_of_turn=True)

            full_text = ""
            async for response in session.receive():
                if response.server_content and response.server_content.model_turn:
                    for part in response.server_content.model_turn.parts:
                        if part.text:
                            full_text += part.text
                if response.server_content and response.server_content.turn_complete:
                    break

            # Parse TRANSCRIPT: and RESPONSE: sections
            for line in full_text.split("\n"):
                line = line.strip()
                if line.startswith("TRANSCRIPT:"):
                    transcript = line[len("TRANSCRIPT:") :].strip()
                elif line.startswith("RESPONSE:"):
                    response_text = line[len("RESPONSE:") :].strip()

            # Fallback: if parsing fails, use the whole text
            if not transcript and not response_text:
                response_text = full_text.strip()

    except Exception as e:
        logger.error("Live voice prompt failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Voice prompt failed: {e}")

    duration_ms = int((time.monotonic() - start) * 1000)

    return {
        "transcript": transcript,
        "response": response_text,
        "duration_ms": duration_ms,
    }
