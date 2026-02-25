"""Tests for executable architecture invariants."""

from __future__ import annotations

import time

import pytest

from chronocanvas.agents.invariants import (
    FULL_PIPELINE_NODES,
    InvariantViolationError,
    check_postcondition,
    check_precondition,
    validate_all_llm_calls,
    validate_initial_state,
    validate_llm_call,
    validate_node_output,
    validate_substate_types,
    validate_trace_completeness,
    validate_trace_entry,
)


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def make_state(**overrides) -> dict:
    base = {
        "request_id": "req-001",
        "input_text": "Napoleon Bonaparte in battle",
        "agent_trace": [],
        "llm_calls": [],
        "retry_count": 0,
    }
    base.update(overrides)
    return base


def make_llm_call(**overrides) -> dict:
    base = {
        "agent": "extraction",
        "timestamp": time.time(),
        "provider": "ollama",
        "model": "llama3.1:8b",
        "input_tokens": 120,
        "output_tokens": 80,
        "cost": 0.0,
        "duration_ms": 450,
        "requested_provider": "ollama",
        "fallback": False,
    }
    base.update(overrides)
    return base


def make_trace(nodes: list[str] | None = None) -> list[dict]:
    nodes = nodes or FULL_PIPELINE_NODES
    return [{"agent": n, "timestamp": time.time()} for n in nodes]


# ---------------------------------------------------------------------------
# TestStateValidators
# ---------------------------------------------------------------------------


class TestStateValidators:
    def test_valid_initial_state_passes(self):
        validate_initial_state(make_state())

    @pytest.mark.parametrize("field", ["request_id", "input_text"])
    def test_missing_required_string(self, field):
        state = make_state()
        del state[field]
        with pytest.raises(InvariantViolationError, match=field):
            validate_initial_state(state)

    @pytest.mark.parametrize("field", ["request_id", "input_text"])
    def test_empty_string_rejected(self, field):
        with pytest.raises(InvariantViolationError, match=field):
            validate_initial_state(make_state(**{field: ""}))

    def test_agent_trace_wrong_type(self):
        with pytest.raises(InvariantViolationError, match="agent_trace"):
            validate_initial_state(make_state(agent_trace="bad"))

    def test_llm_calls_wrong_type(self):
        with pytest.raises(InvariantViolationError, match="llm_calls"):
            validate_initial_state(make_state(llm_calls=None))

    def test_retry_count_wrong_type(self):
        with pytest.raises(InvariantViolationError, match="retry_count"):
            validate_initial_state(make_state(retry_count="0"))

    def test_substate_types_valid(self):
        state = make_state(
            extraction={"figure_name": "Napoleon"},
            research={"historical_context": "French Revolution era"},
            prompt={"image_prompt": "A portrait of Napoleon"},
            image={"image_path": "/tmp/out.png"},
        )
        validate_substate_types(state)

    def test_substate_types_missing_ok(self):
        validate_substate_types(make_state())

    def test_substate_wrong_type(self):
        with pytest.raises(InvariantViolationError, match="extraction"):
            validate_substate_types(make_state(extraction="bad"))

    def test_substate_field_wrong_type(self):
        with pytest.raises(InvariantViolationError, match="figure_name"):
            validate_substate_types(make_state(extraction={"figure_name": 42}))


# ---------------------------------------------------------------------------
# TestNodeContracts
# ---------------------------------------------------------------------------


