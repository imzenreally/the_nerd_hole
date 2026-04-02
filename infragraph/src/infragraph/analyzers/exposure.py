"""Exposure analyzer — identifies publicly exposed services and proxy bypasses."""

from __future__ import annotations

from infragraph.analyzers.base import BaseAnalyzer, Finding, Severity
from infragraph.graph.model import EdgeType, InfraGraphModel, NodeType, TrustZone


class ExposureAnalyzer(BaseAnalyzer):
    @property
    def name(self) -> str:
        return "exposure"

    def analyze(self, graph: InfraGraphModel) -> list[Finding]:
        findings: list[Finding] = []

        # Find all publicly exposed services
        for node in graph.find_nodes():
            if node.trust_zone == TrustZone.PUBLIC:
                public_ports = [p for p in node.ports if p.is_public]
                if public_ports:
                    port_list = ", ".join(str(p.host_port) for p in public_ports)
                    findings.append(
                        Finding(
                            analyzer=self.name,
                            severity=Severity.INFO,
                            title=f"Public service: {node.name}",
                            description=f"{node.name} exposes port(s) {port_list} to all interfaces.",
                            node_ids=[node.id],
                            metadata={"ports": [str(p) for p in public_ports]},
                        )
                    )

        # Find containers with published ports that bypass the reverse proxy
        proxy_backends = set()
        for edge in graph.find_edges(edge_type=EdgeType.ROUTES_TO):
            proxy_backends.add(edge.target_id)

        for node in graph.find_nodes(NodeType.CONTAINER):
            public_ports = [p for p in node.ports if p.is_public]
            if public_ports and node.id not in proxy_backends:
                # Check if this is the proxy itself
                if node.labels.get("role") == "reverse-proxy":
                    continue
                is_routed = any(
                    edge.target_id == node.id
                    for edge in graph.find_edges(edge_type=EdgeType.ROUTES_TO)
                )
                if not is_routed:
                    findings.append(
                        Finding(
                            analyzer=self.name,
                            severity=Severity.WARNING,
                            title=f"Proxy bypass: {node.name}",
                            description=(
                                f"{node.name} has published ports but is not behind "
                                f"the reverse proxy. Traffic reaches it directly."
                            ),
                            node_ids=[node.id],
                        )
                    )

        return findings
