import logging
import uuid
from typing import Any

from chronocanvas.agents.graph import agent_graph
from chronocanvas.agents.state import AgentState
from chronocanvas.db.engine import async_session
from chronocanvas.db.models.image import GeneratedImage
from chronocanvas.db.models.request import RequestStatus
from chronocanvas.db.repositories.images import ImageRepository
from chronocanvas.db.repositories.requests import RequestRepository
from chronocanvas.redis_client import publish_progress

logger = logging.getLogger(__name__)

# Keys excluded from per-node state snapshots (noisy, large, or redundant)
_SNAPSHOT_EXCLUDE = frozenset({
    "llm_calls", "agent_trace", "request_id", "error",
    "should_regenerate", "retry_count",
    "source_face_path", "image_path", "export_path",
    "swapped_image_path", "original_image_path",
})

VALID_RETRY_STEPS = frozenset([
    "orchestrator", "extraction", "research", "prompt_generation",
    "image_generation", "validation", "facial_compositing", "export",
])

# Maps each step to the predecessor node to pass as `as_node` in aupdate_state,
# so that LangGraph sets `next` = [from_step] in the checkpoint.
_PREDECESSOR_NODE: dict[str, str] = {
    "extraction": "orchestrator",
    "research": "extraction",
    "prompt_generation": "research",
    "image_generation": "prompt_generation",
    "validation": "image_generation",
    "facial_compositing": "validation",
    "export": "facial_compositing",
}

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

# Retrying from these steps requires clearing existing generated image records
_STEPS_CLEAR_IMAGES = frozenset([
    "orchestrator", "extraction", "research", "prompt_generation", "image_generation",
])


async def _execute_graph(
    request_id: str,
    initial_state: AgentState | None,
    config: dict,
    channel: str,
    repo: RequestRepository,
    session: Any,
) -> None:
    """Stream the agent graph and persist incremental state to DB.

    Pass ``initial_state=None`` to resume from an existing LangGraph checkpoint.
    """
    final_state: dict[str, Any] | None = None
    # Accumulate every image generation attempt so all are persisted, including
    # intermediate attempts that were regenerated after a failed validation.
    image_attempts: list[dict[str, Any]] = []

    async for event in agent_graph.astream(initial_state, config=config):
        for node_name, node_state in event.items():
            current_agent = node_state.get("current_agent", node_name)
            status = _STATUS_MAP.get(current_agent, RequestStatus.PENDING)

            # Capture each image generation attempt as it happens
            if current_agent == "image_generation" and node_state.get("image_path"):
                image_attempts.append({
                    "image_path": node_state["image_path"],
                    "provider": node_state.get("image_provider", "mock"),
                    "prompt": node_state.get("image_prompt", ""),
                    "validation_score": None,
                })

            # Associate the validation score with the most recent attempt
            if current_agent == "validation" and image_attempts:
                image_attempts[-1]["validation_score"] = node_state.get("validation_score")

            update_kwargs: dict = {
                "status": status,
                "current_agent": current_agent,
                "agent_trace": node_state.get("agent_trace", []),
                "llm_calls": node_state.get("llm_calls", []),
            }
            if node_state.get("figure_name"):
                update_kwargs["extracted_data"] = {
                    "figure_name": node_state.get("figure_name"),
                    "time_period": node_state.get("time_period"),
                    "region": node_state.get("region"),
                    "occupation": node_state.get("occupation"),
                }
            if node_state.get("historical_context"):
                update_kwargs["research_data"] = {
                    "historical_context": node_state.get("historical_context"),
                    "clothing_details": node_state.get("clothing_details"),
                    "physical_description": node_state.get("physical_description"),
                }
            if node_state.get("image_prompt"):
                update_kwargs["generated_prompt"] = node_state["image_prompt"]

            # Attach a state snapshot to the trace entry for this agent
            snapshot = {k: v for k, v in node_state.items() if k not in _SNAPSHOT_EXCLUDE}
            trace = list(update_kwargs.get("agent_trace", []))
            for entry in reversed(trace):
                if entry.get("agent") == current_agent and "state_snapshot" not in entry:
                    entry["state_snapshot"] = snapshot
                    break
            update_kwargs["agent_trace"] = trace

            await repo.update(request_id, **update_kwargs)
            await session.commit()

            await publish_progress(channel, {
                "status": status,
                "agent": current_agent,
                "message": f"Running {current_agent}...",
            })

            final_state = node_state

    if final_state:
        update_data: dict = {
            "status": RequestStatus.COMPLETED,
            "extracted_data": {
                "figure_name": final_state.get("figure_name"),
                "time_period": final_state.get("time_period"),
                "region": final_state.get("region"),
                "occupation": final_state.get("occupation"),
            },
            "research_data": {
                "historical_context": final_state.get("historical_context"),
                "clothing_details": final_state.get("clothing_details"),
                "physical_description": final_state.get("physical_description"),
            },
            "generated_prompt": final_state.get("image_prompt"),
            "agent_trace": final_state.get("agent_trace", []),
            "llm_calls": final_state.get("llm_calls", []),
        }

        if final_state.get("error"):
            update_data["status"] = RequestStatus.FAILED
            update_data["error_message"] = final_state["error"]

        await repo.update(request_id, **update_data)

        if image_attempts:
            # Persist every attempt; for the last one, use original_image_path if
            # facial compositing saved a copy before overwriting.
            for i, attempt in enumerate(image_attempts):
                is_last = i == len(image_attempts) - 1
                file_path = (
                    (final_state.get("original_image_path") or attempt["image_path"])
                    if is_last
                    else attempt["image_path"]
                )
                session.add(GeneratedImage(
                    request_id=uuid.UUID(request_id),
                    figure_id=None,
                    file_path=file_path,
                    prompt_used=attempt["prompt"],
                    provider=attempt["provider"],
                    width=512,
                    height=512,
                    validation_score=attempt["validation_score"],
                ))

            # If facial compositing ran, also record the composited result
            if final_state.get("swapped_image_path"):
                session.add(GeneratedImage(
                    request_id=uuid.UUID(request_id),
                    figure_id=None,
                    file_path=final_state["swapped_image_path"],
                    prompt_used=final_state.get("image_prompt", ""),
                    provider="facefusion",
                    width=512,
                    height=512,
                    validation_score=final_state.get("validation_score"),
                ))
        elif final_state.get("image_path"):
            # Fallback: streaming loop missed events (e.g. resumed checkpoint)
            original_path = final_state.get("original_image_path") or final_state["image_path"]
            session.add(GeneratedImage(
                request_id=uuid.UUID(request_id),
                figure_id=None,
                file_path=original_path,
                prompt_used=final_state.get("image_prompt", ""),
                provider=final_state.get("image_provider", "mock"),
                width=512,
                height=512,
                validation_score=final_state.get("validation_score"),
            ))
            if final_state.get("swapped_image_path"):
                session.add(GeneratedImage(
                    request_id=uuid.UUID(request_id),
                    figure_id=None,
                    file_path=final_state["swapped_image_path"],
                    prompt_used=final_state.get("image_prompt", ""),
                    provider="facefusion",
                    width=512,
                    height=512,
                    validation_score=final_state.get("validation_score"),
                ))

        await session.commit()

    await publish_progress(channel, {
        "status": "completed" if not (final_state or {}).get("error") else "failed",
        "message": "Generation complete",
    })


