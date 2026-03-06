from typing import TYPE_CHECKING, Any, TypedDict

if TYPE_CHECKING:
    from chronocanvas.runtime_config import RuntimeConfig


class StoryPanel(TypedDict, total=False):
    scene_index: int
    description: str
    characters: list[str]
    mood: str
    setting: str
    image_prompt: str
    negative_prompt: str
    image_path: str
    provider: str
    width: int
    height: int
    status: str  # "pending" | "generating" | "completed" | "failed"
    error: str
    # Coherence (populated by storyboard_coherence node)
    coherence_score: float | None
    coherence_issues: list[str]
    coherence_suggestion: str
    # Narration (populated by narration_script / narration_audio nodes)
    narration_text: str
    narration_audio_path: str


class StoryState(TypedDict, total=False):
    # Input
    request_id: str
    input_text: str

    # Optional image input (image-to-story, reference images)
    reference_image_path: str  # uploaded image for image-to-story
    reference_image_mime: str
    story_concept: dict[str, Any]  # Gemini-extracted concept from image
    reference_images: list[dict[str, Any]]  # style/location/character refs
    reference_analysis: list[dict[str, Any]]  # Gemini analysis of refs

    # Extraction
    characters: list[dict[str, Any]]

    # Scene decomposition
    scenes: list[dict[str, Any]]

    # Image generation
    panels: list[StoryPanel]
    total_scenes: int
    completed_scenes: int

    # Audit
    agent_trace: list[dict[str, Any]]
    llm_calls: list[dict[str, Any]]

    # Coherence regen
    regen_scenes: list[int]  # scene indices to regenerate
    coherence_retry_count: int  # caps regen cycles (max 1)

    # Narration audio
    narration_audio_paths: list[str]

    # Per-request configuration overrides (from UI ConfigHUD)
    runtime_config: "RuntimeConfig | None"

    # Control
    current_agent: str
    error: str | None
