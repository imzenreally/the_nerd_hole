"""Markdown report renderer."""

from __future__ import annotations

from infragraph.analyzers.base import AnalysisReport, Severity
from infragraph.graph.model import (
    EdgeType,
    InfraGraphModel,
    NodeType,
    TrustZone,
)
from infragraph.renderers.base import BaseRenderer

_SEVERITY_ICONS = {
    Severity.CRITICAL: "[!!]",
    Severity.WARNING: "[!]",
    Severity.INFO: "[i]",
}

_ZONE_LABELS = {
    TrustZone.PUBLIC: "Public (internet-facing)",
    TrustZone.PROXY: "Behind reverse proxy",
    TrustZone.INTERNAL: "Internal (LAN only)",
    TrustZone.LOCALHOST: "Localhost only",
    TrustZone.UNKNOWN: "Unknown",
}


class MarkdownRenderer(BaseRenderer):
    @property
    def format_name(self) -> str:
        return "markdown"

    def render(self, graph: InfraGraphModel, report: AnalysisReport) -> str:
        sections: list[str] = []
        sections.append("# InfraGraph Report\n")
        sections.append(_render_summary(graph, report))
        sections.append(_render_services(graph))
        sections.append(_render_hosts(graph))
        sections.append(_render_routes(graph))
        sections.append(_render_exposure(graph))
        sections.append(_render_dependencies(graph))
        sections.append(_render_findings(report))
        return "\n".join(sections)


def _render_summary(graph: InfraGraphModel, report: AnalysisReport) -> str:
    containers = graph.find_nodes(NodeType.CONTAINER)
    services = graph.find_nodes(NodeType.SERVICE)
    hosts = graph.find_nodes(NodeType.HOST)
    routes = graph.find_nodes(NodeType.ROUTE)
    dns_names = graph.find_nodes(NodeType.DNS_NAME)

    critical = len(report.by_severity(Severity.CRITICAL))
    warnings = len(report.by_severity(Severity.WARNING))

    lines = [
        "## Summary\n",
        f"| Metric | Count |",
        f"|--------|-------|",
        f"| Containers | {len(containers)} |",
        f"| Services | {len(services)} |",
        f"| Hosts | {len(hosts)} |",
        f"| Routes | {len(routes)} |",
        f"| DNS Names | {len(dns_names)} |",
        f"| Critical findings | {critical} |",
        f"| Warnings | {warnings} |",
        "",
    ]
    return "\n".join(lines)


def _render_services(graph: InfraGraphModel) -> str:
    containers = graph.find_nodes(NodeType.CONTAINER)
    services = graph.find_nodes(NodeType.SERVICE)
    all_svc = containers + services

    if not all_svc:
        return ""

    lines = ["## Services\n"]
    lines.append("| Name | Type | Trust Zone | Ports | Image |")
    lines.append("|------|------|------------|-------|-------|")

    for node in sorted(all_svc, key=lambda n: n.name):
        ports = ", ".join(str(p) for p in node.ports) if node.ports else "-"
        image = node.metadata.get("image", "-")
        zone = _ZONE_LABELS.get(node.trust_zone, node.trust_zone.value)
        lines.append(f"| {node.name} | {node.node_type.value} | {zone} | {ports} | {image} |")

    lines.append("")
    return "\n".join(lines)


def _render_hosts(graph: InfraGraphModel) -> str:
    hosts = graph.find_nodes(NodeType.HOST)
    if not hosts:
        return ""

    lines = ["## Hosts\n"]
    lines.append("| Name | IP | OS | Role | Ports |")
    lines.append("|------|----|----|------|-------|")

    for host in sorted(hosts, key=lambda n: n.name):
        ip = host.metadata.get("ip", "-")
        os_name = host.metadata.get("os", "-")
        role = host.labels.get("role", "-")
        ports = ", ".join(str(p) for p in host.ports) if host.ports else "-"
        lines.append(f"| {host.name} | {ip} | {os_name} | {role} | {ports} |")

    lines.append("")
    return "\n".join(lines)


def _render_routes(graph: InfraGraphModel) -> str:
    routes = graph.find_nodes(NodeType.ROUTE)
    if not routes:
        return ""

    lines = ["## Routes\n"]
    lines.append("| Domain/Path | Backend | Port |")
    lines.append("|-------------|---------|------|")

    for route in sorted(routes, key=lambda n: n.name):
        backend = route.metadata.get("backend_host", "-")
        port = route.metadata.get("backend_port", "-")
        lines.append(f"| {route.name} | {backend} | {port} |")

    lines.append("")
    return "\n".join(lines)


def _render_exposure(graph: InfraGraphModel) -> str:
    lines = ["## Exposure Summary\n"]

    zones: dict[TrustZone, list[str]] = {}
    for node in graph.find_nodes():
        zone = node.trust_zone
        if zone not in zones:
            zones[zone] = []
        zones[zone].append(node.name)

    for zone in [TrustZone.PUBLIC, TrustZone.PROXY, TrustZone.INTERNAL, TrustZone.LOCALHOST, TrustZone.UNKNOWN]:
        if zone in zones:
            label = _ZONE_LABELS[zone]
            names = ", ".join(sorted(zones[zone]))
            lines.append(f"**{label}:** {names}\n")

    return "\n".join(lines)


def _render_dependencies(graph: InfraGraphModel) -> str:
    deps = graph.find_edges(edge_type=EdgeType.DEPENDS_ON)
    if not deps:
        return ""

    lines = ["## Dependencies\n"]
    for edge in sorted(deps, key=lambda e: e.source_id):
        lines.append(f"- {edge.source_id} -> {edge.target_id}")
    lines.append("")
    return "\n".join(lines)


def _render_findings(report: AnalysisReport) -> str:
    if not report.findings:
        return "## Findings\n\nNo issues found.\n"

    lines = ["## Findings\n"]

    for severity in [Severity.CRITICAL, Severity.WARNING, Severity.INFO]:
        findings = report.by_severity(severity)
        if not findings:
            continue
        icon = _SEVERITY_ICONS[severity]
        for f in findings:
            lines.append(f"- {icon} **{f.title}**: {f.description}")

    lines.append("")
    return "\n".join(lines)
