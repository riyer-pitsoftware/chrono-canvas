import logging
import uuid

import chronocanvas.agents.graph as _graph_module
from chronocanvas.agents.invariants import InvariantViolationError, validate_initial_state
from chronocanvas.agents.state import AgentState, FaceState, ValidationState
from chronocanvas.db.engine import async_session as _default_session_factory
from chronocanvas.db.models.request import RequestStatus
from chronocanvas.db.repositories.images import ImageRepository
from chronocanvas.db.repositories.requests import RequestRepository
from chronocanvas.db.repositories.validation_rules import (
    AdminSettingRepository,
    ValidationRuleRepository,
)
from chronocanvas.runtime_config import RuntimeConfig
from chronocanvas.services.image_recorder import ImageAttemptRecorder
from chronocanvas.services.progress import ProgressPublisher
from chronocanvas.services.retry import RetryCoordinator
from chronocanvas.services.runner import GenerationRunner
from chronocanvas.services.state_projector import RequestStateProjector

logger = logging.getLogger(__name__)

VALID_RETRY_STEPS = frozenset([
    # Portrait pipeline
    "orchestrator", "extraction", "research", "prompt_generation",
    "image_generation", "validation", "facial_compositing", "export",
    # Story pipeline
    "story_orchestrator", "image_to_story", "reference_image_analysis",
    "character_extraction", "scene_decomposition", "scene_prompt_generation",
    "scene_image_generation", "storyboard_coherence", "narration_script",
    "narration_audio", "video_assembly", "storyboard_export",
])

# Steps that require clearing existing image records before retrying
_STEPS_CLEAR_IMAGES = frozenset([
    "orchestrator", "extraction", "research", "prompt_generation", "image_generation",
])

_STATUS_MAP: dict[str, RequestStatus] = {
    "orchestrator": RequestStatus.PENDING,
    "extraction": RequestStatus.EXTRACTING,
    "research": RequestStatus.RESEARCHING,
    "prompt_generation": RequestStatus.GENERATING_PROMPT,
    "image_generation": RequestStatus.GENERATING_IMAGE,
    "validation": RequestStatus.VALIDATING,
    "facial_compositing": RequestStatus.SWAPPING_FACE,
    "export": RequestStatus.COMPLETED,
}


def _make_runner(repo: RequestRepository, session: object, graph: object) -> GenerationRunner:
    return GenerationRunner(
        repo=repo,
        session=session,
        publisher=ProgressPublisher(),
        projector=RequestStateProjector(),
        recorder=ImageAttemptRecorder(),
        graph=graph,
    )


async def run_generation_pipeline(
    request_id: str,
    input_text: str,
    *,
    source_face_path: str | None = None,
    config_payload: dict | None = None,
    session_factory=None,
    graph=None,
) -> None:
    _sf = session_factory if session_factory is not None else _default_session_factory
    _graph = graph if graph is not None else _graph_module.agent_graph
    channel = f"generation:{request_id}"
    publisher = ProgressPublisher()

    async with _sf() as session:
        repo = RequestRepository(session)
        try:
            await repo.update(request_id, status=RequestStatus.EXTRACTING)
            await session.commit()
            await publisher.publish(channel, {
                "status": "extracting",
                "agent": "extraction",
                "message": "Extracting figure details...",
            })

            rule_repo = ValidationRuleRepository(session)
            setting_repo = AdminSettingRepository(session)
            validation_weights = await rule_repo.get_weights()
            validation_threshold = await setting_repo.get_pass_threshold()

            rc = RuntimeConfig.from_request_payload(config_payload)

            initial_state: AgentState = {
                "request_id": request_id,
                "input_text": input_text,
                "agent_trace": [],
                "llm_calls": [],
                "retry_count": 0,
                "should_regenerate": False,
                "error": None,
                "runtime_config": rc,
                "validation": ValidationState(
                    rule_weights=validation_weights,
                    pass_threshold=validation_threshold,
                ),
            }
            if source_face_path:
                initial_state["face"] = FaceState(source_face_path=source_face_path)

            try:
                validate_initial_state(initial_state)
            except InvariantViolationError:
                logger.warning("Initial state invariant violation for %s", request_id)

            config = {"configurable": {"thread_id": request_id}}
            runner = _make_runner(repo, session, _graph)
            await runner.run(request_id, initial_state, config, channel)

        except Exception as e:
            logger.exception("Generation pipeline failed for %s", request_id)
            await repo.update(request_id, status=RequestStatus.FAILED, error_message=str(e))
            await session.commit()
            await publisher.publish(channel, {"status": "failed", "message": str(e)})


async def retry_generation_pipeline(
    request_id: str,
    from_step: str,
    *,
    session_factory=None,
    graph=None,
) -> None:
    _sf = session_factory if session_factory is not None else _default_session_factory
    _graph = graph if graph is not None else _graph_module.agent_graph
    channel = f"generation:{request_id}"
    config = {"configurable": {"thread_id": request_id}}
    publisher = ProgressPublisher()
    coordinator = RetryCoordinator()

    async with _sf() as session:
        repo = RequestRepository(session)
        try:
            request = await repo.get(uuid.UUID(request_id))
            if not request:
                raise ValueError(f"Request {request_id} not found")

            retry_status = _STATUS_MAP.get(from_step, RequestStatus.PENDING)
            await repo.update(
                request_id,
                status=retry_status,
                error_message=None,
                current_agent=from_step,
            )

            if from_step in _STEPS_CLEAR_IMAGES:
                image_repo = ImageRepository(session)
                for img in await image_repo.list_by_request(uuid.UUID(request_id)):
                    await session.delete(img)

            await session.commit()
            await publisher.publish(channel, {
                "status": retry_status,
                "agent": from_step,
                "message": f"Retrying from {from_step}...",
            })

            runner = _make_runner(repo, session, _graph)

            if from_step == "orchestrator":
                initial_state: AgentState = {
                    "request_id": request_id,
                    "input_text": request.input_text,
                    "agent_trace": [],
                    "llm_calls": [],
                    "retry_count": 0,
                    "should_regenerate": False,
                    "error": None,
                }
                await runner.run(request_id, initial_state, config, channel)
            else:
                predecessor = coordinator.predecessor_for(from_step)
                current_snapshot = await _graph.aget_state(config)
                if current_snapshot.values:
                    update_values: AgentState = {
                        "error": None,
                        "should_regenerate": False,
                        "retry_count": 0,
                    }  # type: ignore[typeddict-item]
                else:
                    logger.info(
                        "Checkpoint missing for %s (server may have restarted); "
                        "reconstructing state from DB (from_step=%s)",
                        request_id, from_step,
                    )
                    update_values = coordinator.rebuild_state_from_db(request, from_step)

                await _graph.aupdate_state(config, update_values, as_node=predecessor)
                await runner.run(request_id, None, config, channel)

        except Exception as e:
            logger.exception("Retry pipeline failed for %s (from_step=%s)", request_id, from_step)
            await repo.update(request_id, status=RequestStatus.FAILED, error_message=str(e))
            await session.commit()
            await publisher.publish(channel, {"status": "failed", "message": str(e)})
