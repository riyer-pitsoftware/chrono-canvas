"""Live Video — Veo scene video generation for Live Story.

After Live Story generates scenes (text + images), this endpoint accepts
scene data and generates short cinematic video clips using Google's Veo API.
Each scene image is used as a first frame (image-to-video) with the scene
text as a prompt, preserving character consistency.

Videos stream back as SSE events as each completes (~1-3 min per clip).
"""

import asyncio
import base64
import io
import json
import logging
import shutil
import tempfile
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from google import genai
from google.genai import types
from pydantic import BaseModel

from chronocanvas.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/live-video", tags=["live-video"])

# Veo models — fast (cheaper) first, then standard quality
_VEO_MODEL_CHAIN = [
    "veo-3.1-generate-preview",      # $0.15/sec fast
    "veo-3.0-fast-generate-001",      # fallback
]

# Max concurrent Veo operations (avoid quota exhaustion)
_MAX_CONCURRENT = 3

# Poll interval for Veo operations (seconds)
_POLL_INTERVAL = 5.0

# Max wait for a single Veo operation (seconds)
_VEO_TIMEOUT = 300

# Noir style prefix injected into every Veo prompt
_VEO_STYLE_PREFIX = (
    "Cinematic noir film, 35mm film grain, practical lighting, "
    "shallow depth of field. Shot on anamorphic lens. "
    "Slow deliberate camera movement. "
)


class SceneInput(BaseModel):
    text: str
    image_base64: str
    mime_type: str = "image/png"


class SceneVideoRequest(BaseModel):
    scenes: list[SceneInput]
    style: str | None = None
    aspect_ratio: str = "16:9"


class AssembleRequest(BaseModel):
    video_base64_list: list[str]  # base64-encoded MP4 clips
    narration_urls: list[str] | None = None  # optional audio overlay paths


# ── SSE helpers (same pattern as live_story.py) ─────────────────


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


def _stage_event(
    stage: str,
    status: str,
    *,
    elapsed_s: float | None = None,
    scene_idx: int | None = None,
    detail: str | None = None,
) -> dict:
    evt: dict = {"type": "stage", "stage": stage, "status": status}
    if elapsed_s is not None:
        evt["elapsed_s"] = round(elapsed_s, 1)
    if scene_idx is not None:
        evt["scene_idx"] = scene_idx
    if detail:
        evt["detail"] = detail
    return evt


# ── Veo generation for a single scene ───────────────────────────


