"""Live Voice — Gemini native audio for voice narration + voice prompt."""

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

AUDIO_MODEL_PRIMARY = "gemini-2.5-flash-native-audio-latest"
AUDIO_MODEL_FALLBACK = "gemini-2.5-flash-native-audio-preview-12-2025"
SAMPLE_RATE = 24000  # Native audio outputs 24kHz PCM16


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
    """Generate voice narration via Gemini generate_content (HTTP, no WebSocket overhead)."""
    if not settings.google_api_key:
        raise HTTPException(status_code=503, detail="GOOGLE_API_KEY not configured")

    client = genai.Client(api_key=settings.google_api_key)

    voice_name = req.voice_name or "Charon"
    speech_config = types.SpeechConfig(
        voice_config=types.VoiceConfig(
            prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice_name)
        )
    )

    narrator_prompt = (
        "You are Dash, a noir narrator with a deep, gravelly voice. "
        "Read the following story text aloud with dramatic flair:\n\n"
        f"{req.text}"
    )

    last_error = None
    for model in (AUDIO_MODEL_PRIMARY, AUDIO_MODEL_FALLBACK):
        try:
            start = time.monotonic()
            logger.info("Narrate: trying model %s (generate_content)", model)
            response = await client.aio.models.generate_content(
                model=model,
                contents=narrator_prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=speech_config,
                ),
            )
            elapsed_ms = int((time.monotonic() - start) * 1000)

            # Extract audio from response
            audio_data = None
            if response.candidates:
                for part in response.candidates[0].content.parts:
                    if part.inline_data and part.inline_data.mime_type and part.inline_data.mime_type.startswith("audio/"):
                        audio_data = part.inline_data.data
                        break

            if audio_data is None:
                logger.warning("No audio in response from %s", model)
                continue

            logger.info("Narrate: %s returned %d bytes in %dms", model, len(audio_data), elapsed_ms)
            wav_data = _pcm_to_wav(audio_data)
            return Response(content=wav_data, media_type="audio/wav")

        except Exception as e:
            last_error = e
            logger.warning("Narrate model %s failed: %s, trying fallback", model, e)

    logger.error("Voice narration failed on all models: %s", last_error)
    raise HTTPException(status_code=500, detail=f"Narration failed: {last_error}")


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

    transcript = ""
    response_text = ""

    instruction = (
        "The user has spoken a story idea. First transcribe exactly what they said "
        "on a line starting with 'TRANSCRIPT: ', then on a new line starting with "
        "'RESPONSE: ' give a creative noir-style expansion of their idea in 2-3 sentences."
    )

    audio_part = types.Part(
        inline_data=types.Blob(data=audio_bytes, mime_type=req.mime_type)
    )

    last_error = None
    for model in (AUDIO_MODEL_PRIMARY, AUDIO_MODEL_FALLBACK):
        try:
            logger.info("Voice prompt: trying model %s (generate_content)", model)
            response = await client.aio.models.generate_content(
                model=model,
                contents=[instruction, audio_part],
                config=types.GenerateContentConfig(
                    response_modalities=["TEXT"],
                ),
            )

            full_text = response.text or ""

            # Parse TRANSCRIPT: and RESPONSE: sections
            for line in full_text.split("\n"):
                line = line.strip()
                if line.startswith("TRANSCRIPT:"):
                    transcript = line[len("TRANSCRIPT:"):].strip()
                elif line.startswith("RESPONSE:"):
                    response_text = line[len("RESPONSE:"):].strip()

            # Fallback: if parsing fails, use the whole text
            if not transcript and not response_text:
                response_text = full_text.strip()
            break  # success
        except Exception as e:
            last_error = e
            logger.warning("Voice prompt model %s failed: %s, trying fallback", model, e)

    if not transcript and not response_text and last_error:
        logger.error("Voice prompt failed on all models: %s", last_error)
        raise HTTPException(status_code=500, detail=f"Voice prompt failed: {last_error}")

    duration_ms = int((time.monotonic() - start) * 1000)

    return {
        "transcript": transcript,
        "response": response_text,
        "duration_ms": duration_ms,
    }
