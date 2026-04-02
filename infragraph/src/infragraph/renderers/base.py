"""Base renderer interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from infragraph.analyzers.base import AnalysisReport
from infragraph.graph.model import InfraGraphModel


class BaseRenderer(ABC):
    """Abstract base for output renderers."""

    @abstractmethod
    def render(self, graph: InfraGraphModel, report: AnalysisReport) -> str:
        """Render the graph and analysis report to a string."""

    @property
    @abstractmethod
    def format_name(self) -> str:
        """The output format name (e.g., 'json', 'markdown', 'mermaid')."""