async def _generate_scene_video(
    client: genai.Client,
    scene: SceneInput,
    scene_idx: int,
    style: str | None,
    aspect_ratio: str,
) -> dict:
    """Generate a Veo video for a single scene. Returns SSE event dict."""
    t0 = time.perf_counter()

    # Build prompt with noir styling
    prompt_parts = [_VEO_STYLE_PREFIX]
    if style:
        prompt_parts.append(f"{style}. ")
    prompt_parts.append(scene.text)
    prompt = "".join(prompt_parts)

    # Decode scene image for first-frame reference
    raw_image_bytes = base64.b64decode(scene.image_base64)

    # Upload image as a file — Veo may reject raw image bytes (SDK issue #1988)
    # Fall back to types.Image if upload fails
    reference_image = None
    uploaded_file = None
    try:
        uploaded_file = await client.aio.files.upload(
            file=io.BytesIO(raw_image_bytes),
            config={"mime_type": scene.mime_type},
        )
        reference_image = uploaded_file
        logger.info("Veo scene %d: uploaded reference image as file", scene_idx)
    except Exception as upload_err:
        logger.warning(
            "Veo scene %d: file upload failed (%s), falling back to inline image",
            scene_idx, upload_err,
        )
        reference_image = types.Image(
            image_bytes=raw_image_bytes,
            mime_type=scene.mime_type,
        )

    last_error = None
    for model in _VEO_MODEL_CHAIN:
        try:
            operation = await asyncio.wait_for(
                client.aio.models.generate_videos(
                    model=model,
                    prompt=prompt,
                    image=reference_image,
                    config=types.GenerateVideosConfig(
                        duration_seconds=6,
                        aspect_ratio=aspect_ratio,
                        person_generation="allow_adult",
                    ),
                ),
                timeout=30,  # timeout for initial API call only
            )

            # Poll until complete
            elapsed = 0.0
            while not operation.done and elapsed < _VEO_TIMEOUT:
                await asyncio.sleep(_POLL_INTERVAL)
                elapsed = time.perf_counter() - t0
                operation = await client.aio.operations.get(operation)

            if not operation.done:
                raise TimeoutError(f"Veo operation timed out after {_VEO_TIMEOUT}s")

            # Extract video — try operation.response first (documented),
            # fall back to operation.result (older SDK versions)
            response = getattr(operation, "response", None) or getattr(operation, "result", None)
            if not response or not response.generated_videos:
                raise RuntimeError("Veo returned no video")

            video = response.generated_videos[0]
            video_data = video.video
            logger.info(
                "Veo scene %d response format: type=%s, has_bytes=%s, has_uri=%s",
                scene_idx,
                type(video_data).__name__,
                bool(getattr(video_data, "video_bytes", None)),
                bool(getattr(video_data, "uri", None)),
            )

            # Download video file if bytes not yet populated
            # (SDK requires client.files.download() before video_bytes is available)
            if not getattr(video_data, "video_bytes", None):
                try:
                    await client.aio.files.download(file=video_data)
                    logger.info("Veo scene %d: downloaded video via files.download()", scene_idx)
                except Exception as dl_err:
                    logger.warning("Veo scene %d: files.download() failed: %s", scene_idx, dl_err)

            # Extract bytes — inline, post-download, or via URI
            if getattr(video_data, "video_bytes", None):
                video_bytes = video_data.video_bytes
            elif getattr(video_data, "uri", None):
                import httpx
                async with httpx.AsyncClient() as http:
                    resp = await http.get(video_data.uri, timeout=60)
                    resp.raise_for_status()
                    video_bytes = resp.content
                logger.info("Veo scene %d: downloaded video from URI fallback", scene_idx)
            else:
                raise RuntimeError(
                    f"Veo returned unrecognized video format: {type(video_data)}, "
                    f"attrs={[a for a in dir(video_data) if not a.startswith('_')]}"
                )

            video_b64 = base64.b64encode(video_bytes).decode("ascii")

            elapsed_s = time.perf_counter() - t0
            logger.info(
                "Veo scene %d complete: model=%s, %.1fs",
                scene_idx, model, elapsed_s,
            )
            return {
                "type": "scene_video",
                "scene_idx": scene_idx,
                "video_base64": video_b64,
                "mime_type": "video/mp4",
                "model": model,
                "elapsed_s": round(elapsed_s, 1),
            }

        except Exception as e:
            last_error = e
            logger.warning(
                "Veo scene %d failed with model %s: %s",
                scene_idx, model, e,
            )
            continue

    elapsed_s = time.perf_counter() - t0
    logger.error("Veo scene %d: all models failed: %s", scene_idx, last_error)
    return {
        "type": "scene_video_error",
        "scene_idx": scene_idx,
        "error": str(last_error),
        "elapsed_s": round(elapsed_s, 1),
    }


# ── POST /api/live-video/generate ───────────────────────────────


@router.post("/generate")
async def generate_videos(req: SceneVideoRequest):
    """Generate Veo video clips for each scene via SSE streaming.

    Each scene's image is used as first-frame reference + text as prompt.
    Videos stream back as they complete (1-3 min each).
    """
    if not settings.veo_video_enabled:
        raise HTTPException(status_code=503, detail="Veo video generation is disabled")
    if not settings.google_api_key:
        raise HTTPException(status_code=503, detail="GOOGLE_API_KEY not configured")
    if not req.scenes:
        raise HTTPException(status_code=400, detail="No scenes provided")

    client = genai.Client(api_key=settings.google_api_key)

    async def event_stream():
        start_time = time.perf_counter()
        total = len(req.scenes)

        yield _sse(_stage_event("init", "start", detail=f"{total} scenes"))
        yield _sse(_stage_event("init", "complete", elapsed_s=0.0))

        # Process scenes with bounded concurrency
        semaphore = asyncio.Semaphore(_MAX_CONCURRENT)
        completed = 0
        errors = 0

        async def process_scene(idx: int, scene: SceneInput):
            async with semaphore:
                return await _generate_scene_video(
                    client, scene, idx, req.style, req.aspect_ratio,
                )

        # Launch all tasks
        tasks = [
            asyncio.create_task(process_scene(i, scene))
            for i, scene in enumerate(req.scenes)
        ]

        # Yield results as they complete
        for coro in asyncio.as_completed(tasks):
            result = await coro
            scene_idx = result.get("scene_idx", -1)

            if result["type"] == "scene_video":
                completed += 1
                yield _sse(_stage_event(
                    "scene", "complete",
                    scene_idx=scene_idx + 1,
                    elapsed_s=result.get("elapsed_s"),
                    detail=result.get("model"),
                ))
            else:
                errors += 1
                yield _sse(_stage_event(
                    "scene", "error",
                    scene_idx=scene_idx + 1,
                    elapsed_s=result.get("elapsed_s"),
                    detail=result.get("error"),
                ))

            yield _sse(result)

        elapsed = time.perf_counter() - start_time
        yield _sse({
            "type": "film_complete",
            "total_scenes": total,
            "completed": completed,
            "errors": errors,
            "elapsed_s": round(elapsed, 1),
        })

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── POST /api/live-video/assemble ───────────────────────────────


