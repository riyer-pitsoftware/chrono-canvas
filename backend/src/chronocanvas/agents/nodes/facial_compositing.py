import logging
import shutil
import time
from pathlib import Path

from chronocanvas.agents.state import AgentState, CompositingState
from chronocanvas.config import settings
from chronocanvas.service_registry import get_registry

logger = logging.getLogger(__name__)


def _get_compositing_client():
    factory = get_registry().compositing_client_factory
    if factory is not None:
        return factory()
    # Fallback before registry init (tests, CLI)
    from chronocanvas.imaging.mock_face_swap import MockFaceSwapClient

    return MockFaceSwapClient()


async def facial_compositing_node(state: AgentState) -> AgentState:
    face = state.get("face", {})
    img = state.get("image", {})
    source_face_path = face.get("source_face_path", "")
    request_id = state.get("request_id", "unknown")
    trace = list(state.get("agent_trace", []))

    if not source_face_path:
        trace.append({
            "agent": "facial_compositing",
            "timestamp": time.time(),
            "skipped": True,
        })
        return {
            "current_agent": "facial_compositing",
            "agent_trace": trace,
        }

    ext = state.get("extraction", {})
    logger.info(
        "Facial compositing agent: compositing face for %s [request_id=%s]",
        ext.get("figure_name", ""),
        request_id,
    )
    image_path = img.get("image_path", "")

    if not image_path or not Path(image_path).exists():
        logger.warning(
            "Facial compositing: no generated image found, skipping [request_id=%s]",
            request_id,
        )
        trace.append({
            "agent": "facial_compositing",
            "timestamp": time.time(),
            "skipped": True,
            "reason": "no_image",
        })
        return {
            "current_agent": "facial_compositing",
            "agent_trace": trace,
        }

    try:
        # Save original image before overwriting
        original_path = Path(image_path)
        original_copy = original_path.parent / f"original_{original_path.name}"
        shutil.copy2(image_path, original_copy)

        # Run facial compositing (mock when FACEFUSION_ENABLED is false)
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
            "current_agent": "facial_compositing",
            "compositing": CompositingState(
                swapped_image_path=result.file_path,
                original_image_path=str(original_copy),
            ),
            "agent_trace": trace,
        }

    except Exception as e:
        logger.exception(
            "Facial compositing failed, continuing with original image [request_id=%s]: %s",
            request_id, e,
        )
        trace.append({
            "agent": "facial_compositing",
            "timestamp": time.time(),
            "skipped": False,
            "error": True,
            "error_message": str(e),
        })
        return {
            "current_agent": "facial_compositing",
            "agent_trace": trace,
        }
