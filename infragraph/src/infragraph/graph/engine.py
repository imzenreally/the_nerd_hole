"""Graph engine — merges parser output into a unified graph."""

from __future__ import annotations

from pathlib import Path

from infragraph.graph.model import GraphFragment, InfraGraphModel
from infragraph.parsers.base import BaseParser


class GraphEngine:
    """Orchestrates parsing and graph construction."""

    def __init__(self, parsers: list[BaseParser] | None = None) -> None:
        self._parsers: list[BaseParser] = parsers or []
        self._graph = InfraGraphModel()
        self._fragments: list[GraphFragment] = []

    @property
    def graph(self) -> InfraGraphModel:
        return self._graph

    def register_parser(self, parser: BaseParser) -> None:
        self._parsers.append(parser)

    def ingest_path(self, path: Path) -> list[str]:
        """Scan a path (file or directory) and ingest all parseable files.

        Returns list of files that were successfully parsed.
        """
        files = _collect_files(path)
        parsed: list[str] = []

        for file_path in files:
            for parser in self._parsers:
                if parser.can_parse(file_path):
                    fragment = parser.parse(file_path)
                    fragment.source = f"{parser.source_type}:{file_path}"
                    self._merge_fragment(fragment)
                    parsed.append(str(file_path))
                    break

        return parsed

    def ingest_fragment(self, fragment: GraphFragment) -> None:
        """Directly ingest a pre-built graph fragment."""
        self._merge_fragment(fragment)

    def _merge_fragment(self, fragment: GraphFragment) -> None:
        self._fragments.append(fragment)
        for node in fragment.nodes:
            self._graph.add_node(node)
        for edge in fragment.edges:
            self._graph.add_edge(edge)


def _collect_files(path: Path) -> list[Path]:
    """Recursively collect files from a path."""
    if path.is_file():
        return [path]
    if path.is_dir():
        files: list[Path] = []
        for child in sorted(path.rglob("*")):
            if child.is_file() and not child.name.startswith("."):
                files.append(child)
        return files
    return []