class TestNodeContracts:
    # --- Preconditions ---

    def test_orchestrator_pre_needs_input(self):
        with pytest.raises(InvariantViolationError):
            check_precondition("orchestrator", {})

    def test_extraction_pre_rejects_error(self):
        state = make_state(error="something went wrong")
        with pytest.raises(InvariantViolationError, match="error"):
            check_precondition("extraction", state)

    def test_research_pre_needs_extraction(self):
        with pytest.raises(InvariantViolationError, match="extraction"):
            check_precondition("research", make_state())

    def test_research_pre_needs_figure_name(self):
        state = make_state(extraction={"figure_name": ""})
        with pytest.raises(InvariantViolationError, match="figure_name"):
            check_precondition("research", state)

    def test_face_search_pre_needs_extraction(self):
        with pytest.raises(InvariantViolationError):
            check_precondition("face_search", make_state())

    def test_prompt_generation_pre_needs_both(self):
        state = make_state(extraction={"figure_name": "Napoleon"})
        with pytest.raises(InvariantViolationError, match="research"):
            check_precondition("prompt_generation", state)

    def test_image_generation_pre_needs_prompt(self):
        state = make_state(prompt={"image_prompt": ""})
        with pytest.raises(InvariantViolationError, match="image_prompt"):
            check_precondition("image_generation", state)

    def test_validation_pre_needs_prompt_and_extraction(self):
        with pytest.raises(InvariantViolationError):
            check_precondition("validation", make_state())

    def test_export_pre_needs_image(self):
        with pytest.raises(InvariantViolationError):
            check_precondition("export", make_state())

    # --- Postconditions ---

    def test_orchestrator_post_needs_current_agent(self):
        with pytest.raises(InvariantViolationError):
            check_postcondition("orchestrator", {})

    def test_extraction_post_needs_figure_name(self):
        with pytest.raises(InvariantViolationError):
            check_postcondition("extraction", {"extraction": {}})

    def test_extraction_post_valid(self):
        check_postcondition("extraction", {"extraction": {"figure_name": "Napoleon"}})

    def test_research_post_valid(self):
        check_postcondition(
            "research", {"research": {"historical_context": "French general"}}
        )

    def test_face_search_post_no_face_ok(self):
        check_postcondition("face_search", {})

    def test_face_search_post_face_needs_path(self):
        with pytest.raises(InvariantViolationError, match="source_face_path"):
            check_postcondition("face_search", {"face": {"face_search_url": "http://x"}})

    def test_prompt_generation_post_valid(self):
        check_postcondition(
            "prompt_generation", {"prompt": {"image_prompt": "A portrait"}}
        )

    def test_image_generation_post_error_ok(self):
        check_postcondition("image_generation", {"error": "provider down"})

    def test_image_generation_post_needs_path(self):
        with pytest.raises(InvariantViolationError):
            check_postcondition("image_generation", {"image": {}})

    def test_validation_must_not_set_error(self):
        """Invariant #4: validation is informational only."""
        with pytest.raises(InvariantViolationError, match="informational"):
            check_postcondition("validation", {"error": "bad image"})

    def test_validation_post_score_present(self):
        check_postcondition(
            "validation",
            {"validation": {"validation_score": 0.85, "validation_passed": True}},
        )

    def test_validation_post_missing_score(self):
        with pytest.raises(InvariantViolationError, match="validation_score"):
            check_postcondition("validation", {"validation": {}})

    def test_export_post_needs_path(self):
        with pytest.raises(InvariantViolationError):
            check_postcondition("export", {"export": {}})

    def test_export_post_valid(self):
        check_postcondition("export", {"export": {"export_path": "/out/img.png"}})

    def test_facial_compositing_post_always_ok(self):
        check_postcondition("facial_compositing", {})

    def test_unknown_node_no_error(self):
        check_precondition("unknown_node", {})
        check_postcondition("unknown_node", {})

    # --- validate_node_output ---

    def test_node_output_current_agent_mismatch(self):
        with pytest.raises(InvariantViolationError, match="current_agent"):
            validate_node_output(
                "extraction",
                {"current_agent": "research", "extraction": {"figure_name": "X"}},
            )

    def test_node_output_valid(self):
        validate_node_output(
            "extraction",
            {"current_agent": "extraction", "extraction": {"figure_name": "X"}},
        )


# ---------------------------------------------------------------------------
# TestLLMCallAudit
# ---------------------------------------------------------------------------


class TestLLMCallAudit:
    def test_valid_call_no_violations(self):
        assert validate_llm_call(make_llm_call()) == []

    @pytest.mark.parametrize(
        "field",
        [
            "agent",
            "timestamp",
            "provider",
            "model",
            "input_tokens",
            "output_tokens",
            "cost",
            "duration_ms",
            "requested_provider",
            "fallback",
        ],
    )
    def test_missing_field_reported(self, field):
        call = make_llm_call()
        del call[field]
        violations = validate_llm_call(call)
        assert any(field in v for v in violations)

    def test_validate_all_passes(self):
        state = make_state(llm_calls=[make_llm_call(), make_llm_call()])
        validate_all_llm_calls(state)

    def test_validate_all_collects_violations(self):
        bad_call = make_llm_call()
        del bad_call["agent"]
        del bad_call["model"]
        state = make_state(llm_calls=[make_llm_call(), bad_call])
        with pytest.raises(InvariantViolationError, match="llm_calls\\[1\\]"):
            validate_all_llm_calls(state)

    def test_empty_llm_calls_ok(self):
        validate_all_llm_calls(make_state())


# ---------------------------------------------------------------------------
# TestTraceCompleteness
# ---------------------------------------------------------------------------


class TestTraceCompleteness:
    def test_full_trace_passes(self):
        state = make_state(agent_trace=make_trace())
        validate_trace_completeness(state)

    def test_missing_node_raises(self):
        partial = [n for n in FULL_PIPELINE_NODES if n != "validation"]
        state = make_state(agent_trace=make_trace(partial))
        with pytest.raises(InvariantViolationError, match="validation"):
            validate_trace_completeness(state)

    def test_error_prefix_valid(self):
        prefix = FULL_PIPELINE_NODES[:4]  # up to face_search
        state = make_state(agent_trace=make_trace(prefix))
        validate_trace_completeness(state, expect_error=True)

    def test_error_prefix_wrong_order(self):
        wrong = ["extraction", "orchestrator"]  # swapped
        state = make_state(agent_trace=make_trace(wrong))
        with pytest.raises(InvariantViolationError, match="prefix mismatch"):
            validate_trace_completeness(state, expect_error=True)

    def test_empty_trace_error_ok(self):
        state = make_state(agent_trace=[])
        validate_trace_completeness(state, expect_error=True)

    def test_empty_trace_success_raises(self):
        state = make_state(agent_trace=[])
        with pytest.raises(InvariantViolationError, match="missing nodes"):
            validate_trace_completeness(state)

    def test_trace_entry_valid(self):
        validate_trace_entry({"agent": "extraction", "timestamp": time.time()})

    def test_trace_entry_missing_agent(self):
        with pytest.raises(InvariantViolationError, match="agent"):
            validate_trace_entry({"timestamp": time.time()})

    def test_trace_entry_bad_timestamp(self):
        with pytest.raises(InvariantViolationError, match="timestamp"):
            validate_trace_entry({"agent": "extraction", "timestamp": -1})

    def test_trace_entry_zero_timestamp(self):
        with pytest.raises(InvariantViolationError, match="timestamp"):
            validate_trace_entry({"agent": "extraction", "timestamp": 0})
