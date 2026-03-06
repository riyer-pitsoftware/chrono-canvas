from typing import TYPE_CHECKING, Any, TypedDict

if TYPE_CHECKING:
    from chronocanvas.runtime_config import RuntimeConfig


class ExtractionState(TypedDict, total=False):
    figure_name: str
    time_period: str
    region: str
    occupation: str
    extracted_attributes: dict[str, Any]
    alternative_names: list[str]
    birth_year: str
    death_year: str
    notable_features: str
    cultural_context: str
    historical_significance: str
    associated_locations: list[str]


class ResearchState(TypedDict, total=False):
    historical_context: str
    clothing_details: str
    physical_description: str
    art_style_reference: str
    citations: list[dict]
    research_cache_hit: bool


class PromptState(TypedDict, total=False):
    image_prompt: str
    negative_prompt: str
    style_modifiers: list[str]


class ImageState(TypedDict, total=False):
    image_path: str
    image_provider: str
    generation_params: dict[str, Any]


class ValidationState(TypedDict, total=False):
    validation_results: list[dict[str, Any]]
    validation_score: float
    validation_passed: bool
    rule_weights: dict[str, float]
    pass_threshold: float


class FaceState(TypedDict, total=False):
    face_search_url: str
    face_search_query: str
    face_search_provider: str
    source_face_path: str


class CompositingState(TypedDict, total=False):
    swapped_image_path: str
    original_image_path: str


class ExportState(TypedDict, total=False):
    export_path: str
    export_format: str


class AgentState(TypedDict, total=False):
    # Input
    request_id: str
    input_text: str

    # Domain namespaces
    extraction: ExtractionState
    research: ResearchState
    prompt: PromptState
    image: ImageState
    validation: ValidationState
    face: FaceState
    compositing: CompositingState
    export: ExportState

    # Audit
    llm_calls: list[dict[str, Any]]

    # Per-request configuration overrides (from UI ConfigHUD)
    runtime_config: "RuntimeConfig | None"

    # Control
    current_agent: str
    error: str | None
    agent_trace: list[dict[str, Any]]
    retry_count: int
    should_regenerate: bool
