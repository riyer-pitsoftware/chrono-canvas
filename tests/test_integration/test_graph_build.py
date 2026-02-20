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
        "validation", "export",
    }
    assert expected.issubset(node_names)
