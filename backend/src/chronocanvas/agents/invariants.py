"""Executable architecture invariants for the ChronoCanvas pipeline.

Each function validates a specific contract from docs/architecture-invariants.md.
Callable from tests and at runtime via ``settings.invariant_checks_enabled``.

Runtime enforcement is wired through the :func:`checked` decorator which wraps
node functions with precondition, postcondition, and LLM-call audit checks.
When ``invariant_strict`` is True, violations raise; otherwise they are logged
as warnings so the pipeline is never blocked in production.
"""

from __future__ import annotations

import functools
import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)


class InvariantViolationError(AssertionError):
    """Raised when a pipeline invariant is violated."""


# ---------------------------------------------------------------------------
# Ordered node list for the full pipeline
# ---------------------------------------------------------------------------

FULL_PIPELINE_NODES = [
    "orchestrator",
    "extraction",
    "research",
    "face_search",
    "prompt_generation",
    "image_generation",
    "validation",
    "facial_compositing",
    "export",
]


# ---------------------------------------------------------------------------
# 1. State validators
# ---------------------------------------------------------------------------


def validate_initial_state(state: dict[str, Any]) -> None:
    """Check that the initial state contains required top-level fields."""
    _require_str(state, "request_id", "initial state")
    _require_str(state, "input_text", "initial state")

    if not isinstance(state.get("agent_trace"), list):
        raise InvariantViolationError("initial state: 'agent_trace' must be a list")
    if not isinstance(state.get("llm_calls"), list):
        raise InvariantViolationError("initial state: 'llm_calls' must be a list")
    if not isinstance(state.get("retry_count"), int):
        raise InvariantViolationError("initial state: 'retry_count' must be an int")


def validate_substate_types(state: dict[str, Any]) -> None:
    """If namespace sub-dicts are present, verify key fields have correct types."""
    ext = state.get("extraction")
    if ext is not None:
        if not isinstance(ext, dict):
            raise InvariantViolationError("'extraction' must be a dict")
        if "figure_name" in ext and not isinstance(ext["figure_name"], str):
            raise InvariantViolationError("extraction.figure_name must be a str")

    res = state.get("research")
    if res is not None:
        if not isinstance(res, dict):
            raise InvariantViolationError("'research' must be a dict")
        if "historical_context" in res and not isinstance(res["historical_context"], str):
            raise InvariantViolationError("research.historical_context must be a str")

    prompt = state.get("prompt")
    if prompt is not None:
        if not isinstance(prompt, dict):
            raise InvariantViolationError("'prompt' must be a dict")
        if "image_prompt" in prompt and not isinstance(prompt["image_prompt"], str):
            raise InvariantViolationError("prompt.image_prompt must be a str")

    img = state.get("image")
    if img is not None:
        if not isinstance(img, dict):
            raise InvariantViolationError("'image' must be a dict")
        if "image_path" in img and not isinstance(img["image_path"], str):
            raise InvariantViolationError("image.image_path must be a str")


def validate_node_output(node_name: str, output: dict[str, Any]) -> None:
    """Check that ``current_agent`` matches *node_name* and run postcondition."""
    ca = output.get("current_agent")
    if ca is not None and ca != node_name:
        raise InvariantViolationError(
            f"Node '{node_name}' set current_agent to '{ca}' (expected '{node_name}')"
        )
    check_postcondition(node_name, output)


# ---------------------------------------------------------------------------
# 2. Node pre/postconditions
# ---------------------------------------------------------------------------

def _require_str(d: dict[str, Any], key: str, context: str) -> None:
    val = d.get(key)
    if not isinstance(val, str) or not val:
        raise InvariantViolationError(f"{context}: '{key}' must be a non-empty string")


def _require_subdict(d: dict[str, Any], key: str, context: str) -> dict[str, Any]:
    val = d.get(key)
    if not isinstance(val, dict):
        raise InvariantViolationError(f"{context}: '{key}' must be a dict")
    return val


# --- Preconditions ---

def pre_orchestrator(state: dict[str, Any]) -> None:
    _require_str(state, "input_text", "orchestrator pre")


def pre_extraction(state: dict[str, Any]) -> None:
    _require_str(state, "input_text", "extraction pre")
    if state.get("error"):
        raise InvariantViolationError("extraction pre: state has error set")


