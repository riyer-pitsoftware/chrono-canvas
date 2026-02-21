from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    # Input
    request_id: str
    input_text: str

    # Extraction
    figure_name: str
    time_period: str
    region: str
    occupation: str
    extracted_attributes: dict[str, Any]

    # Research
    historical_context: str
    clothing_details: str
    physical_description: str
    art_style_reference: str
    research_sources: list[str]

    # Prompt Generation
    image_prompt: str
    negative_prompt: str
    style_modifiers: list[str]

    # Image Generation
    image_path: str
    image_provider: str
    generation_params: dict[str, Any]

    # Validation
    validation_results: list[dict[str, Any]]
    validation_score: float
    validation_passed: bool

    # Face Search
    face_search_url: str
    face_search_query: str
    face_search_provider: str

    # Facial Compositing
    source_face_path: str
    swapped_image_path: str
    original_image_path: str

    # Export
    export_path: str
    export_format: str

    # Audit
    llm_calls: list[dict[str, Any]]

    # Control
    current_agent: str
    error: str | None
    agent_trace: list[dict[str, Any]]
    retry_count: int
    should_regenerate: bool
