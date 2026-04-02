"""Tests for the graph engine."""

from pathlib import Path

from infragraph.graph.engine import GraphEngine
from infragraph.graph.model import (
    Edge,
    EdgeType,
    GraphFragment,
    Node,
    NodeType,
    TrustZone,
)
from infragraph.parsers.compose import ComposeParser
from infragraph.parsers.nginx import NginxParser


def test_merge_fragments():
    engine = GraphEngine()

    frag1 = GraphFragment(
        nodes=[
            Node(id="web", name="web", node_type=NodeType.CONTAINER, trust_zone=TrustZone.PUBLIC),
            Node(id="api", name="api", node_type=NodeType.CONTAINER, trust_zone=TrustZone.INTERNAL),
        ],
        edges=[Edge(source_id="web", target_id="api", edge_type=EdgeType.DEPENDS_ON)],
    )

    frag2 = GraphFragment(
        nodes=[
            Node(id="api", name="api", node_type=NodeType.CONTAINER, trust_zone=TrustZone.INTERNAL),
            Node(id="db", name="db", node_type=NodeType.CONTAINER, trust_zone=TrustZone.INTERNAL),
        ],
        edges=[Edge(source_id="api", target_id="db", edge_type=EdgeType.DEPENDS_ON)],
    )

    engine.ingest_fragment(frag1)
    engine.ingest_fragment(frag2)

    graph = engine.graph
    assert len(graph.nodes) == 3  # deduped api
    assert len(graph.edges) == 2


def test_ingest_directory(tmp_path: Path):
    compose = tmp_path / "docker-compose.yaml"
    compose.write_text("""
services:
  app:
    image: myapp
    ports:
      - "8080:8080"
""")

    proxies = tmp_path / "nginx-proxies.yaml"
    proxies.write_text("""
proxies:
  - server_name: app.local
    listen: 443
    ssl: true
    locations:
      - path: /
        proxy_pass: http://app:8080
""")

    engine = GraphEngine(parsers=[ComposeParser(), NginxParser()])
    parsed = engine.ingest_path(tmp_path)

    assert len(parsed) == 2

    graph = engine.graph
    # Should have nodes from both parsers
    node_names = {n.name for n in graph.find_nodes()}
    assert "app" in node_names
    assert "nginx" in node_names
    assert "app.local" in node_names  # DNS name


def test_node_dedup_merges_metadata():
    engine = GraphEngine()

    frag1 = GraphFragment(
        nodes=[
            Node(
                id="svc",
                name="svc",
                node_type=NodeType.CONTAINER,
                trust_zone=TrustZone.UNKNOWN,
                labels={"env": "prod"},
            )
        ]
    )

    frag2 = GraphFragment(
        nodes=[
            Node(
                id="svc",
                name="svc",
                node_type=NodeType.CONTAINER,
                trust_zone=TrustZone.INTERNAL,
                labels={"team": "infra"},
            )
        ]
    )

    engine.ingest_fragment(frag1)
    engine.ingest_fragment(frag2)

    node = engine.graph.get_node("container", "svc")
    assert node is not None
    assert node.trust_zone == TrustZone.INTERNAL  # upgraded from unknown
    assert node.labels == {"env": "prod", "team": "infra"}  # merged
