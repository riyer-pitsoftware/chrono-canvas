import logging
import time
from pathlib import Path

from chronocanvas.agents.story.state import StoryState
from chronocanvas.config import settings
from chronocanvas.redis_client import publish_progress
from chronocanvas.service_registry import get_registry

logger = logging.getLogger(__name__)


def _get_generator():
    factory = get_registry().image_generator_factory
    if factory is not None:
        return factory()
    from chronocanvas.imaging.mock_generator import MockImageGenerator
    return MockImageGenerator()


async def scene_image_generation_node(state: StoryState) -> StoryState:
    request_id = state.get("request_id", "unknown")
    panels = list(state.get("panels", []))
    total_scenes = len(panels)
    logger.info(
        "Scene image generation: generating %d images [request_id=%s]",
        total_scenes, request_id,
    )

    trace = list(state.get("agent_trace", []))
    channel = f"generation:{request_id}"
    generator = _get_generator()
    completed_scenes = 0

    for i, panel in enumerate(panels):
        if panel.get("status") == "failed":
            # Skip panels that already failed during prompt generation
            continue

        if not panel.get("image_prompt"):
            panel["status"] = "failed"
            panel["error"] = "No image prompt available"
            continue

        panel["status"] = "generating"
        scene_index = panel.get("scene_index", i)
        output_dir = Path(settings.output_dir) / request_id / f"scene_{scene_index}"

        async def on_progress(step: int, total: int) -> None:
            await publish_progress(channel, {
                "type": "image_progress",
                "agent": "scene_image_generation",
                "step": step,
                "total": total,
                "scene_index": scene_index,
            })

        try:
            result = await generator.generate(
                prompt=panel["image_prompt"],
                output_dir=output_dir,
                width=768,
                height=768,
                negative_prompt=panel.get("negative_prompt", ""),
                on_progress=on_progress,
            )

            panel["image_path"] = result.file_path
            panel["status"] = "completed"
            completed_scenes += 1

            # Publish per-scene completion for incremental storyboard display
            await publish_progress(channel, {
                "type": "scene_image_complete",
                "scene_index": scene_index,
                "total_scenes": total_scenes,
                "image_path": result.file_path,
            })

        except Exception as e:
            logger.warning(
                "Image generation failed for scene %d [request_id=%s]: %s",
                scene_index, request_id, e,
            )
            panel["status"] = "failed"
            panel["error"] = str(e)

    trace.append({
        "agent": "scene_image_generation",
        "timestamp": time.time(),
        "total_scenes": total_scenes,
        "completed_scenes": completed_scenes,
        "failed_scenes": total_scenes - completed_scenes,
    })

    return {
        "current_agent": "scene_image_generation",
        "panels": panels,
        "completed_scenes": completed_scenes,
        "agent_trace": trace,
    }
