from historylens.agents.state import AgentState


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
        "figure_name": "Napoleon Bonaparte",
        "time_period": "18th-19th century",
        "region": "France",
        "occupation": "Emperor",
        "extracted_attributes": {"military": True},
        "historical_context": "French military leader",
        "clothing_details": "Military uniform",
        "physical_description": "Short stature",
        "art_style_reference": "Neoclassical oil painting",
        "research_sources": ["Wikipedia"],
        "image_prompt": "A portrait...",
        "negative_prompt": "blurry",
        "style_modifiers": ["oil painting"],
        "image_path": "/output/test.png",
        "image_provider": "mock",
        "generation_params": {},
        "validation_results": [],
        "validation_score": 85.0,
        "validation_passed": True,
        "export_path": "/output/export",
        "export_format": "json+png",
        "current_agent": "export",
        "error": None,
        "agent_trace": [],
        "retry_count": 0,
        "should_regenerate": False,
    }
    assert state["figure_name"] == "Napoleon Bonaparte"
    assert state["validation_passed"] is True
