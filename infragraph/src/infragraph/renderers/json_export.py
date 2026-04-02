"""JSON graph export renderer."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from infragraph.analyzers.base import AnalysisReport
from infragraph.graph.model import InfraGraphModel
from infragraph.renderers.base import BaseRenderer


class JSONRenderer(BaseRenderer):
    @property
    def format_name(self) -> str:
        return "json"

    def render(self, graph: InfraGraphModel, report: AnalysisReport) -> str:
        output: dict[str, Any] = {
            "nodes": [_serialize_node(n) for n in graph.find_nodes()],
            "edges": [_serialize_edge(e) for e in graph.edges.values()],
            "findings": [asdict(f) for f in report.findings],
            "summary": {
                "total_nodes": len(graph.nodes),
                "total_edges": len(graph.edges),
                "total_findings": len(report.findings),
            },
        }
        return json.dumps(output, indent=2, default=str)


def _serialize_node(node: Any) -> dict[str, Any]:
    return {
        "id": node.id,
        "name": node.name,
        "type": node.node_type.value,
        "trust_zone": node.trust_zone.value,
        "ports": [str(p) for p in node.ports],
        "labels": node.labels,
        "metadata": node.metadata,
        "source": node.source,
    }


def _serialize_edge(edge: Any) -> dict[str, Any]:
    return {
        "source": edge.source_id,
        "target": edge.target_id,
        "type": edge.edge_type.value,
        "metadata": edge.metadata,
    }
