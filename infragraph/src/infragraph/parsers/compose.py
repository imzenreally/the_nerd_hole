"""Docker Compose YAML parser."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from infragraph.graph.model import (
    Edge,
    EdgeType,
    GraphFragment,
    Node,
    NodeType,
    Port,
    Protocol,
    TrustZone,
)
from infragraph.parsers.base import BaseParser

_COMPOSE_FILENAMES = {
    "docker-compose.yml",
    "docker-compose.yaml",
    "compose.yml",
    "compose.yaml",
}


class ComposeParser(BaseParser):
    @property
    def source_type(self) -> str:
        return "docker-compose"

    def can_parse(self, path: Path) -> bool:
        return path.name in _COMPOSE_FILENAMES

    def parse(self, path: Path) -> GraphFragment:
        with open(path) as f:
            data = yaml.safe_load(f)

        if not isinstance(data, dict):
            return GraphFragment()

        services: dict[str, Any] = data.get("services", {})
        if not services:
            return GraphFragment()

        fragment = GraphFragment(source=str(path))

        for name, svc_def in services.items():
            if not isinstance(svc_def, dict):
                continue
            node = _build_service_node(name, svc_def)
            fragment.nodes.append(node)

            # depends_on edges
            for dep in _parse_depends_on(svc_def):
                fragment.edges.append(
                    Edge(
                        source_id=name,
                        target_id=dep,
                        edge_type=EdgeType.DEPENDS_ON,
                    )
                )

            # links edges
            for link in svc_def.get("links", []):
                link_target = link.split(":")[0]
                fragment.edges.append(
                    Edge(
                        source_id=name,
                        target_id=link_target,
                        edge_type=EdgeType.LINKS_TO,
                    )
                )

        # Parse networks as metadata
        networks: dict[str, Any] = data.get("networks", {})
        for net_name, net_def in networks.items():
            if isinstance(net_def, dict) and net_def.get("external"):
                fragment.nodes.append(
                    Node(
                        id=f"network:{net_name}",
                        name=net_name,
                        node_type=NodeType.SERVICE,
                        labels={"kind": "network", "external": "true"},
                        source=str(path),
                    )
                )

        return fragment


def _build_service_node(name: str, svc_def: dict[str, Any]) -> Node:
    ports = _parse_ports(svc_def.get("ports", []))
    image = svc_def.get("image", "")

    # Determine trust zone from ports
    trust_zone = TrustZone.INTERNAL
    for port in ports:
        if port.is_public:
            trust_zone = TrustZone.PUBLIC
            break
        if port.is_published:
            trust_zone = TrustZone.LOCALHOST

    labels: dict[str, str] = {}
    raw_labels = svc_def.get("labels", {})
    if isinstance(raw_labels, dict):
        labels = {k: str(v) for k, v in raw_labels.items()}
    elif isinstance(raw_labels, list):
        for item in raw_labels:
            if "=" in str(item):
                k, v = str(item).split("=", 1)
                labels[k] = v

    env_vars: list[str] = []
    raw_env = svc_def.get("environment", [])
    if isinstance(raw_env, dict):
        env_vars = [f"{k}={v}" for k, v in raw_env.items()]
    elif isinstance(raw_env, list):
        env_vars = [str(e) for e in raw_env]

    networks = svc_def.get("networks", [])
    if isinstance(networks, dict):
        networks = list(networks.keys())

    volumes = svc_def.get("volumes", [])

    return Node(
        id=name,
        name=name,
        node_type=NodeType.CONTAINER,
        trust_zone=trust_zone,
        ports=ports,
        labels=labels,
        metadata={
            "image": image,
            "environment": env_vars,
            "networks": networks,
            "volumes": [str(v) for v in volumes],
            "restart": svc_def.get("restart", ""),
        },
        source="docker-compose",
    )


def _parse_ports(raw_ports: list[Any]) -> list[Port]:
    ports: list[Port] = []
    for entry in raw_ports:
        parsed = _parse_single_port(entry)
        if parsed:
            ports.append(parsed)
    return ports


def _parse_single_port(entry: Any) -> Port | None:
    if isinstance(entry, int):
        return Port(host_port=entry, container_port=entry)

    s = str(entry)
    protocol = Protocol.TCP
    if "/" in s:
        s, proto_str = s.rsplit("/", 1)
        if proto_str.lower() == "udp":
            protocol = Protocol.UDP

    host_ip = "0.0.0.0"
    parts = s.split(":")
    if len(parts) == 3:
        host_ip = parts[0]
        host_port = int(parts[1])
        container_port = int(parts[2])
    elif len(parts) == 2:
        host_port = int(parts[0])
        container_port = int(parts[1])
    elif len(parts) == 1:
        return Port(host_port=None, container_port=int(parts[0]), protocol=protocol)
    else:
        return None

    return Port(
        host_port=host_port,
        container_port=container_port,
        protocol=protocol,
        host_ip=host_ip,
    )


def _parse_depends_on(svc_def: dict[str, Any]) -> list[str]:
    deps = svc_def.get("depends_on", [])
    if isinstance(deps, list):
        return [str(d) for d in deps]
    if isinstance(deps, dict):
        return list(deps.keys())
    return []
