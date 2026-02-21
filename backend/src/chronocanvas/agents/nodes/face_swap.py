import logging
import shutil
import time
from pathlib import Path

from chronocanvas.agents.state import AgentState
from chronocanvas.config import settings
from chronocanvas.imaging.facefusion_client import FaceFusionClient
from chronocanvas.imaging.mock_face_swap import MockFaceSwapClient

logger = logging.getLogger(__name__)


def _get_face_swap_client():
    if settings.image_provider == "facefusion":
        return FaceFusionClient()
    return MockFaceSwapClient()


async def face_swap_node(state: AgentState) -> AgentState:
    source_face_path = state.get("source_face_path", "")
    trace = list(state.get("agent_trace", []))

    if not source_face_path:
        trace.append({
            "agent": "face_swap",
            "timestamp": time.time(),
            "skipped": True,
        })
        return {
            **state,
            "current_agent": "face_swap",
            "agent_trace": trace,
        }

    logger.info(f"Face swap agent: swapping face for {state.get('figure_name', '')}")
    image_path = state.get("image_path", "")

    if not image_path or not Path(image_path).exists():
        logger.warning("Face swap: no generated image found, skipping")
        trace.append({
            "agent": "face_swap",
            "timestamp": time.time(),
            "skipped": True,
            "reason": "no_image",
        })
        return {
            **state,
            "current_agent": "face_swap",
            "agent_trace": trace,
        }

    try:
        # Save original image before overwriting
        original_path = Path(image_path)
        original_copy = original_path.parent / f"original_{original_path.name}"
        shutil.copy2(image_path, original_copy)

        # Run face swap (mock when IMAGE_PROVIDER != "facefusion")
        client = _get_face_swap_client()
        request_id = state.get("request_id", "unknown")
        output_dir = Path(settings.output_dir) / request_id

        result = await client.generate(
            prompt="",
            output_dir=output_dir,
            source_image=source_face_path,
            target_image=image_path,
        )

        trace.append({
            "agent": "face_swap",
            "timestamp": time.time(),
            "skipped": False,
            "source_face": source_face_path,
            "swapped_path": result.file_path,
            "original_path": str(original_copy),
        })

        return {
            **state,
            "current_agent": "face_swap",
            "swapped_image_path": result.file_path,
            "original_image_path": str(original_copy),
            "agent_trace": trace,
        }

    except Exception as e:
        logger.exception("Face swap failed, continuing with original image")
        trace.append({
            "agent": "face_swap",
            "timestamp": time.time(),
            "skipped": False,
            "error": True,
            "error_message": str(e),
        })
        return {
            **state,
            "current_agent": "face_swap",
            "agent_trace": trace,
        }
