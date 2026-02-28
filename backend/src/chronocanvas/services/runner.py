import logging
import uuid
from typing import Any

from chronocanvas.agents.state import AgentState
from chronocanvas.db.models.request import RequestStatus
from chronocanvas.db.repositories.requests import RequestRepository
from chronocanvas.services.image_recorder import ImageAttemptRecorder
from chronocanvas.services.progress import ProgressPublisher
from chronocanvas.services.state_projector import RequestStateProjector
from chronocanvas.services.validation import save_validation_results

logger = logging.getLogger(__name__)


class GenerationRunner:
    """Streams the LangGraph agent graph, persisting incremental state to DB and
    publishing progress events to Redis as each node completes.

    ``graph`` is injected so tests can substitute a lightweight graph without
    touching the module-level singleton.
    """

    def __init__(
        self,
        repo: RequestRepository,
        session: Any,
        publisher: ProgressPublisher,
        projector: RequestStateProjector,
        recorder: ImageAttemptRecorder,
        graph: Any,
    ) -> None:
        self._repo = repo
        self._session = session
        self._publisher = publisher
        self._projector = projector
        self._recorder = recorder
        self._graph = graph

    async def run(
        self,
        request_id: str,
        initial_state: AgentState | None,
        config: dict[str, Any],
        channel: str,
    ) -> None:
        """Execute the graph, streaming events.

        Pass ``initial_state=None`` to resume from an existing LangGraph checkpoint.
        """
        final_state: dict[str, Any] | None = None
        last_successful_agent: str | None = None
        failed = False

        try:
            async for event in self._graph.astream(initial_state, config=config):
                for node_name, node_state in event.items():
                    current_agent = node_state.get("current_agent", node_name)

                    img = node_state.get("image", {})
                    if current_agent == "image_generation" and img.get("image_path"):
                        self._recorder.on_image_generated(node_state)

                    if current_agent == "validation":
                        self._recorder.on_validation(node_state)
                        val_results = node_state.get("validation", {}).get(
                            "validation_results"
                        )
                        if val_results:
                            await save_validation_results(
                                self._session,
                                uuid.UUID(request_id),
                                val_results,
                            )

                    update_kwargs = self._projector.project(node_state, current_agent)
                    update_kwargs["agent_trace"] = self._projector.attach_snapshot(
                        update_kwargs["agent_trace"], current_agent, node_state
                    )

                    try:
                        await self._repo.update(request_id, **update_kwargs)
                        await self._session.commit()
                    except Exception:
                        logger.exception("Failed to persist state for node %s", current_agent)
                        await self._session.rollback()

                    try:
                        await self._publisher.publish_agent(
                            channel, current_agent, update_kwargs["status"]
                        )
                    except Exception:
                        logger.warning(
                            "Failed to publish progress for node %s",
                            current_agent,
                            exc_info=True,
                        )

                    last_successful_agent = current_agent
                    final_state = node_state

            if final_state:
                ext = final_state.get("extraction", {})
                res = final_state.get("research", {})
                prompt_state = final_state.get("prompt", {})
                update_data: dict[str, Any] = {
                    "status": RequestStatus.COMPLETED,
                    "extracted_data": {
                        "figure_name": ext.get("figure_name"),
                        "time_period": ext.get("time_period"),
                        "region": ext.get("region"),
                        "occupation": ext.get("occupation"),
                    },
                    "research_data": {
                        "historical_context": res.get("historical_context"),
                        "clothing_details": res.get("clothing_details"),
                        "physical_description": res.get("physical_description"),
                    },
                    "generated_prompt": prompt_state.get("image_prompt"),
                    "agent_trace": final_state.get("agent_trace", []),
                    "llm_calls": final_state.get("llm_calls", []),
                }
                if final_state.get("error"):
                    update_data["status"] = RequestStatus.FAILED
                    update_data["error_message"] = final_state["error"]
                    failed = True

                await self._repo.update(request_id, **update_data)
                await self._recorder.flush(self._session, request_id, final_state)

                await self._session.commit()

        except Exception:
            failed = True
            logger.exception("Pipeline failed at node %s", last_successful_agent or "unknown")
            try:
                await self._session.rollback()
                await self._repo.update(
                    request_id,
                    status=RequestStatus.FAILED,
                    error_message=(
                        f"Pipeline error after node: {last_successful_agent or 'unknown'}"
                    ),
                )
                await self._session.commit()
            except Exception:
                logger.exception("Failed to persist terminal error state")

        finally:
            try:
                await self._publisher.publish_terminal(channel, failed=failed)
            except Exception:
                logger.warning("Failed to publish terminal event", exc_info=True)
