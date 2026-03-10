from arq.connections import RedisSettings

from chronocanvas.agents.checkpointer import close_checkpointer, init_checkpointer
from chronocanvas.agents.graph import recompile_graph
from chronocanvas.config import settings
from chronocanvas.service_registry import init_registry
from chronocanvas.services.generation import retry_generation_pipeline, run_generation_pipeline
from chronocanvas.services.scene_editor import edit_scene
from chronocanvas.services.story_generation import run_story_pipeline


async def startup(ctx: dict) -> None:
    init_registry()
    await init_checkpointer()
    recompile_graph()


async def shutdown(ctx: dict) -> None:
    await close_checkpointer()


async def run_generation_pipeline_task(
    ctx: dict,
    request_id: str,
    input_text: str,
    source_face_path: str | None = None,
    config_payload: dict | None = None,
) -> None:
    await run_generation_pipeline(
        request_id,
        input_text,
        source_face_path=source_face_path,
        config_payload=config_payload,
    )


async def retry_generation_pipeline_task(ctx: dict, request_id: str, from_step: str) -> None:
    await retry_generation_pipeline(request_id, from_step)


async def run_story_pipeline_task(
    ctx: dict,
    request_id: str,
    input_text: str,
    ref_image_path: str | None = None,
    ref_image_mime: str | None = None,
    ref_images: list[dict] | None = None,
    config_payload: dict | None = None,
) -> None:
    await run_story_pipeline(
        request_id,
        input_text,
        ref_image_path=ref_image_path,
        ref_image_mime=ref_image_mime,
        ref_images=ref_images,
        config_payload=config_payload,
    )


async def edit_scene_task(
    ctx: dict,
    request_id: str,
    scene_index: int,
    instruction: str,
) -> dict:
    # Look up current image path and description from the storyboard data
    from chronocanvas.db.engine import async_session
    from chronocanvas.db.repositories.requests import RequestRepository

    async with async_session() as session:
        repo = RequestRepository(session)
        gen_request = await repo.get(request_id)

    if not gen_request or not gen_request.storyboard_data:
        raise ValueError(f"No storyboard data for request {request_id}")

    panels = gen_request.storyboard_data.get("panels", [])
    panel = next((p for p in panels if p.get("scene_index") == scene_index), None)
    if not panel:
        raise ValueError(f"No panel found for scene_index {scene_index}")

    return await edit_scene(
        request_id=request_id,
        scene_index=scene_index,
        instruction=instruction,
        current_image_path=panel.get("image_path", ""),
        current_description=panel.get("description", ""),
    )


class WorkerSettings:
    functions = [
        run_generation_pipeline_task,
        retry_generation_pipeline_task,
        run_story_pipeline_task,
        edit_scene_task,
    ]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_jobs = 5
    job_timeout = 1200  # 20 min per job (story mode generates multiple images)
    keep_result = 600  # keep result in Redis for 10 min
