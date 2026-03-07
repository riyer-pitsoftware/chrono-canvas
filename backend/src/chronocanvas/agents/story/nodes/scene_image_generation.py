import asyncio
import logging
import time
from pathlib import Path

from chronocanvas.agents.story.state import StoryState, get_runtime_config
from chronocanvas.config import settings
from chronocanvas.redis_client import publish_progress
from chronocanvas.service_registry import get_registry
from chronocanvas.services.progress import ProgressPublisher

logger = logging.getLogger(__name__)


def _get_generator(runtime_config=None):
    factory = get_registry().image_generator_factory
    if factory is not None:
        gen = factory(runtime_config=runtime_config)
        logger.info("Image generator selected: %s (runtime_config.image_provider=%s)",
                     gen.name, getattr(runtime_config, 'image_provider', None))
        return gen
    from chronocanvas.imaging.mock_generator import MockImageGenerator
    logger.warning("No image_generator_factory registered, using MockImageGenerator")
    return MockImageGenerator()


async def _generate_scene(
    panel: dict,
    index: int,
    generator,
    request_id: str,
    total_scenes: int,
    channel: str,
    completed_counter: list[int] | None = None,
) -> bool:
    """Generate image for a single scene panel. Returns True on success."""
    if panel.get("status") == "failed":
        return False
    if not panel.get("image_prompt"):
        panel["status"] = "failed"
        panel["error"] = "No image prompt available"
        return False

    panel["status"] = "generating"
    scene_index = panel.get("scene_index", index)
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
        panel["provider"] = result.provider
        panel["width"] = result.width
        panel["height"] = result.height
        panel["status"] = "completed"

        await publish_progress(channel, {
            "type": "scene_image_complete",
            "scene_index": scene_index,
            "total_scenes": total_scenes,
            "image_path": result.file_path,
        })

        # Emit uniform artifact_ready event
        if completed_counter is not None:
            completed_counter[0] += 1
            progress = ProgressPublisher()
            await progress.publish_artifact(
                channel,
                artifact_type="image",
                scene_index=scene_index,
                total=total_scenes,
                completed=completed_counter[0],
                url=f"/output/{request_id}/scene_{scene_index}/{Path(result.file_path).name}",
                mime_type="image/png",
            )

        return True

    except Exception as e:
        logger.warning(
            "Image generation failed for scene %d [request_id=%s]: %s",
            scene_index, request_id, e,
        )
        panel["status"] = "failed"
        panel["error"] = str(e)
        return False


async def scene_image_generation_node(state: StoryState) -> StoryState:
    request_id = state.get("request_id", "unknown")
    panels = list(state.get("panels", []))
    total_scenes = len(panels)
    logger.info(
        "Scene image generation: generating %d images in parallel [request_id=%s]",
        total_scenes, request_id,
    )

    rc = get_runtime_config(state)
    trace = list(state.get("agent_trace", []))
    channel = f"generation:{request_id}"
    generator = _get_generator(runtime_config=rc)

    # Generate all scene images concurrently
    completed_counter = [0]  # mutable counter (safe: asyncio is single-threaded)
    results = await asyncio.gather(*(
        _generate_scene(panel, i, generator, request_id, total_scenes, channel, completed_counter)
        for i, panel in enumerate(panels)
    ))

    completed_scenes = sum(1 for ok in results if ok)

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
