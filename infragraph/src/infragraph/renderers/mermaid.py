"""Mermaid diagram renderer."""

from __future__ import annotations

import re

from infragraph.analyzers.base import AnalysisReport
from infragraph.graph.model import (
    EdgeType,
    InfraGraphModel,
    NodeType,
    TrustZone,
)
from infragraph.renderers.base import BaseRenderer

_NODE_SHAPES = {
    NodeType.HOST: ("[[", "]]"),        # stadium
    NodeType.CONTAINER: ("[", "]"),      # rectangle
    NodeType.SERVICE: ("([", "])"),      # rounded
    NodeType.ROUTE: ("{", "}"),          # rhombus
    NodeType.DNS_NAME: ("((", "))"),     # circle
    NodeType.CERTIFICATE: (">", "]"),    # flag
}

_EDGE_LABELS = {
    EdgeType.DEPENDS_ON: "depends on",
    EdgeType.ROUTES_TO: "routes to",
    EdgeType.RUNS_ON: "runs on",
    EdgeType.EXPOSES: "exposes",
    EdgeType.RESOLVES_TO: "resolves to",
    EdgeType.SECURES: "secures",
    EdgeType.LINKS_TO: "links to",
}

_ZONE_ORDER = [TrustZone.PUBLIC, TrustZone.PROXY, TrustZone.INTERNAL, TrustZone.LOCALHOST, TrustZone.UNKNOWN]


class MermaidRenderer(BaseRenderer):
    @property
    def format_name(self) -> str:
        return "mermaid"

    def render(self, graph: InfraGraphModel, report: AnalysisReport) -> str:
        lines: list[str] = ["graph TD"]

        # Group nodes by trust zone into subgraphs
        zones: dict[TrustZone, list[str]] = {}
        for node in graph.find_nodes():
            zone = node.trust_zone
            if zone not in zones:
                zones[zone] = []

            safe_id = _safe_id(node.id)
            left, right = _NODE_SHAPES.get(node.node_type, ("[", "]"))
            label = _safe_label(node.name)

            # Add port info for containers/services
            port_info = ""
            if node.ports:
                port_strs = []
                for p in node.ports[:3]:  # limit to avoid clutter
                    if p.host_port:
                        port_strs.append(f":{p.host_port}")
                if port_strs:
                    port_info = f" {','.join(port_strs)}"

            zones[zone].append(f"        {safe_id}{left}\"{label}{port_info}\"{right}")

        for zone in _ZONE_ORDER:
            if zone not in zones:
                continue
            zone_label = zone.value.replace("_", " ").title()
            lines.append(f"    subgraph {zone_label}")
            for node_line in zones[zone]:
                lines.append(node_line)
            lines.append("    end")

        # Render edges
        for edge in graph.edges.values():
            src = _safe_id(edge.source_id)
            tgt = _safe_id(edge.target_id)
            label = _EDGE_LABELS.get(edge.edge_type, edge.edge_type.value)
            lines.append(f"    {src} -->|{label}| {tgt}")

        # Style trust zones
        lines.append("")
        lines.append("    style Public fill:#ff6b6b,stroke:#c92a2a,color:#fff")
        lines.append("    style Proxy fill:#ffd43b,stroke:#f59f00,color:#000")
        lines.append("    style Internal fill:#69db7c,stroke:#2b8a3e,color:#000")
        lines.append("    style Localhost fill:#74c0fc,stroke:#1c7ed6,color:#000")

        return "\n".join(lines)


def _safe_id(node_id: str) -> str:
    """Convert a node ID to a Mermaid-safe identifier."""
    return re.sub(r"[^a-zA-Z0-9_]", "_", node_id)


def _safe_label(label: str) -> str:
    """Escape quotes in labels."""
    return label.replace('"', "'")
