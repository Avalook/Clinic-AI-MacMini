from clinicai.graphs.scheduling import build_scheduling_subgraph


def test_build_scheduling_subgraph_compiles():
    """Graph compiles with 4 nodes after T-P9.1-02 (added confirm)."""
    graph = build_scheduling_subgraph()
    assert graph is not None
    node_names = set(graph.get_graph().nodes.keys())
    assert {"ask_date", "ask_time", "find_doctor", "confirm"}.issubset(node_names)
