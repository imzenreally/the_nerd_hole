"""Tests for the Nginx proxy parser."""

from pathlib import Path

from infragraph.graph.model import EdgeType, NodeType, TrustZone
from infragraph.parsers.nginx import NginxParser


def test_can_parse():
    parser = NginxParser()
    assert parser.can_parse(Path("nginx-proxies.yaml"))
    assert parser.can_parse(Path("proxies.yml"))
    assert not parser.can_parse(Path("docker-compose.yaml"))


def test_parse_basic_proxy(tmp_path: Path):
    config = tmp_path / "nginx-proxies.yaml"
    config.write_text("""
proxies:
  - server_name: app.example.com
    listen: 443
    ssl: true
    locations:
      - path: /
        proxy_pass: http://app:8080
      - path: /api
        proxy_pass: http://api:3000
""")

    parser = NginxParser()
    fragment = parser.parse(config)

    # Should have: nginx node, dns node, 2 route nodes
    node_types = {n.node_type for n in fragment.nodes}
    assert NodeType.SERVICE in node_types  # nginx
    assert NodeType.DNS_NAME in node_types
    assert NodeType.ROUTE in node_types

    nginx = next(n for n in fragment.nodes if n.id == "nginx")
    assert nginx.trust_zone == TrustZone.PROXY
    assert nginx.labels["role"] == "reverse-proxy"

    dns = next(n for n in fragment.nodes if n.node_type == NodeType.DNS_NAME)
    assert dns.name == "app.example.com"
    assert dns.trust_zone == TrustZone.PUBLIC

    routes = [n for n in fragment.nodes if n.node_type == NodeType.ROUTE]
    assert len(routes) == 2

    root_route = next(r for r in routes if r.metadata["path"] == "/")
    assert root_route.metadata["backend_host"] == "app"
    assert root_route.metadata["backend_port"] == 8080

    api_route = next(r for r in routes if r.metadata["path"] == "/api")
    assert api_route.metadata["backend_host"] == "api"
    assert api_route.metadata["backend_port"] == 3000


def test_routes_to_edges(tmp_path: Path):
    config = tmp_path / "proxies.yaml"
    config.write_text("""
proxies:
  - server_name: test.local
    listen: 80
    locations:
      - path: /
        proxy_pass: http://backend:5000
""")

    parser = NginxParser()
    fragment = parser.parse(config)

    route_edges = [e for e in fragment.edges if e.edge_type == EdgeType.ROUTES_TO]
    # nginx -> route, route -> backend
    assert len(route_edges) == 2
    assert any(e.source_id == "nginx" for e in route_edges)
    assert any(e.target_id == "backend" for e in route_edges)


def test_dns_resolves_to_nginx(tmp_path: Path):
    config = tmp_path / "nginx-proxies.yaml"
    config.write_text("""
proxies:
  - server_name: mysite.com
    listen: 443
    ssl: true
    locations:
      - path: /
        proxy_pass: http://web:3000
""")

    parser = NginxParser()
    fragment = parser.parse(config)

    resolves = [e for e in fragment.edges if e.edge_type == EdgeType.RESOLVES_TO]
    assert len(resolves) == 1
    assert resolves[0].source_id == "dns:mysite.com"
    assert resolves[0].target_id == "nginx"
