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
    if backend.is_cloud():
        try:
            # Upload storyboard.json
            await upload_artifact(str(metadata_path), request_id)

            # Upload all panel images
            for p in panels:
                img_path = p.get("image_path")
                if img_path and Path(img_path).exists():
                    await upload_artifact(img_path, request_id)
                    uploaded_count += 1

                # Upload audio files
                audio_path = p.get("narration_audio_path")
                if audio_path and Path(audio_path).exists():
                    await upload_artifact(audio_path, request_id)

            # Upload video if it exists
            video_path = export_dir / "storyboard.mp4"
            if video_path.exists():
                await upload_artifact(str(video_path), request_id)

            logger.info(
                "Uploaded %d artifacts to GCS [request_id=%s]",
                uploaded_count, request_id,
            )
        except Exception as e:
            logger.warning(
                "GCS upload failed (exports may be inaccessible) [request_id=%s]: %s",
                request_id, e,
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
