"""Dependency analyzer — finds orphans, broken references, and dependency chains."""

from __future__ import annotations

from infragraph.analyzers.base import BaseAnalyzer, Finding, Severity
from infragraph.graph.model import EdgeType, InfraGraphModel, NodeType


class DependencyAnalyzer(BaseAnalyzer):
    @property
    def name(self) -> str:
        return "dependencies"

    def analyze(self, graph: InfraGraphModel) -> list[Finding]:
        findings: list[Finding] = []

        all_node_ids = {n.id for n in graph.find_nodes()}

        # Find broken references (edges pointing to non-existent nodes)
        for edge in graph.find_edges():
            if edge.target_id not in all_node_ids:
                findings.append(
                    Finding(
                        analyzer=self.name,
                        severity=Severity.WARNING,
                        title=f"Broken reference: {edge.source_id} -> {edge.target_id}",
                        description=(
                            f"{edge.source_id} references {edge.target_id} "
                            f"({edge.edge_type.value}) but no matching node was found."
                        ),
                        node_ids=[edge.source_id],
                        metadata={"missing_target": edge.target_id, "edge_type": edge.edge_type.value},
                    )
                )

        # Find orphaned services (no incoming or outgoing edges)
        referenced_ids: set[str] = set()
        for edge in graph.find_edges():
            referenced_ids.add(edge.source_id)
            referenced_ids.add(edge.target_id)

        for node in graph.find_nodes():
            if node.id not in referenced_ids:
                # Don't flag hosts or DNS names as orphaned — they're leaf nodes
                if node.node_type in (NodeType.HOST, NodeType.DNS_NAME):
                    continue
                findings.append(
                    Finding(
                        analyzer=self.name,
                        severity=Severity.INFO,
                        title=f"Orphaned service: {node.name}",
                        description=(
                            f"{node.name} ({node.node_type.value}) has no dependencies "
                            f"and nothing depends on it."
                        ),
                        node_ids=[node.id],
                    )
                )

        # Find routes with missing backends
        for edge in graph.find_edges(edge_type=EdgeType.ROUTES_TO):
            target_exists = edge.target_id in all_node_ids
            if not target_exists:
                source_node = next(
                    (n for n in graph.find_nodes() if n.id == edge.source_id), None
                )
                if source_node and source_node.node_type == NodeType.ROUTE:
                    findings.append(
                        Finding(
                            analyzer=self.name,
                            severity=Severity.CRITICAL,
                            title=f"Missing backend: {edge.source_id}",
                            description=(
                                f"Route {edge.source_id} forwards to {edge.target_id} "
                                f"but no matching service was found."
                            ),
                            node_ids=[edge.source_id],
                            metadata={"missing_backend": edge.target_id},
                        )
                    )

        return findings
