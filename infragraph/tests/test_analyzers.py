"""Tests for the analyzers."""

from infragraph.analyzers.dependencies import DependencyAnalyzer
from infragraph.analyzers.exposure import ExposureAnalyzer
from infragraph.analyzers.spof import SPOFAnalyzer
from infragraph.graph.model import (
    Edge,
    EdgeType,
    GraphFragment,
    InfraGraphModel,
    Node,
    NodeType,
    Port,
    TrustZone,
)


def _build_graph(*fragments: GraphFragment) -> InfraGraphModel:
    graph = InfraGraphModel()
    for frag in fragments:
        for node in frag.nodes:
            graph.add_node(node)
        for edge in frag.edges:
            graph.add_edge(edge)
    return graph


def test_exposure_finds_public_services():
    graph = _build_graph(
        GraphFragment(
            nodes=[
                Node(
                    id="web",
                    name="web",
                    node_type=NodeType.CONTAINER,
                    trust_zone=TrustZone.PUBLIC,
                    ports=[Port(host_port=80, container_port=80)],
                ),
            ]
        )
    )

    findings = ExposureAnalyzer().analyze(graph)
    assert any("Public service" in f.title for f in findings)


def test_exposure_finds_proxy_bypass():
    graph = _build_graph(
        GraphFragment(
            nodes=[
                Node(
                    id="app",
                    name="app",
                    node_type=NodeType.CONTAINER,
                    trust_zone=TrustZone.PUBLIC,
                    ports=[Port(host_port=8080, container_port=8080)],
                ),
            ]
        )
    )

    findings = ExposureAnalyzer().analyze(graph)
    assert any("Proxy bypass" in f.title for f in findings)


def test_dependency_finds_broken_references():
    graph = _build_graph(
        GraphFragment(
            nodes=[
                Node(id="app", name="app", node_type=NodeType.CONTAINER),
            ],
            edges=[
                Edge(source_id="app", target_id="nonexistent", edge_type=EdgeType.DEPENDS_ON),
            ],
        )
    )

    findings = DependencyAnalyzer().analyze(graph)
    assert any("Broken reference" in f.title for f in findings)


def test_dependency_finds_orphans():
    graph = _build_graph(
        GraphFragment(
            nodes=[
                Node(id="app", name="app", node_type=NodeType.CONTAINER),
                Node(id="lonely", name="lonely", node_type=NodeType.CONTAINER),
            ],
            edges=[
                Edge(source_id="app", target_id="db", edge_type=EdgeType.DEPENDS_ON),
            ],
        )
    )

    findings = DependencyAnalyzer().analyze(graph)
    assert any("Orphaned service" in f.title and "lonely" in f.title for f in findings)


def test_dependency_finds_missing_backend():
    graph = _build_graph(
        GraphFragment(
            nodes=[
                Node(id="route:/app", name="/app", node_type=NodeType.ROUTE),
            ],
            edges=[
                Edge(source_id="route:/app", target_id="missing-svc", edge_type=EdgeType.ROUTES_TO),
            ],
        )
    )

    findings = DependencyAnalyzer().analyze(graph)
    assert any("Missing backend" in f.title for f in findings)


def test_spof_finds_nodes_with_many_dependents():
    graph = _build_graph(
        GraphFragment(
            nodes=[
                Node(id="db", name="db", node_type=NodeType.CONTAINER),
                Node(id="app1", name="app1", node_type=NodeType.CONTAINER),
                Node(id="app2", name="app2", node_type=NodeType.CONTAINER),
                Node(id="app3", name="app3", node_type=NodeType.CONTAINER),
            ],
            edges=[
                Edge(source_id="app1", target_id="db", edge_type=EdgeType.DEPENDS_ON),
                Edge(source_id="app2", target_id="db", edge_type=EdgeType.DEPENDS_ON),
                Edge(source_id="app3", target_id="db", edge_type=EdgeType.DEPENDS_ON),
            ],
        )
    )

    findings = SPOFAnalyzer().analyze(graph)
    assert any("SPOF" in f.title and "db" in f.title for f in findings)


def test_spof_finds_single_proxy():
    graph = _build_graph(
        GraphFragment(
            nodes=[
                Node(
                    id="nginx",
                    name="nginx",
                    node_type=NodeType.SERVICE,
                    labels={"role": "reverse-proxy"},
                ),
                Node(id="route1", name="route1", node_type=NodeType.ROUTE),
            ],
            edges=[
                Edge(source_id="nginx", target_id="route1", edge_type=EdgeType.ROUTES_TO),
            ],
        )
    )

    findings = SPOFAnalyzer().analyze(graph)
    assert any("Single reverse proxy" in f.title for f in findings)
