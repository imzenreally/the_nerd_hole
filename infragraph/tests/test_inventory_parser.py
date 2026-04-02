"""Tests for the host inventory parser."""

from pathlib import Path

from infragraph.graph.model import EdgeType, NodeType, TrustZone
from infragraph.parsers.inventory import InventoryParser


def test_can_parse():
    parser = InventoryParser()
    assert parser.can_parse(Path("hosts.yaml"))
    assert parser.can_parse(Path("inventory.yml"))
    assert parser.can_parse(Path("hosts.json"))
    assert not parser.can_parse(Path("docker-compose.yaml"))


def test_parse_basic_inventory(tmp_path: Path):
    hosts_file = tmp_path / "hosts.yaml"
    hosts_file.write_text("""
hosts:
  - name: server-01
    ip: 192.168.1.10
    role: docker-host
    os: Ubuntu 24.04
    services:
      - name: ssh
        port: 22
        protocol: tcp
      - name: docker
        port: 2375
        protocol: tcp
""")

    parser = InventoryParser()
    fragment = parser.parse(hosts_file)

    hosts = [n for n in fragment.nodes if n.node_type == NodeType.HOST]
    assert len(hosts) == 1

    host = hosts[0]
    assert host.name == "server-01"
    assert host.metadata["ip"] == "192.168.1.10"
    assert host.labels["role"] == "docker-host"
    assert host.trust_zone == TrustZone.INTERNAL

    services = [n for n in fragment.nodes if n.node_type == NodeType.SERVICE]
    assert len(services) == 2

    runs_on = [e for e in fragment.edges if e.edge_type == EdgeType.RUNS_ON]
    assert len(runs_on) == 2
    assert all(e.target_id == "server-01" for e in runs_on)


def test_parse_json_inventory(tmp_path: Path):
    hosts_file = tmp_path / "hosts.json"
    hosts_file.write_text("""
{
  "hosts": [
    {
      "name": "pi-01",
      "ip": "192.168.1.5",
      "role": "dns",
      "os": "Raspberry Pi OS"
    }
  ]
}
""")

    parser = InventoryParser()
    fragment = parser.parse(hosts_file)

    hosts = [n for n in fragment.nodes if n.node_type == NodeType.HOST]
    assert len(hosts) == 1
    assert hosts[0].name == "pi-01"


def test_host_gets_service_ports(tmp_path: Path):
    hosts_file = tmp_path / "hosts.yaml"
    hosts_file.write_text("""
hosts:
  - name: web-01
    ip: 10.0.0.1
    services:
      - name: nginx
        port: 80
        protocol: http
      - name: ssh
        port: 22
""")

    parser = InventoryParser()
    fragment = parser.parse(hosts_file)

    host = next(n for n in fragment.nodes if n.node_type == NodeType.HOST)
    assert len(host.ports) == 2
