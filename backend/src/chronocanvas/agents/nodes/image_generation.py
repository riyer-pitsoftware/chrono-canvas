import logging
import time
from pathlib import Path

from chronocanvas.agents.state import AgentState, ImageState
from chronocanvas.config import settings
from chronocanvas.redis_client import publish_progress
from chronocanvas.service_registry import get_registry
from chronocanvas.services.progress import ProgressPublisher

logger = logging.getLogger(__name__)


def _get_generator(runtime_config=None):
    factory = get_registry().image_generator_factory
    if factory is not None:
        return factory(runtime_config=runtime_config)
    if settings.hackathon_mode:
        raise RuntimeError(
            "HACKATHON MODE: Image generation falling back"
            " to mock — service registry not initialized"
        )
    # Fallback before registry init (tests, CLI)
    from chronocanvas.imaging.mock_generator import MockImageGenerator

    return MockImageGenerator()


async def image_generation_node(state: AgentState) -> AgentState:
    request_id = state.get("request_id", "unknown")
    ext = state.get("extraction", {})
    prompt_state = state.get("prompt", {})
    rc = state.get("runtime_config")
    logger.info(
        "Image generation agent: generating image for %s [request_id=%s]",
        ext.get("figure_name", ""),
        request_id,
    )

    generator = _get_generator(runtime_config=rc)
    output_dir = Path(settings.output_dir) / request_id
    channel = f"generation:{request_id}"

    # Use runtime config for dimensions if provided
    width = (rc.portrait_width if rc and rc.portrait_width else None) or settings.portrait_width
    height = (rc.portrait_height if rc and rc.portrait_height else None) or settings.portrait_height

    async def on_progress(step: int, total: int) -> None:
        await publish_progress(
            channel,
            {
                "type": "image_progress",
                "agent": "image_generation",
                "step": step,
                "total": total,
            },
        )

    try:
        result = await generator.generate(
            prompt=prompt_state.get("image_prompt", "historical portrait"),
            output_dir=output_dir,
            width=width,
            height=height,
            negative_prompt=prompt_state.get("negative_prompt", ""),
            on_progress=on_progress,
        )

        # Emit artifact_ready for portrait image
        progress = ProgressPublisher()
        await progress.publish_artifact(
            channel,
            artifact_type="image",
            scene_index=None,
            total=1,
            completed=1,
            url=f"/output/{request_id}/{Path(result.file_path).name}",
            mime_type="image/png",
        )

        trace = state.get("agent_trace", [])
        trace.append(
            {
                "agent": "image_generation",
                "timestamp": time.time(),
                "provider": result.provider,
                "file_path": result.file_path,
            }
        )

        return {
            "current_agent": "image_generation",
            "image": ImageState(
                image_path=result.file_path,
                image_provider=result.provider,
                generation_params=result.generation_params,
            ),
            "agent_trace": trace,
        }
    except Exception as e:
        logger.error("Image generation failed [request_id=%s]: %s", request_id, e)
        trace = state.get("agent_trace", [])
        trace.append(
            {
                "agent": "image_generation",
                "timestamp": time.time(),
                "error": str(e),
            }
        )
        return {
            "current_agent": "image_generation",
            "error": f"Image generation failed: {e}",
            "agent_trace": trace,
        }
