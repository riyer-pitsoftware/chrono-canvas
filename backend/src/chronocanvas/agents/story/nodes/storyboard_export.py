import json
import logging
import time
from pathlib import Path

from chronocanvas.agents.story.state import StoryState
from chronocanvas.config import settings

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

    storyboard = {
        "request_id": request_id,
        "characters": characters,
        "scenes": scenes,
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
            }
            for p in panels
        ],
        "total_scenes": len(panels),
        "completed_scenes": sum(1 for p in panels if p.get("status") == "completed"),
    }

    metadata_path = export_dir / "storyboard.json"
    metadata_path.write_text(json.dumps(storyboard, indent=2))

    trace.append({
        "agent": "storyboard_export",
        "timestamp": time.time(),
        "export_path": str(export_dir),
        "total_panels": len(panels),
    })

    return {
        "current_agent": "storyboard_export",
        "agent_trace": trace,
    }
