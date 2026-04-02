"""Base analyzer interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from infragraph.graph.model import InfraGraphModel


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class Finding:
    """A single finding from an analyzer."""

    analyzer: str
    severity: Severity
    title: str
    description: str
    node_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AnalysisReport:
    """Collection of findings from all analyzers."""

    findings: list[Finding] = field(default_factory=list)

    def add(self, finding: Finding) -> None:
        self.findings.append(finding)

    def by_severity(self, severity: Severity) -> list[Finding]:
        return [f for f in self.findings if f.severity == severity]

    def by_analyzer(self, analyzer: str) -> list[Finding]:
        return [f for f in self.findings if f.analyzer == analyzer]


class BaseAnalyzer(ABC):
    """Abstract base for graph analyzers."""

    @abstractmethod
    def analyze(self, graph: InfraGraphModel) -> list[Finding]:
        """Analyze the graph and return findings."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable analyzer name."""