async def _check_ffmpeg() -> bool:
    try:
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-version",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
        return proc.returncode == 0
    except FileNotFoundError:
        return False


@router.post("/assemble")
async def assemble_film(req: AssembleRequest):
    """Concatenate individual Veo clips into a single MP4 film.

    Optionally muxes narration audio overlay from live-voice.
    Returns the assembled video as base64.
    """
    if not settings.veo_video_enabled:
        raise HTTPException(status_code=503, detail="Veo video generation is disabled")
    if not req.video_base64_list:
        raise HTTPException(status_code=400, detail="No video clips provided")
    if not await _check_ffmpeg():
        raise HTTPException(status_code=503, detail="ffmpeg not available on server")

    tmpdir = tempfile.mkdtemp(prefix="chrono_assemble_")
    try:
        # Write individual clips to temp files
        clip_paths = []
        for i, b64 in enumerate(req.video_base64_list):
            clip_path = Path(tmpdir) / f"clip_{i:03d}.mp4"
            clip_path.write_bytes(base64.b64decode(b64))
            clip_paths.append(clip_path)

        # Build ffmpeg concat demuxer file
        concat_file = Path(tmpdir) / "concat.txt"
        concat_file.write_text(
            "\n".join(f"file '{p}'" for p in clip_paths)
        )

        output_path = Path(tmpdir) / "film.mp4"

        # Concat clips
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(concat_file),
            "-c", "copy",
            str(output_path),
        ]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()

        if proc.returncode != 0:
            logger.error("Film assembly failed: %s", stderr.decode()[-500:])
            raise HTTPException(
                status_code=500,
                detail="Film assembly failed — ffmpeg error",
            )

        # If narration audio URLs provided, mux audio
        if req.narration_urls:
            final_path = Path(tmpdir) / "film_with_audio.mp4"

            # Download and concat narration audio files
            audio_paths = []
            for url in req.narration_urls:
                # URLs are local paths like /output/.../scene_0.wav
                local_path = Path(settings.output_dir) / url.lstrip("/output/")
                if local_path.exists():
                    audio_paths.append(str(local_path))

            if audio_paths:
                # Concat audio
                audio_concat = Path(tmpdir) / "narration.wav"
                audio_list = Path(tmpdir) / "audio_list.txt"
                audio_list.write_text(
                    "\n".join(f"file '{p}'" for p in audio_paths)
                )
                audio_cmd = [
                    "ffmpeg", "-y",
                    "-f", "concat", "-safe", "0",
                    "-i", str(audio_list),
                    "-c", "copy",
                    str(audio_concat),
                ]
                proc = await asyncio.create_subprocess_exec(
                    *audio_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await proc.communicate()

                # Mux video + audio
                mux_cmd = [
                    "ffmpeg", "-y",
                    "-i", str(output_path),
                    "-i", str(audio_concat),
                    "-c:v", "copy",
                    "-c:a", "aac",
                    "-shortest",
                    str(final_path),
                ]
                proc = await asyncio.create_subprocess_exec(
                    *mux_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await proc.communicate()

                if proc.returncode == 0:
                    output_path = final_path

        # Read and return as base64
        video_bytes = output_path.read_bytes()
        video_b64 = base64.b64encode(video_bytes).decode("ascii")

        return {
            "video_base64": video_b64,
            "mime_type": "video/mp4",
            "size_bytes": len(video_bytes),
        }

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
