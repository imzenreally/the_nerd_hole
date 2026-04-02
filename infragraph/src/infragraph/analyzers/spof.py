"""Single Point of Failure (SPOF) analyzer."""

from __future__ import annotations

from infragraph.analyzers.base import BaseAnalyzer, Finding, Severity
from infragraph.graph.model import EdgeType, InfraGraphModel, NodeType


class SPOFAnalyzer(BaseAnalyzer):
    @property
    def name(self) -> str:
        return "spof"

    def analyze(self, graph: InfraGraphModel) -> list[Finding]:
        findings: list[Finding] = []

        # Count how many things depend on each node
        dependents_count: dict[str, set[str]] = {}
        for edge in graph.find_edges():
            if edge.edge_type in (EdgeType.DEPENDS_ON, EdgeType.ROUTES_TO, EdgeType.RUNS_ON):
                if edge.target_id not in dependents_count:
                    dependents_count[edge.target_id] = set()
                dependents_count[edge.target_id].add(edge.source_id)

        # Identify nodes with many dependents
        for node_id, dependents in dependents_count.items():
            if len(dependents) < 2:
                continue

            node = next((n for n in graph.find_nodes() if n.id == node_id), None)
            if not node:
                continue

            dependent_names = sorted(dependents)
            findings.append(
                Finding(
                    analyzer=self.name,
                    severity=Severity.WARNING,
                    title=f"Potential SPOF: {node.name}",
                    description=(
                        f"{node.name} ({node.node_type.value}) has {len(dependents)} "
                        f"dependent(s): {', '.join(dependent_names)}. "
                        f"If it goes down, all dependents are affected."
                    ),
                    node_ids=[node_id] + dependent_names,
                    metadata={"dependent_count": len(dependents)},
                )
            )

        # Check for single reverse proxy
        proxies = [
            n for n in graph.find_nodes()
            if n.labels.get("role") == "reverse-proxy"
        ]
        if len(proxies) == 1:
            proxy = proxies[0]
            route_count = len(graph.find_edges(edge_type=EdgeType.ROUTES_TO, source_id=proxy.id))
            if route_count > 0:
                findings.append(
                    Finding(
                        analyzer=self.name,
                        severity=Severity.WARNING,
                        title=f"Single reverse proxy: {proxy.name}",
                        description=(
                            f"{proxy.name} is the only reverse proxy and handles "
                            f"{route_count} route(s). It is a single point of failure "
                            f"for all proxied traffic."
                        ),
                        node_ids=[proxy.id],
                        metadata={"route_count": route_count},
                    )
                )

        # Check for single-host setups
        hosts = graph.find_nodes(NodeType.HOST)
        if len(hosts) == 1:
            host = hosts[0]
            services_on_host = len(graph.find_edges(edge_type=EdgeType.RUNS_ON, target_id=host.id))
            if services_on_host > 0:
                findings.append(
                    Finding(
                        analyzer=self.name,
                        severity=Severity.INFO,
                        title=f"Single host: {host.name}",
                        description=(
                            f"All services run on a single host ({host.name}). "
                            f"Hardware failure would take down everything."
                        ),
                        node_ids=[host.id],
                    )
                )

        return findings
