from chronocanvas.llm.cost_tracker import CostTracker


def test_cost_tracker_record():
    tracker = CostTracker()
    tracker.record(
        provider="ollama",
        model="llama3.1:8b",
        input_tokens=100,
        output_tokens=50,
        cost=0.0,
        task_type="extraction",
    )

    assert len(tracker.entries) == 1
    assert tracker.total_tokens == 150
    assert tracker.total_cost == 0.0


def test_cost_tracker_multiple():
    tracker = CostTracker()
    tracker.record("claude", "claude-sonnet", 500, 200, 0.005, "research")
    tracker.record("ollama", "llama3.1:8b", 300, 100, 0.0, "extraction")

    summary = tracker.summary()
    assert summary["num_calls"] == 2
    assert summary["total_cost"] == 0.005
    assert summary["total_tokens"] == 1100
    assert "claude" in summary["by_provider"]
    assert "ollama" in summary["by_provider"]


def test_cost_tracker_empty():
    tracker = CostTracker()
    assert tracker.total_cost == 0.0
    assert tracker.total_tokens == 0
    assert tracker.summary()["num_calls"] == 0
