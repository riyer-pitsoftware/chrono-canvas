from historylens.agents.decisions import (
    should_continue_after_image,
    should_continue_after_validation,
)


def test_continue_after_image_success():
    state = {"error": None}
    assert should_continue_after_image(state) == "validate"


def test_continue_after_image_error():
    state = {"error": "Generation failed"}
    assert should_continue_after_image(state) == "error"


def test_continue_after_validation_export():
    state = {"error": None, "should_regenerate": False}
    assert should_continue_after_validation(state) == "export"


def test_continue_after_validation_regenerate():
    state = {"error": None, "should_regenerate": True}
    assert should_continue_after_validation(state) == "regenerate"


def test_continue_after_validation_error():
    state = {"error": "Validation failed", "should_regenerate": False}
    assert should_continue_after_validation(state) == "error"
