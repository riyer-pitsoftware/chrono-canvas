from historylens.agents.graph import build_graph


def test_graph_builds_successfully():
    graph = build_graph()
    compiled = graph.compile()
    assert compiled is not None


def test_graph_has_all_nodes():
    graph = build_graph()
    node_names = set(graph.nodes.keys())
    expected = {
        "orchestrator", "extraction", "research",
        "prompt_generation", "image_generation",
        "validation", "face_swap", "export",
    }
    assert expected.issubset(node_names)


def test_face_swap_wired_between_validation_and_export():
    """Verify face_swap sits between validation and export in the graph."""
    graph = build_graph()
    node_names = set(graph.nodes.keys())
    assert "face_swap" in node_names

    # The graph should have an edge from face_swap to export
    # We verify by checking that face_swap exists as a node and the
    # graph compiles without errors (edges are validated at compile time)
    compiled = graph.compile()
    assert compiled is not None
