"""Narration audio node — synthesizes WAV audio per panel via Gemini TTS.

Uses google.genai.Client directly (same pattern as storyboard_coherence) to call
the Gemini TTS model.  Each panel with narration_text gets a WAV file saved to
the output directory.

Non-fatal: individual panel failures don't block others, and a complete node
failure still allows the pipeline to continue without audio.
"""

import logging
import struct
import time
from pathlib import Path

from google import genai
from google.genai import types

from chronocanvas.agents.story.state import StoryState
from chronocanvas.config import settings
from chronocanvas.llm.providers.gemini import gemini_generate_with_timeout
from chronocanvas.services.progress import ProgressPublisher

logger = logging.getLogger(__name__)


def _write_wav(
    pcm_data: bytes, sample_rate: int, num_channels: int, sample_width: int, path: Path
) -> None:
    """Write raw PCM data as a WAV file."""
    data_size = len(pcm_data)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        # RIFF header
        f.write(b"RIFF")
        f.write(struct.pack("<I", 36 + data_size))
        f.write(b"WAVE")
        # fmt chunk
        f.write(b"fmt ")
        f.write(struct.pack("<I", 16))  # chunk size
        f.write(struct.pack("<H", 1))  # PCM format
        f.write(struct.pack("<H", num_channels))
        f.write(struct.pack("<I", sample_rate))
        f.write(struct.pack("<I", sample_rate * num_channels * sample_width))  # byte rate
        f.write(struct.pack("<H", num_channels * sample_width))  # block align
        f.write(struct.pack("<H", sample_width * 8))  # bits per sample
        # data chunk
        f.write(b"data")
        f.write(struct.pack("<I", data_size))
        f.write(pcm_data)


async def narration_audio_node(state: StoryState) -> StoryState:
    request_id = state.get("request_id", "unknown")
    panels = list(state.get("panels", []))
    logger.info(
        "Narration audio: synthesizing for %d panels [request_id=%s]",
        len(panels),
        request_id,
    )

    trace = list(state.get("agent_trace", []))
    llm_calls = list(state.get("llm_calls", []))

    # Filter to panels that have narration text
    panels_with_text = [(i, p) for i, p in enumerate(panels) if p.get("narration_text")]

    if not panels_with_text:
        logger.info("Skipping narration audio: no panels with narration text")
        trace.append(
            {
                "agent": "narration_audio",
                "timestamp": time.time(),
                "skipped": True,
                "reason": "No panels with narration text",
            }
        )
        return {
            "current_agent": "narration_audio",
            "agent_trace": trace,
            "llm_calls": llm_calls,
        }

    client = genai.Client(api_key=settings.google_api_key)
    model = settings.tts_model
    voice = settings.tts_voice

    audio_dir = Path(settings.output_dir) / request_id / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    audio_paths: list[str] = []
    synthesized_count = 0
    channel = f"generation:{request_id}"
    progress = ProgressPublisher()
    total_audio = len(panels_with_text)

    for idx, panel in panels_with_text:
        scene_idx = panel.get("scene_index", idx)
        narration = panel["narration_text"]

        start = time.perf_counter()
        try:
            response = await gemini_generate_with_timeout(
                client,
                model=model,
                contents=narration,
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                voice_name=voice,
                            ),
                        ),
                    ),
                ),
            )
            elapsed_ms = (time.perf_counter() - start) * 1000

            # Extract audio data from response
            audio_part = None
            if response.candidates:
                for part in response.candidates[0].content.parts:
                    if part.inline_data and part.inline_data.mime_type.startswith("audio/"):
                        audio_part = part
                        break

            if audio_part is None:
                logger.warning(
                    "No audio in TTS response for scene %d [request_id=%s]",
                    scene_idx,
                    request_id,
                )
                continue

            wav_path = audio_dir / f"scene_{scene_idx}.wav"

            # Gemini TTS returns raw PCM audio (24kHz, mono, 16-bit)
            _write_wav(
                pcm_data=audio_part.inline_data.data,
                sample_rate=24000,
                num_channels=1,
                sample_width=2,
                path=wav_path,
            )

            panel["narration_audio_path"] = str(wav_path)
            audio_paths.append(str(wav_path))
            synthesized_count += 1

            await progress.publish_artifact(
                channel,
                artifact_type="audio",
                scene_index=scene_idx,
                total=total_audio,
                completed=synthesized_count,
                url=f"/output/{request_id}/audio/scene_{scene_idx}.wav",
                mime_type="audio/wav",
            )

            # Record LLM call for cost tracking
            input_tokens = 0
            output_tokens = 0
            if response.usage_metadata:
                input_tokens = response.usage_metadata.prompt_token_count or 0
                output_tokens = response.usage_metadata.candidates_token_count or 0

            llm_calls.append(
                {
                    "agent": "narration_audio",
                    "timestamp": time.time(),
                    "provider": "gemini",
                    "model": model,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "cost": 0,  # TTS pricing TBD
                    "duration_ms": elapsed_ms,
                    "requested_provider": "gemini",
                    "fallback": False,
                }
            )

            logger.info(
                "Synthesized audio for scene %d (%.0fms) [request_id=%s]",
                scene_idx,
                elapsed_ms,
                request_id,
            )

        except Exception as e:
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.warning(
                "TTS failed for scene %d [request_id=%s]: %s",
                scene_idx,
                request_id,
                e,
            )
            # Non-fatal: skip this panel's audio

    trace.append(
        {
            "agent": "narration_audio",
            "timestamp": time.time(),
            "panels_synthesized": synthesized_count,
            "total_with_text": len(panels_with_text),
            "audio_dir": str(audio_dir),
        }
    )

    logger.info(
        "Narration audio complete: %d/%d panels [request_id=%s]",
        synthesized_count,
        len(panels_with_text),
        request_id,
    )

    return {
        "current_agent": "narration_audio",
        "panels": panels,
        "narration_audio_paths": audio_paths,
        "agent_trace": trace,
        "llm_calls": llm_calls,
    }
