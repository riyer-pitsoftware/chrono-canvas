"""Integration tests for checkpoint recovery after server restart.

Covers the scenario where the in-memory LangGraph checkpoint is gone and
retry_generation_pipeline must reconstruct state from the database.
"""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from chronocanvas.db.models.request import GenerationRequest
from chronocanvas.services.retry import _PREDECESSOR_NODE, RetryCoordinator

_rebuild_state_from_db = RetryCoordinator().rebuild_state_from_db


# ---------------------------------------------------------------------------
# Unit tests for _rebuild_state_from_db
# ---------------------------------------------------------------------------

def _make_request(**kwargs) -> MagicMock:
    """Return a mock GenerationRequest with sensible defaults."""
    req = MagicMock(spec=GenerationRequest)
    req.id = kwargs.get("id", uuid.uuid4())
    req.input_text = kwargs.get("input_text", "Test Figure")
    req.extracted_data = kwargs.get("extracted_data", None)
    req.research_data = kwargs.get("research_data", None)
    req.generated_prompt = kwargs.get("generated_prompt", None)
    req.agent_trace = kwargs.get("agent_trace", [])
    req.llm_calls = kwargs.get("llm_calls", [])
    return req


def test_rebuild_state_base_fields():
    req = _make_request(input_text="Chandragupta Maurya")
    state = _rebuild_state_from_db(req, "image_generation")

    assert state["request_id"] == str(req.id)
    assert state["input_text"] == "Chandragupta Maurya"
    assert state["error"] is None
    assert state["retry_count"] == 0
    assert state["should_regenerate"] is False


def test_rebuild_state_uses_extracted_data():
    req = _make_request(
        extracted_data={
            "figure_name": "Ashoka",
            "time_period": "3rd century BCE",
            "region": "India",
            "occupation": "Emperor",
        }
    )
    state = _rebuild_state_from_db(req, "image_generation")

    assert state["figure_name"] == "Ashoka"
    assert state["time_period"] == "3rd century BCE"
    assert state["region"] == "India"
    assert state["occupation"] == "Emperor"


def test_rebuild_state_uses_research_data():
    req = _make_request(
        research_data={
            "historical_context": "Founded Maurya Empire",
            "clothing_details": "Royal dhoti",
            "physical_description": "Tall and regal",
        }
    )
    state = _rebuild_state_from_db(req, "image_generation")

    assert state["historical_context"] == "Founded Maurya Empire"
    assert state["clothing_details"] == "Royal dhoti"


def test_rebuild_state_maps_generated_prompt_to_image_prompt():
    req = _make_request(generated_prompt="Portrait of Ashoka the Great")
    state = _rebuild_state_from_db(req, "image_generation")

    assert state["image_prompt"] == "Portrait of Ashoka the Great"


def test_rebuild_state_enriches_from_predecessor_snapshot():
    """Fields absent from dedicated columns are pulled from agent_trace snapshots."""
    req = _make_request(
        agent_trace=[
            {
                "agent": "prompt_generation",
                "state_snapshot": {
                    "negative_prompt": "blurry, modern",
                    "style_modifiers": ["ancient Indian", "scholarly"],
                    "image_prompt": "Aryabhata portrait",  # should not override generated_prompt
                },
            }
        ],
        generated_prompt="Override prompt from DB column",
    )
    state = _rebuild_state_from_db(req, "image_generation")

    # Snapshot-only fields are merged in
    assert state["negative_prompt"] == "blurry, modern"
    assert state["style_modifiers"] == ["ancient Indian", "scholarly"]
    # DB column takes precedence over snapshot
    assert state["image_prompt"] == "Override prompt from DB column"


def test_rebuild_state_predecessor_mapping():
    """Reconstructed state uses the correct predecessor for each step."""
    req = _make_request()
    for step, predecessor in _PREDECESSOR_NODE.items():
        state = _rebuild_state_from_db(req, step)
        # Just verify no exception is raised and basic fields are present
        assert "request_id" in state


def test_rebuild_state_skips_none_extracted_values():
    """None values in extracted_data do not overwrite defaults."""
    req = _make_request(
        extracted_data={"figure_name": "Akbar", "time_period": None}
    )
    state = _rebuild_state_from_db(req, "image_generation")

    assert state["figure_name"] == "Akbar"
    assert "time_period" not in state


