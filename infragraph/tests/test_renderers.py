"""Tests for the renderers."""

import json

from infragraph.analyzers.base import AnalysisReport, Finding, Severity
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
from infragraph.renderers.json_export import JSONRenderer
from infragraph.renderers.markdown import MarkdownRenderer
from infragraph.renderers.mermaid import MermaidRenderer


def _sample_graph() -> InfraGraphModel:
    graph = InfraGraphModel()
    frag = GraphFragment(
        nodes=[
            Node(
                id="nginx",
                name="nginx",
                node_type=NodeType.SERVICE,
                trust_zone=TrustZone.PROXY,
                ports=[Port(host_port=443, container_port=443)],
                labels={"role": "reverse-proxy"},
            ),
            Node(
                id="app",
                name="app",
                node_type=NodeType.CONTAINER,
                trust_zone=TrustZone.INTERNAL,
                ports=[Port(host_port=None, container_port=8080)],
                metadata={"image": "myapp:latest"},
            ),
            Node(
                id="db",
                name="db",
                node_type=NodeType.CONTAINER,
                trust_zone=TrustZone.INTERNAL,
                metadata={"image": "postgres:16"},
            ),
        ],
        edges=[
            Edge(source_id="nginx", target_id="app", edge_type=EdgeType.ROUTES_TO),
            Edge(source_id="app", target_id="db", edge_type=EdgeType.DEPENDS_ON),
        ],
    )
    for node in frag.nodes:
        graph.add_node(node)
    for edge in frag.edges:
        graph.add_edge(edge)
    return graph


def _sample_report() -> AnalysisReport:
    report = AnalysisReport()
    report.add(
        Finding(
            analyzer="test",
            severity=Severity.WARNING,
            title="Test warning",
            description="This is a test warning.",
        )
    )
    return report


def test_json_renderer_produces_valid_json():
    graph = _sample_graph()
    report = _sample_report()

    output = JSONRenderer().render(graph, report)
    data = json.loads(output)

    assert "nodes" in data
    assert "edges" in data
    assert "findings" in data
    assert "summary" in data
    assert data["summary"]["total_nodes"] == 3
    assert data["summary"]["total_edges"] == 2


def test_markdown_renderer_has_sections():
    graph = _sample_graph()
    report = _sample_report()

    output = MarkdownRenderer().render(graph, report)

    assert "# InfraGraph Report" in output
    assert "## Summary" in output
    assert "## Services" in output
    assert "## Findings" in output
    assert "Test warning" in output


def test_mermaid_renderer_produces_valid_diagram():
    graph = _sample_graph()
    report = _sample_report()

    output = MermaidRenderer().render(graph, report)

    assert output.startswith("graph TD")
    assert "subgraph" in output
    assert "-->|" in output
    # Check that nodes appear
    assert "nginx" in output
    assert "app" in output
    assert "db" in output


def test_json_renderer_includes_all_node_fields():
    graph = _sample_graph()
    report = AnalysisReport()

    output = JSONRenderer().render(graph, report)
    data = json.loads(output)

    nginx_node = next(n for n in data["nodes"] if n["id"] == "nginx")
    assert nginx_node["type"] == "service"
    assert nginx_node["trust_zone"] == "proxy"
    assert nginx_node["labels"]["role"] == "reverse-proxy"
