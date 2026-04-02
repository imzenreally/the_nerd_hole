"""Typed internal graph model for InfraGraph."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class NodeType(str, Enum):
    HOST = "host"
    SERVICE = "service"
    CONTAINER = "container"
    ROUTE = "route"
    DNS_NAME = "dns_name"
    CERTIFICATE = "certificate"


class TrustZone(str, Enum):
    PUBLIC = "public"
    PROXY = "proxy"
    INTERNAL = "internal"
    LOCALHOST = "localhost"
    UNKNOWN = "unknown"


class EdgeType(str, Enum):
    DEPENDS_ON = "depends_on"
    ROUTES_TO = "routes_to"
    RUNS_ON = "runs_on"
    EXPOSES = "exposes"
    RESOLVES_TO = "resolves_to"
    SECURES = "secures"
    LINKS_TO = "links_to"


class Protocol(str, Enum):
    TCP = "tcp"
    UDP = "udp"
    HTTP = "http"
    HTTPS = "https"


@dataclass
class Port:
    """A port binding."""

    host_port: int | None
    container_port: int
    protocol: Protocol = Protocol.TCP
    host_ip: str = "0.0.0.0"

    @property
    def is_published(self) -> bool:
        return self.host_port is not None

    @property
    def is_public(self) -> bool:
        return self.is_published and self.host_ip in ("0.0.0.0", "::")

    def __str__(self) -> str:
        if self.host_port:
            return f"{self.host_ip}:{self.host_port}->{self.container_port}/{self.protocol.value}"
        return f"{self.container_port}/{self.protocol.value}"


@dataclass
class Node:
    """A node in the infrastructure graph."""

    id: str
    name: str
    node_type: NodeType
    trust_zone: TrustZone = TrustZone.UNKNOWN
    ports: list[Port] = field(default_factory=list)
    labels: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    source: str = ""

    @property
    def key(self) -> tuple[str, str]:
        """Deduplication key: (type, id)."""
        return (self.node_type.value, self.id)


@dataclass
class Edge:
    """A directed edge between two nodes."""

    source_id: str
    target_id: str
    edge_type: EdgeType
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.source_id, self.target_id, self.edge_type.value)


@dataclass
class GraphFragment:
    """A partial graph produced by a single parser.

    The engine merges multiple fragments into the final graph.
    """

    nodes: list[Node] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)
    source: str = ""


@dataclass
class InfraGraphModel:
    """The complete, merged infrastructure graph."""

    nodes: dict[tuple[str, str], Node] = field(default_factory=dict)
    edges: dict[tuple[str, str, str], Edge] = field(default_factory=dict)

    def add_node(self, node: Node) -> None:
        existing = self.nodes.get(node.key)
        if existing:
            _merge_node(existing, node)
        else:
            self.nodes[node.key] = node

    def add_edge(self, edge: Edge) -> None:
        if edge.key not in self.edges:
            self.edges[edge.key] = edge

    def get_node(self, node_type: str, node_id: str) -> Node | None:
        return self.nodes.get((node_type, node_id))

    def find_nodes(self, node_type: NodeType | None = None) -> list[Node]:
        if node_type is None:
            return list(self.nodes.values())
        return [n for n in self.nodes.values() if n.node_type == node_type]

    def find_edges(
        self,
        edge_type: EdgeType | None = None,
        source_id: str | None = None,
        target_id: str | None = None,
    ) -> list[Edge]:
        results = list(self.edges.values())
        if edge_type:
            results = [e for e in results if e.edge_type == edge_type]
        if source_id:
            results = [e for e in results if e.source_id == source_id]
        if target_id:
            results = [e for e in results if e.target_id == target_id]
        return results

    def dependents_of(self, node_id: str) -> list[str]:
        """Return IDs of nodes that depend on the given node."""
        return [
            e.source_id
            for e in self.edges.values()
            if e.target_id == node_id and e.edge_type == EdgeType.DEPENDS_ON
        ]

    def dependencies_of(self, node_id: str) -> list[str]:
        """Return IDs of nodes that the given node depends on."""
        return [
            e.target_id
            for e in self.edges.values()
            if e.source_id == node_id and e.edge_type == EdgeType.DEPENDS_ON
        ]


def _merge_node(existing: Node, incoming: Node) -> None:
    """Merge an incoming node into an existing one."""
    for port in incoming.ports:
        if port not in existing.ports:
            existing.ports.append(port)
    existing.labels.update(incoming.labels)
    existing.metadata.update(incoming.metadata)
    if existing.trust_zone == TrustZone.UNKNOWN and incoming.trust_zone != TrustZone.UNKNOWN:
        existing.trust_zone = incoming.trust_zone
