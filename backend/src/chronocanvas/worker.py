from arq.connections import RedisSettings

from chronocanvas.agents.checkpointer import close_checkpointer, init_checkpointer
from chronocanvas.agents.graph import recompile_graph
from chronocanvas.config import settings
from chronocanvas.services.generation import retry_generation_pipeline, run_generation_pipeline


async def startup(ctx: dict) -> None:
    await init_checkpointer()
    recompile_graph()


async def shutdown(ctx: dict) -> None:
    await close_checkpointer()


async def run_generation_pipeline_task(
    ctx: dict, request_id: str, input_text: str, source_face_path: str | None = None
) -> None:
    await run_generation_pipeline(request_id, input_text, source_face_path=source_face_path)


async def retry_generation_pipeline_task(ctx: dict, request_id: str, from_step: str) -> None:
    await retry_generation_pipeline(request_id, from_step)


class WorkerSettings:
    functions = [run_generation_pipeline_task, retry_generation_pipeline_task]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_jobs = 5
    job_timeout = 600  # 10 min per job
    keep_result = 600  # keep result in Redis for 10 min
