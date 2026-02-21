import logging
import time
from pathlib import Path

from chronocanvas.agents.state import AgentState
from chronocanvas.config import settings
from chronocanvas.imaging.comfyui_client import ComfyUIClient
from chronocanvas.imaging.mock_generator import MockImageGenerator
from chronocanvas.imaging.sd_client import StableDiffusionClient
from chronocanvas.redis_client import publish_progress

logger = logging.getLogger(__name__)


def _get_generator():
    if settings.image_provider == "stable_diffusion":
        return StableDiffusionClient()
    elif settings.image_provider == "comfyui":
        return ComfyUIClient()
    return MockImageGenerator()


async def image_generation_node(state: AgentState) -> AgentState:
    request_id = state.get("request_id", "unknown")
    logger.info(
        "Image generation agent: generating image for %s [request_id=%s]",
        state.get("figure_name", ""),
        request_id,
    )

    generator = _get_generator()
    output_dir = Path(settings.output_dir) / request_id
    channel = f"generation:{request_id}"

    async def on_progress(step: int, total: int) -> None:
        await publish_progress(channel, {
            "type": "image_progress",
            "agent": "image_generation",
            "step": step,
            "total": total,
        })

    try:
        result = await generator.generate(
            prompt=state.get("image_prompt", "historical portrait"),
            output_dir=output_dir,
            width=768,
            height=768,
            negative_prompt=state.get("negative_prompt", ""),
            on_progress=on_progress,
        )

        trace = state.get("agent_trace", [])
        trace.append({
            "agent": "image_generation",
            "timestamp": time.time(),
            "provider": result.provider,
            "file_path": result.file_path,
        })

        return {
            **state,
            "current_agent": "image_generation",
            "image_path": result.file_path,
            "image_provider": result.provider,
            "generation_params": result.generation_params,
            "agent_trace": trace,
        }
    except Exception as e:
        logger.error("Image generation failed [request_id=%s]: %s", request_id, e)
        trace = state.get("agent_trace", [])
        trace.append({
            "agent": "image_generation",
            "timestamp": time.time(),
            "error": str(e),
        })
        return {
            **state,
            "current_agent": "image_generation",
            "error": f"Image generation failed: {e}",
            "agent_trace": trace,
        }
