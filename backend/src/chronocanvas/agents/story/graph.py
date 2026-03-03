from langgraph.graph import END, StateGraph

import chronocanvas.agents.checkpointer as _ckpt
from chronocanvas.agents.story.nodes.character_extraction import character_extraction_node
from chronocanvas.agents.story.nodes.image_to_story import image_to_story_node
from chronocanvas.agents.story.nodes.narration_audio import narration_audio_node
from chronocanvas.agents.story.nodes.narration_script import narration_script_node
from chronocanvas.agents.story.nodes.reference_image_analysis import reference_image_analysis_node
from chronocanvas.agents.story.nodes.video_assembly import video_assembly_node
from chronocanvas.agents.story.nodes.scene_decomposition import scene_decomposition_node
from chronocanvas.agents.story.nodes.scene_image_generation import scene_image_generation_node
from chronocanvas.agents.story.nodes.scene_prompt_generation import scene_prompt_generation_node
from chronocanvas.agents.story.nodes.story_orchestrator import story_orchestrator_node
from chronocanvas.agents.story.nodes.storyboard_coherence import storyboard_coherence_node
from chronocanvas.agents.story.nodes.storyboard_export import storyboard_export_node
from chronocanvas.agents.story.state import StoryState
from chronocanvas.config import settings


def _should_continue_after_orchestrator(state: StoryState) -> str:
    if state.get("error"):
        return "error"
    # If an image was uploaded, route through image_to_story first
    if state.get("reference_image_path") and settings.image_to_story_enabled:
        return "image_to_story"
    # If reference images provided, route through analysis first
    if state.get("reference_images") and len(state.get("reference_images", [])) > 0:
        return "ref_analysis"
    return "continue"


def _after_image_to_story(state: StoryState) -> str:
    """After image-to-story, check if there are also reference images to analyze."""
    if state.get("reference_images") and len(state.get("reference_images", [])) > 0:
        return "ref_analysis"
    return "continue"


def _should_regen_after_coherence(state: StoryState) -> str:
    """Route to regen cycle if coherence flagged scenes, else narration or export."""
    if state.get("regen_scenes"):
        return "regen"
    if settings.tts_enabled:
        return "narration"
    return "export"


def build_story_graph() -> StateGraph:
    graph = StateGraph(StoryState)

    graph.add_node("story_orchestrator", story_orchestrator_node)
    graph.add_node("image_to_story", image_to_story_node)
    graph.add_node("reference_image_analysis", reference_image_analysis_node)
    graph.add_node("character_extraction", character_extraction_node)
    graph.add_node("scene_decomposition", scene_decomposition_node)
    graph.add_node("scene_prompt_generation", scene_prompt_generation_node)
    graph.add_node("scene_image_generation", scene_image_generation_node)
    graph.add_node("storyboard_coherence", storyboard_coherence_node)
    graph.add_node("narration_script", narration_script_node)
    graph.add_node("narration_audio", narration_audio_node)
    graph.add_node("video_assembly", video_assembly_node)
    graph.add_node("storyboard_export", storyboard_export_node)

    graph.set_entry_point("story_orchestrator")
    graph.add_conditional_edges(
        "story_orchestrator",
        _should_continue_after_orchestrator,
        {
            "continue": "character_extraction",
            "error": END,
            "image_to_story": "image_to_story",
            "ref_analysis": "reference_image_analysis",
        },
    )
    graph.add_conditional_edges(
        "image_to_story",
        _after_image_to_story,
        {
            "continue": "character_extraction",
            "ref_analysis": "reference_image_analysis",
        },
    )
    graph.add_edge("reference_image_analysis", "character_extraction")
    graph.add_edge("character_extraction", "scene_decomposition")
    graph.add_edge("scene_decomposition", "scene_prompt_generation")
    graph.add_edge("scene_prompt_generation", "scene_image_generation")
    graph.add_edge("scene_image_generation", "storyboard_coherence")
    graph.add_conditional_edges(
        "storyboard_coherence",
        _should_regen_after_coherence,
        {
            "regen": "scene_prompt_generation",
            "narration": "narration_script",
            "export": "storyboard_export",
        },
    )
    graph.add_edge("narration_script", "narration_audio")
    graph.add_edge("narration_audio", "video_assembly")
    graph.add_edge("video_assembly", "storyboard_export")
    graph.add_edge("storyboard_export", END)

    return graph


def get_compiled_story_graph():
    graph = build_story_graph()
    return graph.compile(checkpointer=_ckpt.checkpointer)