def pre_research(state: dict[str, Any]) -> None:
    ext = _require_subdict(state, "extraction", "research pre")
    _require_str(ext, "figure_name", "research pre (extraction)")


def pre_face_search(state: dict[str, Any]) -> None:
    _require_subdict(state, "extraction", "face_search pre")


def pre_prompt_generation(state: dict[str, Any]) -> None:
    _require_subdict(state, "extraction", "prompt_generation pre")
    _require_subdict(state, "research", "prompt_generation pre")


def pre_image_generation(state: dict[str, Any]) -> None:
    prompt = _require_subdict(state, "prompt", "image_generation pre")
    _require_str(prompt, "image_prompt", "image_generation pre (prompt)")


def pre_validation(state: dict[str, Any]) -> None:
    _require_subdict(state, "prompt", "validation pre")
    _require_subdict(state, "extraction", "validation pre")


def pre_facial_compositing(state: dict[str, Any]) -> None:
    _require_subdict(state, "image", "facial_compositing pre")


def pre_export(state: dict[str, Any]) -> None:
    _require_subdict(state, "image", "export pre")


# --- Postconditions ---

def post_orchestrator(output: dict[str, Any]) -> None:
    _require_str(output, "current_agent", "orchestrator post")


def post_extraction(output: dict[str, Any]) -> None:
    ext = _require_subdict(output, "extraction", "extraction post")
    _require_str(ext, "figure_name", "extraction post (extraction)")


def post_research(output: dict[str, Any]) -> None:
    res = _require_subdict(output, "research", "research post")
    _require_str(res, "historical_context", "research post (research)")


def post_face_search(output: dict[str, Any]) -> None:
    face = output.get("face")
    if isinstance(face, dict) and face:
        _require_str(face, "source_face_path", "face_search post (face)")


def post_prompt_generation(output: dict[str, Any]) -> None:
    prompt = _require_subdict(output, "prompt", "prompt_generation post")
    _require_str(prompt, "image_prompt", "prompt_generation post (prompt)")


def post_image_generation(output: dict[str, Any]) -> None:
    if output.get("error"):
        return  # error is acceptable
    img = _require_subdict(output, "image", "image_generation post")
    _require_str(img, "image_path", "image_generation post (image)")


def post_validation(output: dict[str, Any]) -> None:
    # Invariant #4: validation must NOT set error
    if output.get("error"):
        raise InvariantViolationError(
            "validation post: validation node must not set 'error' "
            "(invariant #4 — validation is informational only)"
        )
    val = output.get("validation")
    if isinstance(val, dict):
        if "validation_score" not in val:
            raise InvariantViolationError("validation post: 'validation_score' missing")


def post_facial_compositing(output: dict[str, Any]) -> None:
    pass  # no strict postcondition


def post_export(output: dict[str, Any]) -> None:
    exp = _require_subdict(output, "export", "export post")
    _require_str(exp, "export_path", "export post (export)")


# --- Dispatchers ---

_PRECONDITIONS: dict[str, Any] = {
    "orchestrator": pre_orchestrator,
    "extraction": pre_extraction,
    "research": pre_research,
    "face_search": pre_face_search,
    "prompt_generation": pre_prompt_generation,
    "image_generation": pre_image_generation,
    "validation": pre_validation,
    "facial_compositing": pre_facial_compositing,
    "export": pre_export,
}

_POSTCONDITIONS: dict[str, Any] = {
    "orchestrator": post_orchestrator,
    "extraction": post_extraction,
    "research": post_research,
    "face_search": post_face_search,
    "prompt_generation": post_prompt_generation,
    "image_generation": post_image_generation,
    "validation": post_validation,
    "facial_compositing": post_facial_compositing,
    "export": post_export,
}


def check_precondition(node_name: str, state: dict[str, Any]) -> None:
    fn = _PRECONDITIONS.get(node_name)
    if fn:
        fn(state)


def check_postcondition(node_name: str, output: dict[str, Any]) -> None:
    fn = _POSTCONDITIONS.get(node_name)
    if fn:
        fn(output)


# ---------------------------------------------------------------------------
# 3. LLM call audit completeness
# ---------------------------------------------------------------------------

_LLM_CALL_REQUIRED_FIELDS = (
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
)


