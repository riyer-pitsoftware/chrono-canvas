from typing import Any

from chronocanvas.agents.state import AgentState
from chronocanvas.db.models.request import RequestStatus
from chronocanvas.db.repositories.requests import RequestRepository
from chronocanvas.services.image_recorder import ImageAttemptRecorder
from chronocanvas.services.progress import ProgressPublisher
from chronocanvas.services.state_projector import RequestStateProjector


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

        async for event in self._graph.astream(initial_state, config=config):
            for node_name, node_state in event.items():
                current_agent = node_state.get("current_agent", node_name)

                if current_agent == "image_generation" and node_state.get("image_path"):
                    self._recorder.on_image_generated(node_state)

                if current_agent == "validation":
                    self._recorder.on_validation(node_state)

                update_kwargs = self._projector.project(node_state, current_agent)
                update_kwargs["agent_trace"] = self._projector.attach_snapshot(
                    update_kwargs["agent_trace"], current_agent, node_state
                )

                await self._repo.update(request_id, **update_kwargs)
                await self._session.commit()

                await self._publisher.publish_agent(
                    channel, current_agent, update_kwargs["status"]
                )

                final_state = node_state

        if final_state:
            update_data: dict[str, Any] = {
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

            await self._repo.update(request_id, **update_data)
            await self._recorder.flush(self._session, request_id, final_state)
            await self._session.commit()

        await self._publisher.publish_terminal(
            channel, failed=bool((final_state or {}).get("error"))
        )
