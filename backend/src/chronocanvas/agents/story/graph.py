from langgraph.graph import END, StateGraph

import chronocanvas.agents.checkpointer as _ckpt
from chronocanvas.agents.story.nodes.character_extraction import character_extraction_node
from chronocanvas.agents.story.nodes.scene_decomposition import scene_decomposition_node
from chronocanvas.agents.story.nodes.scene_image_generation import scene_image_generation_node
from chronocanvas.agents.story.nodes.scene_prompt_generation import scene_prompt_generation_node
from chronocanvas.agents.story.nodes.story_orchestrator import story_orchestrator_node
from chronocanvas.agents.story.nodes.storyboard_export import storyboard_export_node
from chronocanvas.agents.story.state import StoryState


def _should_continue_after_orchestrator(state: StoryState) -> str:
    if state.get("error"):
        return "error"
    return "continue"


def build_story_graph() -> StateGraph:
    graph = StateGraph(StoryState)

    graph.add_node("story_orchestrator", story_orchestrator_node)
    graph.add_node("character_extraction", character_extraction_node)
    graph.add_node("scene_decomposition", scene_decomposition_node)
    graph.add_node("scene_prompt_generation", scene_prompt_generation_node)
    graph.add_node("scene_image_generation", scene_image_generation_node)
    graph.add_node("storyboard_export", storyboard_export_node)

    graph.set_entry_point("story_orchestrator")
    graph.add_conditional_edges(
        "story_orchestrator",
        _should_continue_after_orchestrator,
        {"continue": "character_extraction", "error": END},
    )
    graph.add_edge("character_extraction", "scene_decomposition")
    graph.add_edge("scene_decomposition", "scene_prompt_generation")
    graph.add_edge("scene_prompt_generation", "scene_image_generation")
    graph.add_edge("scene_image_generation", "storyboard_export")
    graph.add_edge("storyboard_export", END)

    return graph


def get_compiled_story_graph():
    graph = build_story_graph()
    return graph.compile(checkpointer=_ckpt.checkpointer)
