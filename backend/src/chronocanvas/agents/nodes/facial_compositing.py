import logging
import shutil
import time
from pathlib import Path

from chronocanvas.agents.state import AgentState
from chronocanvas.config import settings
from chronocanvas.imaging.facefusion_client import FaceFusionClient
from chronocanvas.imaging.mock_face_swap import MockFaceSwapClient

logger = logging.getLogger(__name__)


def _get_compositing_client():
    if settings.image_provider == "facefusion":
        return FaceFusionClient()
    return MockFaceSwapClient()


async def facial_compositing_node(state: AgentState) -> AgentState:
    source_face_path = state.get("source_face_path", "")
    request_id = state.get("request_id", "unknown")
    trace = list(state.get("agent_trace", []))

    if not source_face_path:
        trace.append({
            "agent": "facial_compositing",
            "timestamp": time.time(),
            "skipped": True,
        })
        return {
            **state,
            "current_agent": "facial_compositing",
            "agent_trace": trace,
        }

    logger.info(
        "Facial compositing agent: compositing face for %s [request_id=%s]",
        state.get("figure_name", ""),
        request_id,
    )
    image_path = state.get("image_path", "")

    if not image_path or not Path(image_path).exists():
        logger.warning("Facial compositing: no generated image found, skipping [request_id=%s]", request_id)
        trace.append({
            "agent": "facial_compositing",
            "timestamp": time.time(),
            "skipped": True,
            "reason": "no_image",
        })
        return {
            **state,
            "current_agent": "facial_compositing",
            "agent_trace": trace,
        }

    try:
        # Save original image before overwriting
        original_path = Path(image_path)
        original_copy = original_path.parent / f"original_{original_path.name}"
        shutil.copy2(image_path, original_copy)

        # Run facial compositing (mock when IMAGE_PROVIDER != "facefusion")
        client = _get_compositing_client()
        output_dir = Path(settings.output_dir) / request_id

        result = await client.generate(
            prompt="",
            output_dir=output_dir,
            source_image=source_face_path,
            target_image=image_path,
        )

        trace.append({
            "agent": "facial_compositing",
            "timestamp": time.time(),
            "skipped": False,
            "source_face": source_face_path,
            "swapped_path": result.file_path,
            "original_path": str(original_copy),
        })

        return {
            **state,
            "current_agent": "facial_compositing",
            "swapped_image_path": result.file_path,
            "original_image_path": str(original_copy),
            "agent_trace": trace,
        }

    except Exception as e:
        logger.exception("Facial compositing failed, continuing with original image [request_id=%s]: %s", request_id, e)
        trace.append({
            "agent": "facial_compositing",
            "timestamp": time.time(),
            "skipped": False,
            "error": True,
            "error_message": str(e),
        })
        return {
            **state,
            "current_agent": "facial_compositing",
            "agent_trace": trace,
        }
