from langgraph.graph import END, StateGraph

import chronocanvas.agents.checkpointer as _ckpt
from chronocanvas.agents.decisions import (
    should_continue_after_image,
    should_continue_after_orchestrator,
    should_continue_after_validation,
)
from chronocanvas.agents.invariants import checked
from chronocanvas.agents.nodes.export import export_node
from chronocanvas.agents.nodes.extraction import extraction_node
from chronocanvas.agents.nodes.face_search import face_search_node
from chronocanvas.agents.nodes.facial_compositing import facial_compositing_node
from chronocanvas.agents.nodes.image_generation import image_generation_node
from chronocanvas.agents.nodes.multimodal_validation import multimodal_validation_node
from chronocanvas.agents.nodes.orchestrator import orchestrator_node
from chronocanvas.agents.nodes.prompt_generation import prompt_generation_node
from chronocanvas.agents.nodes.research import research_node
from chronocanvas.agents.nodes.validation import validation_node
from chronocanvas.agents.state import AgentState


def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    # Add nodes — each wrapped with runtime invariant checks
    graph.add_node("orchestrator", checked("orchestrator")(orchestrator_node))
    graph.add_node("extraction", checked("extraction")(extraction_node))
    graph.add_node("research", checked("research")(research_node))
    graph.add_node("face_search", checked("face_search")(face_search_node))
    graph.add_node("prompt_generation", checked("prompt_generation")(prompt_generation_node))
    graph.add_node("image_generation", checked("image_generation")(image_generation_node))
    graph.add_node("validation", checked("validation")(validation_node))
    graph.add_node(
        "multimodal_validation",
        checked("multimodal_validation")(multimodal_validation_node),
    )
    graph.add_node("facial_compositing", checked("facial_compositing")(facial_compositing_node))
    graph.add_node("export", checked("export")(export_node))

    # Define edges
    graph.set_entry_point("orchestrator")
    graph.add_conditional_edges(
        "orchestrator",
        should_continue_after_orchestrator,
        {"continue": "extraction", "error": END},
    )
    graph.add_edge("extraction", "research")
    graph.add_edge("research", "face_search")
    graph.add_edge("face_search", "prompt_generation")
    graph.add_edge("prompt_generation", "image_generation")

    graph.add_conditional_edges(
        "image_generation",
        should_continue_after_image,
        {"validate": "validation", "error": END},
    )

    graph.add_conditional_edges(
        "validation",
        should_continue_after_validation,
        {"continue": "multimodal_validation", "regenerate": "prompt_generation", "error": END},
    )

    graph.add_edge("multimodal_validation", "facial_compositing")
    graph.add_edge("facial_compositing", "export")
    graph.add_edge("export", END)

    return graph


def get_compiled_graph():
    graph = build_graph()
    return graph.compile(checkpointer=_ckpt.checkpointer)


def recompile_graph():
    """Recompile the singleton graphs with the current checkpointer.

    Called after ``init_checkpointer`` upgrades from MemorySaver to
    AsyncPostgresSaver so that the running graph uses durable storage.
    """
    global agent_graph, story_graph
    agent_graph = get_compiled_graph()

    from chronocanvas.agents.story.graph import get_compiled_story_graph
    story_graph = get_compiled_story_graph()


# Singleton compiled graph — compiled with MemorySaver at import time,
# then recompiled with the durable Postgres checkpointer during startup.
agent_graph = get_compiled_graph()
story_graph = None  # Compiled lazily or during recompile_graph()
