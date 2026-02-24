from chronocanvas.agents.state import (
    AgentState,
    CompositingState,
    ExportState,
    ExtractionState,
    FaceState,
    ImageState,
    PromptState,
    ResearchState,
    ValidationState,
)


def test_agent_state_creation():
    state: AgentState = {
        "request_id": "test-123",
        "input_text": "Cleopatra",
        "agent_trace": [],
        "retry_count": 0,
    }
    assert state["request_id"] == "test-123"
    assert state["input_text"] == "Cleopatra"


def test_agent_state_with_all_fields():
    state: AgentState = {
        "request_id": "test-456",
        "input_text": "Napoleon Bonaparte",
        "extraction": ExtractionState(
            figure_name="Napoleon Bonaparte",
            time_period="18th-19th century",
            region="France",
            occupation="Emperor",
            extracted_attributes={"military": True},
        ),
        "research": ResearchState(
            historical_context="French military leader",
            clothing_details="Military uniform",
            physical_description="Short stature",
            art_style_reference="Neoclassical oil painting",
            research_sources=["Wikipedia"],
        ),
        "prompt": PromptState(
            image_prompt="A portrait...",
            negative_prompt="blurry",
            style_modifiers=["oil painting"],
        ),
        "image": ImageState(
            image_path="/output/test.png",
            image_provider="mock",
            generation_params={},
        ),
        "validation": ValidationState(
            validation_results=[],
            validation_score=85.0,
            validation_passed=True,
        ),
        "export": ExportState(
            export_path="/output/export",
            export_format="json+png",
        ),
        "current_agent": "export",
        "error": None,
        "agent_trace": [],
        "retry_count": 0,
        "should_regenerate": False,
    }
    assert state["extraction"]["figure_name"] == "Napoleon Bonaparte"
    assert state["validation"]["validation_passed"] is True


def test_agent_state_face_swap_fields():
    state: AgentState = {
        "request_id": "test-789",
        "input_text": "Caesar",
        "face": FaceState(
            source_face_path="/uploads/faces/abc123.jpg",
        ),
        "compositing": CompositingState(
            swapped_image_path="/output/test-789/swapped.png",
            original_image_path="/output/test-789/original_generated.png",
        ),
        "agent_trace": [],
        "retry_count": 0,
    }
    assert state["face"]["source_face_path"] == "/uploads/faces/abc123.jpg"
    assert state["compositing"]["swapped_image_path"] == "/output/test-789/swapped.png"
    assert state["compositing"]["original_image_path"] == "/output/test-789/original_generated.png"
