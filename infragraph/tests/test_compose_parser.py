"""Tests for the Docker Compose parser."""

from pathlib import Path

from infragraph.graph.model import EdgeType, NodeType, TrustZone
from infragraph.parsers.compose import ComposeParser

FIXTURES = Path(__file__).parent / "fixtures"


def test_can_parse_compose_files():
    parser = ComposeParser()
    assert parser.can_parse(Path("docker-compose.yaml"))
    assert parser.can_parse(Path("compose.yml"))
    assert not parser.can_parse(Path("hosts.yaml"))
    assert not parser.can_parse(Path("random.yaml"))


def test_parse_basic_compose(tmp_path: Path):
    compose = tmp_path / "docker-compose.yaml"
    compose.write_text("""
services:
  web:
    image: nginx:latest
    ports:
      - "80:80"
    depends_on:
      - api
  api:
    image: myapp:latest
    ports:
      - "127.0.0.1:3000:3000"
    depends_on:
      - db
  db:
    image: postgres:16
    volumes:
      - pg_data:/var/lib/postgresql/data
""")

    parser = ComposeParser()
    fragment = parser.parse(compose)

    assert len(fragment.nodes) == 3

    web = next(n for n in fragment.nodes if n.name == "web")
    assert web.node_type == NodeType.CONTAINER
    assert web.trust_zone == TrustZone.PUBLIC
    assert len(web.ports) == 1
    assert web.ports[0].host_port == 80
    assert web.metadata["image"] == "nginx:latest"

    api = next(n for n in fragment.nodes if n.name == "api")
    assert api.trust_zone == TrustZone.LOCALHOST
    assert api.ports[0].host_ip == "127.0.0.1"

    db = next(n for n in fragment.nodes if n.name == "db")
    assert db.trust_zone == TrustZone.INTERNAL
    assert len(db.ports) == 0

    # Check dependency edges
    dep_edges = [e for e in fragment.edges if e.edge_type == EdgeType.DEPENDS_ON]
    assert len(dep_edges) == 2
    assert any(e.source_id == "web" and e.target_id == "api" for e in dep_edges)
    assert any(e.source_id == "api" and e.target_id == "db" for e in dep_edges)


def test_parse_port_formats(tmp_path: Path):
    compose = tmp_path / "docker-compose.yaml"
    compose.write_text("""
services:
  svc:
    image: test
    ports:
      - "8080:80"
      - "127.0.0.1:9090:9090"
      - "1883:1883/udp"
      - 3000
""")

    parser = ComposeParser()
    fragment = parser.parse(compose)
    svc = fragment.nodes[0]

    assert len(svc.ports) == 4
    assert svc.ports[0].host_port == 8080
    assert svc.ports[0].container_port == 80
    assert svc.ports[1].host_ip == "127.0.0.1"
    assert svc.ports[2].protocol.value == "udp"
    assert svc.ports[3].host_port == 3000  # bare int


def test_parse_depends_on_dict(tmp_path: Path):
    compose = tmp_path / "docker-compose.yaml"
    compose.write_text("""
services:
  web:
    image: nginx
    depends_on:
      api:
        condition: service_healthy
      cache:
        condition: service_started
  api:
    image: myapp
  cache:
    image: redis
""")

    parser = ComposeParser()
    fragment = parser.parse(compose)

    dep_edges = [e for e in fragment.edges if e.edge_type == EdgeType.DEPENDS_ON]
    targets = {e.target_id for e in dep_edges if e.source_id == "web"}
    assert targets == {"api", "cache"}


def test_parse_labels_as_list(tmp_path: Path):
    compose = tmp_path / "docker-compose.yaml"
    compose.write_text("""
services:
  web:
    image: nginx
    labels:
      - "role=reverse-proxy"
      - "env=prod"
""")

    parser = ComposeParser()
    fragment = parser.parse(compose)
    web = fragment.nodes[0]
    assert web.labels == {"role": "reverse-proxy", "env": "prod"}


def test_parse_homelab_fixture():
    """Parse the full homelab example fixture."""
    fixture = Path(__file__).parent.parent / "examples" / "homelab" / "docker-compose.yaml"
    if not fixture.exists():
        return

    parser = ComposeParser()
    fragment = parser.parse(fixture)

    names = {n.name for n in fragment.nodes}
    assert "nginx" in names
    assert "jellyfin" in names
    assert "postgres" in names
    assert "grafana" in names

    # nginx should be public (ports 80, 443 on 0.0.0.0)
    nginx = next(n for n in fragment.nodes if n.name == "nginx")
    assert nginx.trust_zone == TrustZone.PUBLIC