# ---------------------------------------------------------------------------
# Integration test: retry with missing checkpoint reconstructs from DB
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_retry_falls_back_to_db_when_checkpoint_missing():
    """retry_generation_pipeline reconstructs state from DB after a restart.

    Simulates a server restart by returning an empty LangGraph snapshot.
    Verifies that aupdate_state is called with the full reconstructed state
    rather than just the minimal control-flag reset.
    """
    request_id = str(uuid.uuid4())

    fake_request = _make_request(
        id=uuid.UUID(request_id),
        input_text="Rani Lakshmibai",
        extracted_data={
            "figure_name": "Rani Lakshmibai",
            "time_period": "19th century CE",
            "region": "India",
            "occupation": "Queen and warrior",
        },
        research_data={
            "historical_context": "Led the Indian Rebellion of 1857",
            "clothing_details": "Warrior attire with sword",
            "physical_description": "Fierce and determined",
        },
        generated_prompt="A portrait of Rani Lakshmibai in battle armour",
    )

    async def fake_astream(_state, config):
        yield {"export": {"current_agent": "export", "agent_trace": [], "llm_calls": []}}

    mock_image_repo = AsyncMock()
    mock_image_repo.list_by_request.return_value = []

    with (
        patch("chronocanvas.services.generation.async_session") as mock_ctx,
        patch("chronocanvas.services.generation.agent_graph") as mock_graph,
        patch("chronocanvas.services.generation.ProgressPublisher", return_value=AsyncMock()),
        patch("chronocanvas.services.generation.RequestRepository") as mock_repo_cls,
        patch("chronocanvas.services.generation.ImageRepository", return_value=mock_image_repo),
    ):
        mock_session = AsyncMock()
        mock_ctx.return_value.__aenter__.return_value = mock_session
        mock_ctx.return_value.__aexit__.return_value = None

        mock_repo = AsyncMock()
        mock_repo.get.return_value = fake_request
        mock_repo.update.return_value = fake_request
        mock_repo_cls.return_value = mock_repo

        # Simulate missing checkpoint (server restarted)
        mock_graph.aget_state = AsyncMock(return_value=MagicMock(values={}))
        mock_graph.aupdate_state = AsyncMock()
        mock_graph.astream = MagicMock(return_value=fake_astream(None, None))

        await _retry_pipeline(request_id, "image_generation")

        # aupdate_state must have been called once
        mock_graph.aupdate_state.assert_awaited_once()
        call_args = mock_graph.aupdate_state.call_args

        injected_state = call_args[0][1]
        assert injected_state["input_text"] == "Rani Lakshmibai"
        assert injected_state["figure_name"] == "Rani Lakshmibai"
        assert injected_state["image_prompt"] == "A portrait of Rani Lakshmibai in battle armour"
        assert injected_state["error"] is None
        assert injected_state["retry_count"] == 0
        # as_node must be the predecessor of image_generation
        assert call_args[1]["as_node"] == "prompt_generation"


@pytest.mark.asyncio
async def test_retry_uses_minimal_reset_when_checkpoint_alive():
    """retry_generation_pipeline only resets control flags when checkpoint is alive."""
    request_id = str(uuid.uuid4())
    fake_request = _make_request(id=uuid.UUID(request_id), input_text="Akbar the Great")

    async def fake_astream(_state, config):
        yield {"export": {"current_agent": "export", "agent_trace": [], "llm_calls": []}}

    mock_image_repo = AsyncMock()
    mock_image_repo.list_by_request.return_value = []

    with (
        patch("chronocanvas.services.generation.async_session") as mock_ctx,
        patch("chronocanvas.services.generation.agent_graph") as mock_graph,
        patch("chronocanvas.services.generation.ProgressPublisher", return_value=AsyncMock()),
        patch("chronocanvas.services.generation.RequestRepository") as mock_repo_cls,
        patch("chronocanvas.services.generation.ImageRepository", return_value=mock_image_repo),
    ):
        mock_session = AsyncMock()
        mock_ctx.return_value.__aenter__.return_value = mock_session
        mock_ctx.return_value.__aexit__.return_value = None

        mock_repo = AsyncMock()
        mock_repo.get.return_value = fake_request
        mock_repo.update.return_value = fake_request
        mock_repo_cls.return_value = mock_repo

        # Checkpoint is alive — has values
        mock_graph.aget_state = AsyncMock(
            return_value=MagicMock(values={"input_text": "Akbar the Great", "figure_name": "Akbar"})
        )
        mock_graph.aupdate_state = AsyncMock()
        mock_graph.astream = MagicMock(return_value=fake_astream(None, None))

        await _retry_pipeline(request_id, "image_generation")

        mock_graph.aupdate_state.assert_awaited_once()
        call_args = mock_graph.aupdate_state.call_args
        injected_state = call_args[0][1]

        # Only control flags should be reset, not the full state
        assert set(injected_state.keys()) == {"error", "should_regenerate", "retry_count"}
        assert injected_state["error"] is None
        assert injected_state["retry_count"] == 0


# ---------------------------------------------------------------------------
# Helper: import retry pipeline after patching env
# ---------------------------------------------------------------------------

async def _retry_pipeline(request_id: str, from_step: str) -> None:
    from chronocanvas.services.generation import retry_generation_pipeline
    await retry_generation_pipeline(request_id, from_step)
