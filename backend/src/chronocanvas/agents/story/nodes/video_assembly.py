"""Video assembly node — stitches scene images + narration audio into an MP4 video.

Uses ffmpeg to create a Ken Burns slideshow with crossfade transitions and
narration audio overlay. Runs after narration_audio, before storyboard_export.

OPTIONAL: only runs when video_assembly_enabled=True and ffmpeg is available.
Non-fatal: if ffmpeg fails, pipeline continues without video.
"""

import asyncio
import logging
import time
from pathlib import Path

from chronocanvas.agents.story.state import StoryState
from chronocanvas.config import settings
from chronocanvas.services.progress import ProgressPublisher

logger = logging.getLogger(__name__)

SECONDS_PER_PANEL = 5  # how long each panel is displayed
CROSSFADE_DURATION = 0.5


async def _check_ffmpeg() -> bool:
    """Check if ffmpeg is available."""
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


async def _create_slideshow(
    image_paths: list[str],
    output_path: str,
    fps: int = 30,
) -> bool:
    """Create a video slideshow from images with Ken Burns effect."""
    if not image_paths:
        return False

    # Build ffmpeg filter for slideshow with crossfade
    n = len(image_paths)
    panel_frames = SECONDS_PER_PANEL * fps

    # Simple approach: concat images with zoompan filter for Ken Burns
    inputs = []
    filter_parts = []
    for i, img_path in enumerate(image_paths):
        inputs.extend(["-loop", "1", "-t", str(SECONDS_PER_PANEL), "-i", img_path])
        # Alternate zoom direction for visual interest
        if i % 2 == 0:
            zoom_expr = f"min(zoom+0.0005,1.15)"
        else:
            zoom_expr = f"if(eq(on,1),1.15,max(zoom-0.0005,1.0))"
        filter_parts.append(
            f"[{i}:v]scale=1920:1080:force_original_aspect_ratio=decrease,"
            f"pad=1920:1080:(ow-iw)/2:(oh-ih)/2,"
            f"zoompan=z='{zoom_expr}':d={panel_frames}:s=1920x1080:fps={fps},"
            f"setpts=PTS-STARTPTS[v{i}]"
        )

    # Concat all video streams
    concat_inputs = "".join(f"[v{i}]" for i in range(n))
    filter_complex = ";".join(filter_parts) + f";{concat_inputs}concat=n={n}:v=1:a=0[outv]"

    cmd = ["ffmpeg", "-y"] + inputs + [
        "-filter_complex", filter_complex,
        "-map", "[outv]",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-pix_fmt", "yuv420p",
        output_path,
    ]

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        logger.warning("ffmpeg slideshow failed: %s", stderr.decode()[-500:])
        return False
    return True


