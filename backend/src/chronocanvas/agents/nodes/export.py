import json
import logging
import shutil
import time
from pathlib import Path

from chronocanvas.agents.state import AgentState, ExportState
from chronocanvas.config import settings

logger = logging.getLogger(__name__)


async def export_node(state: AgentState) -> AgentState:
    ext = state.get("extraction", {})
    res = state.get("research", {})
    prompt_state = state.get("prompt", {})
    img = state.get("image", {})
    val = state.get("validation", {})
    comp = state.get("compositing", {})
    figure_name = ext.get("figure_name", "")
    logger.info(f"Export agent: exporting results for {figure_name}")

    request_id = state.get("request_id", "unknown")
    export_dir = Path(settings.output_dir) / request_id / "export"
    export_dir.mkdir(parents=True, exist_ok=True)

    # Copy generated image to export directory
    image_path = img.get("image_path", "")
    export_image_path = ""
    if image_path and Path(image_path).exists():
        dest = export_dir / Path(image_path).name
        shutil.copy2(image_path, dest)
        export_image_path = str(dest)

    # Copy swapped image if available
    export_swapped_path = ""
    swapped_image_path = comp.get("swapped_image_path", "")
    if swapped_image_path and Path(swapped_image_path).exists():
        dest = export_dir / Path(swapped_image_path).name
        shutil.copy2(swapped_image_path, dest)
        export_swapped_path = str(dest)

    # Write metadata
    original_image_path = comp.get("original_image_path", "")
    metadata = {
        "figure_name": figure_name,
        "time_period": ext.get("time_period", ""),
        "region": ext.get("region", ""),
        "occupation": ext.get("occupation", ""),
        "historical_context": res.get("historical_context", ""),
        "image_prompt": prompt_state.get("image_prompt", ""),
        "validation_score": val.get("validation_score", 0),
        "image_provider": img.get("image_provider", ""),
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
        "current_agent": "export",
        "export": ExportState(
            export_path=str(export_dir),
            export_format="json+png",
        ),
        "agent_trace": trace,
    }
