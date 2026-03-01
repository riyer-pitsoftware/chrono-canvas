"""Story generation pipeline — runs the story LangGraph for creative_story mode."""

import logging
from typing import Any

from chronocanvas.agents.story.state import StoryState
from chronocanvas.db.engine import async_session as _default_session_factory
from chronocanvas.db.models.request import RequestStatus
from chronocanvas.db.repositories.requests import RequestRepository
from chronocanvas.services.progress import ProgressPublisher

logger = logging.getLogger(__name__)


async def run_story_pipeline(
    request_id: str,
    input_text: str,
    *,
    session_factory=None,
    graph=None,
) -> None:
    if graph is None:
        from chronocanvas.agents.story.graph import get_compiled_story_graph
        graph = get_compiled_story_graph()

    _sf = session_factory if session_factory is not None else _default_session_factory
    channel = f"generation:{request_id}"
    publisher = ProgressPublisher()

    async with _sf() as session:
        repo = RequestRepository(session)
        try:
            await repo.update(request_id, status=RequestStatus.EXTRACTING)
            await session.commit()
            await publisher.publish(channel, {
                "status": "extracting",
                "agent": "character_extraction",
                "message": "Extracting characters from story...",
            })

            initial_state: StoryState = {
                "request_id": request_id,
                "input_text": input_text,
                "characters": [],
                "scenes": [],
                "panels": [],
                "agent_trace": [],
                "llm_calls": [],
                "total_scenes": 0,
                "completed_scenes": 0,
                "error": None,
            }

            config = {"configurable": {"thread_id": f"story-{request_id}"}}

            final_state: dict[str, Any] | None = None
            failed = False

            try:
                async for event in graph.astream(initial_state, config=config):
                    for node_name, node_state in event.items():
                        current_agent = node_state.get("current_agent", node_name)

                        # Determine status from current agent
                        status_map = {
                            "story_orchestrator": RequestStatus.PENDING,
                            "character_extraction": RequestStatus.EXTRACTING,
                            "scene_decomposition": RequestStatus.EXTRACTING,
                            "scene_prompt_generation": RequestStatus.GENERATING_PROMPT,
                            "scene_image_generation": RequestStatus.GENERATING_IMAGE,
                            "storyboard_export": RequestStatus.COMPLETED,
                        }
                        agent_status = status_map.get(current_agent, RequestStatus.EXTRACTING)

                        update_kwargs: dict[str, Any] = {
                            "status": agent_status,
                            "current_agent": current_agent,
                            "agent_trace": node_state.get("agent_trace"),
                            "llm_calls": node_state.get("llm_calls"),
                        }
                        # Remove None values to avoid overwriting with nulls
                        update_kwargs = {k: v for k, v in update_kwargs.items() if v is not None}

                        if node_state.get("error"):
                            update_kwargs["status"] = RequestStatus.FAILED
                            update_kwargs["error_message"] = node_state["error"]
                            failed = True

                        try:
                            await repo.update(request_id, **update_kwargs)
                            await session.commit()
                        except Exception:
                            logger.exception(
                                "Failed to persist state for story node %s",
                                current_agent,
                            )
                            await session.rollback()

                        try:
                            status = update_kwargs.get(
                                "status", agent_status,
                            )
                            await publisher.publish_agent(
                                channel, current_agent, status,
                            )
                        except Exception:
                            logger.warning(
                                "Failed to publish story progress for %s",
                                current_agent,
                                exc_info=True,
                            )

                        final_state = node_state

                # Persist final storyboard_data
                if final_state and not failed:
                    # Gather storyboard data from accumulated state across all nodes
                    # We need to get the full accumulated state from the graph
                    snapshot = await graph.aget_state(config)
                    full_state = snapshot.values if snapshot else {}

                    storyboard_data = {
                        "characters": full_state.get("characters", []),
                        "scenes": full_state.get("scenes", []),
                        "panels": [
                            {
                                "scene_index": p.get("scene_index"),
                                "description": p.get("description"),
                                "characters": p.get("characters", []),
                                "mood": p.get("mood"),
                                "setting": p.get("setting"),
                                "image_prompt": p.get("image_prompt"),
                                "image_path": p.get("image_path"),
                                "status": p.get("status"),
                            }
                            for p in full_state.get("panels", [])
                        ],
                        "total_scenes": full_state.get("total_scenes", 0),
                        "completed_scenes": full_state.get("completed_scenes", 0),
                    }

                    await repo.update(
                        request_id,
                        status=RequestStatus.COMPLETED,
                        storyboard_data=storyboard_data,
                        agent_trace=full_state.get("agent_trace", []),
                        llm_calls=full_state.get("llm_calls", []),
                    )
                    await session.commit()

            except Exception:
                failed = True
                logger.exception("Story pipeline failed for %s", request_id)
                try:
                    await session.rollback()
                    await repo.update(
                        request_id,
                        status=RequestStatus.FAILED,
                        error_message="Story pipeline error",
                    )
                    await session.commit()
                except Exception:
                    logger.exception("Failed to persist terminal error state")
            finally:
                try:
                    await publisher.publish_terminal(channel, failed=failed)
                except Exception:
                    logger.warning("Failed to publish terminal event", exc_info=True)

        except Exception as e:
            logger.exception("Story pipeline setup failed for %s", request_id)
            await repo.update(request_id, status=RequestStatus.FAILED, error_message=str(e))
            await session.commit()
            await publisher.publish(channel, {"status": "failed", "message": str(e)})
