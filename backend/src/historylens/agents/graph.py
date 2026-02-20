from langgraph.graph import END, StateGraph

from historylens.agents.checkpointer import checkpointer
from historylens.agents.decisions import (
    should_continue_after_image,
    should_continue_after_validation,
)
from historylens.agents.nodes.extraction import extraction_node
from historylens.agents.nodes.export import export_node
from historylens.agents.nodes.face_swap import face_swap_node
from historylens.agents.nodes.image_generation import image_generation_node
from historylens.agents.nodes.orchestrator import orchestrator_node
from historylens.agents.nodes.prompt_generation import prompt_generation_node
from historylens.agents.nodes.research import research_node
from historylens.agents.nodes.validation import validation_node
from historylens.agents.state import AgentState


def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("orchestrator", orchestrator_node)
    graph.add_node("extraction", extraction_node)
    graph.add_node("research", research_node)
    graph.add_node("prompt_generation", prompt_generation_node)
    graph.add_node("image_generation", image_generation_node)
    graph.add_node("validation", validation_node)
    graph.add_node("face_swap", face_swap_node)
    graph.add_node("export", export_node)

    # Define edges
    graph.set_entry_point("orchestrator")
    graph.add_edge("orchestrator", "extraction")
    graph.add_edge("extraction", "research")
    graph.add_edge("research", "prompt_generation")
    graph.add_edge("prompt_generation", "image_generation")

    graph.add_conditional_edges(
        "image_generation",
        should_continue_after_image,
        {"validate": "validation", "error": END},
    )

    graph.add_conditional_edges(
        "validation",
        should_continue_after_validation,
        {"continue": "face_swap", "regenerate": "prompt_generation", "error": END},
    )

    graph.add_edge("face_swap", "export")
    graph.add_edge("export", END)

    return graph


def get_compiled_graph():
    graph = build_graph()
    return graph.compile(checkpointer=checkpointer)


# Singleton compiled graph
agent_graph = get_compiled_graph()
