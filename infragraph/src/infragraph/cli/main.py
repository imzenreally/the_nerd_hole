"""InfraGraph CLI — map your homelab infrastructure."""

from __future__ import annotations

import sys
from pathlib import Path

import click
from rich.console import Console

from infragraph.analyzers.base import AnalysisReport
from infragraph.analyzers.dependencies import DependencyAnalyzer
from infragraph.analyzers.exposure import ExposureAnalyzer
from infragraph.analyzers.spof import SPOFAnalyzer
from infragraph.graph.engine import GraphEngine
from infragraph.parsers.compose import ComposeParser
from infragraph.parsers.inventory import InventoryParser
from infragraph.parsers.nginx import NginxParser
from infragraph.renderers.json_export import JSONRenderer
from infragraph.renderers.markdown import MarkdownRenderer
from infragraph.renderers.mermaid import MermaidRenderer

console = Console(stderr=True)

RENDERERS = {
    "json": JSONRenderer,
    "markdown": MarkdownRenderer,
    "mermaid": MermaidRenderer,
}

ANALYZERS = [
    ExposureAnalyzer(),
    DependencyAnalyzer(),
    SPOFAnalyzer(),
]


def _build_engine() -> GraphEngine:
    return GraphEngine(parsers=[ComposeParser(), NginxParser(), InventoryParser()])


def _run_analysis(engine: GraphEngine) -> AnalysisReport:
    report = AnalysisReport()
    for analyzer in ANALYZERS:
        findings = analyzer.analyze(engine.graph)
        for finding in findings:
            report.add(finding)
    return report


@click.group()
@click.version_option(package_name="infragraph")
def cli() -> None:
    """InfraGraph — map your homelab infrastructure from config files."""


@cli.command()
@click.argument("path", type=click.Path(exists=True))
def scan(path: str) -> None:
    """Scan a path for infrastructure config files and show what was found."""
    engine = _build_engine()
    target = Path(path)
    parsed = engine.ingest_path(target)

    if not parsed:
        console.print("[yellow]No parseable config files found.[/yellow]")
        sys.exit(1)

    console.print(f"[green]Scanned {len(parsed)} file(s):[/green]")
    for f in parsed:
        console.print(f"  - {f}")

    graph = engine.graph
    console.print(f"\n[bold]Graph:[/bold] {len(graph.nodes)} nodes, {len(graph.edges)} edges")


@cli.command()
@click.argument("path", type=click.Path(exists=True))
@click.option("--format", "-f", "fmt", type=click.Choice(["markdown", "json"]), default="markdown")
@click.option("--output", "-o", "output_file", type=click.Path(), default=None)
def report(path: str, fmt: str, output_file: str | None) -> None:
    """Generate an infrastructure report."""
    engine = _build_engine()
    target = Path(path)
    parsed = engine.ingest_path(target)

    if not parsed:
        console.print("[yellow]No parseable config files found.[/yellow]")
        sys.exit(1)

    console.print(f"[dim]Parsed {len(parsed)} file(s), running analysis...[/dim]")
    analysis = _run_analysis(engine)

    renderer = RENDERERS[fmt]()
    output = renderer.render(engine.graph, analysis)

    if output_file:
        Path(output_file).write_text(output)
        console.print(f"[green]Report written to {output_file}[/green]")
    else:
        click.echo(output)


@cli.command()
@click.argument("path", type=click.Path(exists=True))
@click.option("--format", "-f", "fmt", type=click.Choice(["mermaid", "json"]), default="mermaid")
@click.option("--output", "-o", "output_file", type=click.Path(), default=None)
def render(path: str, fmt: str, output_file: str | None) -> None:
    """Render the infrastructure graph as a diagram."""
    engine = _build_engine()
    target = Path(path)
    parsed = engine.ingest_path(target)

    if not parsed:
        console.print("[yellow]No parseable config files found.[/yellow]")
        sys.exit(1)

    console.print(f"[dim]Parsed {len(parsed)} file(s), rendering...[/dim]")
    analysis = _run_analysis(engine)

    renderer = RENDERERS[fmt]()
    output = renderer.render(engine.graph, analysis)

    if output_file:
        Path(output_file).write_text(output)
        console.print(f"[green]Diagram written to {output_file}[/green]")
    else:
        click.echo(output)


@cli.command(name="export")
@click.argument("path", type=click.Path(exists=True))
@click.option("--format", "-f", "fmt", type=click.Choice(["json"]), default="json")
@click.option("--output", "-o", "output_file", type=click.Path(), default=None)
def export_cmd(path: str, fmt: str, output_file: str | None) -> None:
    """Export the raw infrastructure graph as JSON."""
    engine = _build_engine()
    target = Path(path)
    parsed = engine.ingest_path(target)

    if not parsed:
        console.print("[yellow]No parseable config files found.[/yellow]")
        sys.exit(1)

    analysis = _run_analysis(engine)
    renderer = RENDERERS[fmt]()
    output = renderer.render(engine.graph, analysis)

    if output_file:
        Path(output_file).write_text(output)
        console.print(f"[green]Export written to {output_file}[/green]")
    else:
        click.echo(output)


if __name__ == "__main__":
    cli()
