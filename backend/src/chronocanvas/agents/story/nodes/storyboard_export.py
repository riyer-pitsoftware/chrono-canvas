import json
import logging
import time
from pathlib import Path

from chronocanvas.agents.story.state import StoryState
from chronocanvas.config import settings
from chronocanvas.services.storage import get_storage_backend, upload_artifact

logger = logging.getLogger(__name__)


async def storyboard_export_node(state: StoryState) -> StoryState:
    request_id = state.get("request_id", "unknown")
    characters = state.get("characters", [])
    scenes = state.get("scenes", [])
    panels = state.get("panels", [])
    logger.info("Storyboard export: assembling [request_id=%s]", request_id)

    trace = list(state.get("agent_trace", []))

    export_dir = Path(settings.output_dir) / request_id / "export"
    export_dir.mkdir(parents=True, exist_ok=True)

    grounding_sources = state.get("grounding_sources", [])

    storyboard = {
        "request_id": request_id,
        "characters": characters,
        "scenes": scenes,
        "grounding_sources": grounding_sources,
        "panels": [
            {
                "scene_index": p.get("scene_index"),
                "description": p.get("description"),
                "characters": p.get("characters", []),
                "mood": p.get("mood"),
                "setting": p.get("setting"),
                "image_prompt": p.get("image_prompt"),
                "image_path": p.get("image_path"),
                "status": p.get("status"),
                "coherence_score": p.get("coherence_score"),
                "coherence_issues": p.get("coherence_issues", []),
                "coherence_suggestion": p.get("coherence_suggestion", ""),
                "narration_text": p.get("narration_text", ""),
                "narration_audio_path": p.get("narration_audio_path", ""),
            }
            for p in panels
        ],
        "total_scenes": len(panels),
        "completed_scenes": sum(1 for p in panels if p.get("status") == "completed"),
    }

    metadata_path = export_dir / "storyboard.json"
    metadata_path.write_text(json.dumps(storyboard, indent=2))

    # Upload to GCS if in cloud mode
    backend = get_storage_backend()
    uploaded_count = 0
    skipped_count = 0
    failed_count = 0
    if backend.is_cloud():
        # Upload storyboard.json
        try:
            await upload_artifact(str(metadata_path), request_id)
        except Exception as e:
            logger.error("GCS upload failed for storyboard.json [request_id=%s]: %s", request_id, e)

        # Upload all panel images and audio
        for p in panels:
            img_path = p.get("image_path")
            if img_path:
                if Path(img_path).exists():
                    try:
                        await upload_artifact(img_path, request_id)
                        uploaded_count += 1
                    except Exception as e:
                        failed_count += 1
                        logger.error("GCS upload failed for image %s: %s", img_path, e)
                else:
                    skipped_count += 1
                    logger.warning("Image file missing, skipping GCS upload: %s", img_path)

            audio_path = p.get("narration_audio_path")
            if audio_path:
                if Path(audio_path).exists():
                    try:
                        await upload_artifact(audio_path, request_id)
                    except Exception as e:
                        logger.error("GCS upload failed for audio %s: %s", audio_path, e)
                else:
                    logger.warning("Audio file missing, skipping GCS upload: %s", audio_path)

        # Upload video if it exists
        video_path = export_dir / "storyboard.mp4"
        if video_path.exists():
            try:
                await upload_artifact(str(video_path), request_id)
            except Exception as e:
                logger.error("GCS upload failed for video: %s", e)

        logger.info(
            "GCS upload complete [request_id=%s]: %d uploaded, %d skipped (missing), %d failed",
            request_id, uploaded_count, skipped_count, failed_count,
        )

    trace.append({
        "agent": "storyboard_export",
        "timestamp": time.time(),
        "export_path": str(export_dir),
        "total_panels": len(panels),
        "gcs_uploaded": uploaded_count if backend.is_cloud() else None,
    })

    return {
        "current_agent": "storyboard_export",
        "agent_trace": trace,
    }
