import json
import logging
import shutil
import time
from pathlib import Path

from chronocanvas.agents.state import AgentState
from chronocanvas.config import settings

logger = logging.getLogger(__name__)


async def export_node(state: AgentState) -> AgentState:
    logger.info(f"Export agent: exporting results for {state.get('figure_name', '')}")

    request_id = state.get("request_id", "unknown")
    export_dir = Path(settings.output_dir) / request_id / "export"
    export_dir.mkdir(parents=True, exist_ok=True)

    # Copy generated image to export directory
    image_path = state.get("image_path", "")
    export_image_path = ""
    if image_path and Path(image_path).exists():
        dest = export_dir / Path(image_path).name
        shutil.copy2(image_path, dest)
        export_image_path = str(dest)

    # Copy swapped image if available
    export_swapped_path = ""
    swapped_image_path = state.get("swapped_image_path", "")
    if swapped_image_path and Path(swapped_image_path).exists():
        dest = export_dir / Path(swapped_image_path).name
        shutil.copy2(swapped_image_path, dest)
        export_swapped_path = str(dest)

    # Write metadata
    original_image_path = state.get("original_image_path", "")
    metadata = {
        "figure_name": state.get("figure_name", ""),
        "time_period": state.get("time_period", ""),
        "region": state.get("region", ""),
        "occupation": state.get("occupation", ""),
        "historical_context": state.get("historical_context", ""),
        "image_prompt": state.get("image_prompt", ""),
        "validation_score": state.get("validation_score", 0),
        "image_provider": state.get("image_provider", ""),
        "image_path": export_image_path,
        "swapped_image_path": export_swapped_path,
        "original_image_path": original_image_path,
    }

    metadata_path = export_dir / "metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2))

    trace = state.get("agent_trace", [])
    trace.append({
        "agent": "export",
        "timestamp": time.time(),
        "export_path": str(export_dir),
    })

    return {
        **state,
        "current_agent": "export",
        "export_path": str(export_dir),
        "export_format": "json+png",
        "agent_trace": trace,
    }