async def run_generation_pipeline(
    request_id: str,
    input_text: str,
    *,
    source_face_path: str | None = None,
) -> None:
    channel = f"generation:{request_id}"

    async with async_session() as session:
        repo = RequestRepository(session)

        try:
            await repo.update(request_id, status=RequestStatus.EXTRACTING)
            await session.commit()

            await publish_progress(channel, {
                "status": "extracting",
                "agent": "extraction",
                "message": "Extracting figure details...",
            })

            initial_state: AgentState = {
                "request_id": request_id,
                "input_text": input_text,
                "agent_trace": [],
                "llm_calls": [],
                "retry_count": 0,
                "should_regenerate": False,
                "error": None,
            }
            if source_face_path:
                initial_state["source_face_path"] = source_face_path

            config = {"configurable": {"thread_id": request_id}}
            await _execute_graph(request_id, initial_state, config, channel, repo, session)

        except Exception as e:
            logger.exception(f"Generation pipeline failed for {request_id}")
            await repo.update(
                request_id,
                status=RequestStatus.FAILED,
                error_message=str(e),
            )
            await session.commit()
            await publish_progress(channel, {
                "status": "failed",
                "message": str(e),
            })


async def retry_generation_pipeline(request_id: str, from_step: str) -> None:
    """Resume a failed generation pipeline from a specific step.

    Uses the LangGraph checkpointer to rewind state to just before ``from_step``
    and re-runs the graph from that point.  ``from_step="orchestrator"`` performs
    a full restart using the original input stored in the database.

    Note: requires the in-process MemorySaver checkpoint to still be alive.
    If the server has restarted since the original run, retrying from
    ``orchestrator`` is the safe fallback (it doesn't rely on checkpoint state).
    """
    channel = f"generation:{request_id}"
    config = {"configurable": {"thread_id": request_id}}

    async with async_session() as session:
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

            # Delete stale image records when re-generating images
            if from_step in _STEPS_CLEAR_IMAGES:
                image_repo = ImageRepository(session)
                existing = await image_repo.list_by_request(uuid.UUID(request_id))
                for img in existing:
                    await session.delete(img)

            await session.commit()

            await publish_progress(channel, {
                "status": retry_status,
                "agent": from_step,
                "message": f"Retrying from {from_step}...",
            })

            if from_step == "orchestrator":
                # Full restart — does not rely on checkpoint state
                initial_state: AgentState = {
                    "request_id": request_id,
                    "input_text": request.input_text,
                    "agent_trace": [],
                    "llm_calls": [],
                    "retry_count": 0,
                    "should_regenerate": False,
                    "error": None,
                }
                await _execute_graph(request_id, initial_state, config, channel, repo, session)
            else:
                # Rewind checkpoint: update state as if the predecessor node just ran,
                # so LangGraph will run `from_step` next when we call astream(None).
                predecessor = _PREDECESSOR_NODE[from_step]
                await agent_graph.aupdate_state(
                    config,
                    {"error": None, "should_regenerate": False, "retry_count": 0},
                    as_node=predecessor,
                )
                await _execute_graph(request_id, None, config, channel, repo, session)

        except Exception as e:
            logger.exception(f"Retry pipeline failed for {request_id} (from_step={from_step})")
            await repo.update(
                request_id,
                status=RequestStatus.FAILED,
                error_message=str(e),
            )
            await session.commit()
            await publish_progress(channel, {
                "status": "failed",
                "message": str(e),
            })