async def _mux_audio(
    video_path: str,
    audio_paths: list[str],
    output_path: str,
) -> bool:
    """Mux narration audio onto the video slideshow."""
    if not audio_paths:
        # No audio — just copy video
        import shutil
        shutil.copy2(video_path, output_path)
        return True

    # Concatenate all audio files with silence gaps
    audio_inputs = []
    filter_parts = []
    for i, ap in enumerate(audio_paths):
        if Path(ap).exists():
            audio_inputs.extend(["-i", ap])
            # Pad each audio clip to match panel duration
            filter_parts.append(
                f"[{i}:a]apad=whole_dur={SECONDS_PER_PANEL}[a{i}]"
            )

    if not audio_inputs:
        import shutil
        shutil.copy2(video_path, output_path)
        return True

    n_audio = len(audio_inputs) // 2
    concat_audio = "".join(f"[a{i}]" for i in range(n_audio))
    filter_complex = ";".join(filter_parts) + f";{concat_audio}concat=n={n_audio}:v=0:a=1[outa]"

    # First create concatenated audio
    audio_concat_path = output_path.replace(".mp4", "_audio.wav")
    cmd_audio = ["ffmpeg", "-y"] + audio_inputs + [
        "-filter_complex", filter_complex,
        "-map", "[outa]",
        audio_concat_path,
    ]

    proc = await asyncio.create_subprocess_exec(
        *cmd_audio,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        logger.warning("Audio concat failed: %s", stderr.decode()[-300:])
        import shutil
        shutil.copy2(video_path, output_path)
        return True

    # Then mux video + audio
    cmd_mux = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", audio_concat_path,
        "-c:v", "copy",
        "-c:a", "aac",
        "-shortest",
        output_path,
    ]

    proc = await asyncio.create_subprocess_exec(
        *cmd_mux,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()

    # Clean up temp audio
    Path(audio_concat_path).unlink(missing_ok=True)

    if proc.returncode != 0:
        logger.warning("Audio mux failed: %s", stderr.decode()[-300:])
        import shutil
        shutil.copy2(video_path, output_path)

    return True


async def video_assembly_node(state: StoryState) -> StoryState:
    request_id = state.get("request_id", "unknown")
    panels = list(state.get("panels", []))
    logger.info(
        "Video assembly: %d panels [request_id=%s]",
        len(panels), request_id,
    )

    trace = list(state.get("agent_trace", []))

    if not settings.video_assembly_enabled:
        trace.append({
            "agent": "video_assembly",
            "timestamp": time.time(),
            "skipped": True,
            "reason": "Video assembly disabled",
        })
        return {
            "current_agent": "video_assembly",
            "agent_trace": trace,
        }

    if not await _check_ffmpeg():
        logger.warning("ffmpeg not available, skipping video assembly [request_id=%s]", request_id)
        trace.append({
            "agent": "video_assembly",
            "timestamp": time.time(),
            "skipped": True,
            "reason": "ffmpeg not available",
        })
        return {
            "current_agent": "video_assembly",
            "agent_trace": trace,
        }

    completed_panels = sorted(
        [p for p in panels if p.get("status") == "completed" and p.get("image_path")],
        key=lambda p: p.get("scene_index", 0),
    )

    if len(completed_panels) < 2:
        trace.append({
            "agent": "video_assembly",
            "timestamp": time.time(),
            "skipped": True,
            "reason": f"Only {len(completed_panels)} completed panels",
        })
        return {
            "current_agent": "video_assembly",
            "agent_trace": trace,
        }

    export_dir = Path(settings.output_dir) / request_id / "export"
    export_dir.mkdir(parents=True, exist_ok=True)

    image_paths = [p["image_path"] for p in completed_panels]
    slideshow_path = str(export_dir / "slideshow.mp4")
    final_path = str(export_dir / "storyboard.mp4")

    start = time.perf_counter()
    try:
        # Step 1: Create slideshow
        slideshow_ok = await _create_slideshow(image_paths, slideshow_path)
        if not slideshow_ok:
            raise RuntimeError("Slideshow creation failed")

        # Step 2: Mux audio
        audio_dir = Path(settings.output_dir) / request_id / "audio"
        audio_paths = [
            str(audio_dir / f"scene_{p.get('scene_index', i)}.wav")
            for i, p in enumerate(completed_panels)
        ]
        await _mux_audio(slideshow_path, audio_paths, final_path)

        # Clean up intermediate
        Path(slideshow_path).unlink(missing_ok=True)

        elapsed_ms = (time.perf_counter() - start) * 1000

        # Publish video artifact
        publisher = ProgressPublisher()
        channel = f"generation:{request_id}"
        video_url = f"/output/{request_id}/export/storyboard.mp4"
        await publisher.publish_artifact(
            channel,
            artifact_type="video",
            scene_index=None,
            total=1,
            completed=1,
            url=video_url,
            mime_type="video/mp4",
        )

        trace.append({
            "agent": "video_assembly",
            "timestamp": time.time(),
            "panels_used": len(completed_panels),
            "video_path": final_path,
            "duration_ms": elapsed_ms,
        })

        logger.info(
            "Video assembly complete: %d panels → %s (%.0fms) [request_id=%s]",
            len(completed_panels), final_path, elapsed_ms, request_id,
        )

    except Exception as e:
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.warning(
            "Video assembly failed [request_id=%s]: %s",
            request_id, e,
        )
        trace.append({
            "agent": "video_assembly",
            "timestamp": time.time(),
            "error": str(e),
        })

    return {
        "current_agent": "video_assembly",
        "agent_trace": trace,
    }