def validate_llm_call(call: dict[str, Any]) -> list[str]:
    """Return list of missing/invalid fields for a single LLM call record."""
    violations: list[str] = []
    for field in _LLM_CALL_REQUIRED_FIELDS:
        if field not in call:
            violations.append(f"missing '{field}'")
    return violations


def validate_all_llm_calls(state: dict[str, Any]) -> None:
    """Validate every entry in ``state['llm_calls']``."""
    calls = state.get("llm_calls", [])
    all_violations: list[str] = []
    for i, call in enumerate(calls):
        issues = validate_llm_call(call)
        if issues:
            all_violations.append(f"llm_calls[{i}]: {', '.join(issues)}")
    if all_violations:
        raise InvariantViolationError(
            "LLM call audit violations:\n" + "\n".join(all_violations)
        )


# ---------------------------------------------------------------------------
# 4. Trace completeness
# ---------------------------------------------------------------------------


def validate_trace_entry(entry: dict[str, Any]) -> None:
    """Validate a single trace entry has required fields."""
    if not isinstance(entry.get("agent"), str) or not entry["agent"]:
        raise InvariantViolationError("trace entry: 'agent' must be a non-empty string")
    ts = entry.get("timestamp")
    if not isinstance(ts, (int, float)) or ts <= 0:
        raise InvariantViolationError("trace entry: 'timestamp' must be a positive number")


def validate_trace_completeness(
    state: dict[str, Any], expect_error: bool = False
) -> None:
    """Check that all expected nodes appear in the agent trace.

    For successful runs, all nodes in ``FULL_PIPELINE_NODES`` must appear.
    For error runs (``expect_error=True``), the trace must be a contiguous
    prefix of the full pipeline.
    """
    trace = state.get("agent_trace", [])
    traced_agents = [e["agent"] for e in trace if isinstance(e, dict) and "agent" in e]

    if expect_error:
        # Must be a contiguous prefix
        for i, agent in enumerate(traced_agents):
            if i >= len(FULL_PIPELINE_NODES):
                break
            if agent != FULL_PIPELINE_NODES[i]:
                raise InvariantViolationError(
                    f"trace prefix mismatch at index {i}: "
                    f"expected '{FULL_PIPELINE_NODES[i]}', got '{agent}'"
                )
    else:
        missing = [n for n in FULL_PIPELINE_NODES if n not in traced_agents]
        if missing:
            raise InvariantViolationError(
                f"trace completeness: missing nodes: {', '.join(missing)}"
            )


# ---------------------------------------------------------------------------
# 5. Runtime enforcement decorator
# ---------------------------------------------------------------------------


def _report(violation: InvariantViolationError, *, strict: bool) -> None:
    """Log the violation; re-raise only when strict mode is on."""
    logger.warning("INVARIANT VIOLATION: %s", violation)
    if strict:
        raise violation


def checked(node_name: str) -> Callable:
    """Wrap an async node function with runtime invariant checks.

    Reads ``settings.invariant_checks_enabled`` / ``settings.invariant_strict``
    at call time so the feature can be toggled without restarting.

    Usage in ``graph.py``::

        graph.add_node("extraction", checked("extraction")(extraction_node))
    """

    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        async def wrapper(state: dict[str, Any]) -> dict[str, Any]:
            from chronocanvas.config import settings

            if not settings.invariant_checks_enabled:
                return await fn(state)

            strict = settings.invariant_strict

            # --- Preconditions ---
            try:
                check_precondition(node_name, state)
            except InvariantViolationError as exc:
                _report(exc, strict=strict)

            # --- Run the actual node ---
            result = await fn(state)

            # --- Postconditions ---
            try:
                validate_node_output(node_name, result)
            except InvariantViolationError as exc:
                _report(exc, strict=strict)

            # --- LLM-call audit completeness (check latest calls only) ---
            llm_calls = result.get("llm_calls", [])
            if llm_calls:
                # Only validate the tail entries added by this node
                prev_count = len(state.get("llm_calls", []))
                new_calls = llm_calls[prev_count:]
                for i, call in enumerate(new_calls):
                    issues = validate_llm_call(call)
                    if issues:
                        _report(
                            InvariantViolationError(
                                f"{node_name} llm_calls[{prev_count + i}]: "
                                f"{', '.join(issues)}"
                            ),
                            strict=strict,
                        )

            return result

        return wrapper

    return decorator
