"""Base parser interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from infragraph.graph.model import GraphFragment


class BaseParser(ABC):
    """Abstract base for all config source parsers."""

    @abstractmethod
    def can_parse(self, path: Path) -> bool:
        """Return True if this parser can handle the given file."""

    @abstractmethod
    def parse(self, path: Path) -> GraphFragment:
        """Parse a config file and return a graph fragment."""

    @property
    @abstractmethod
    def source_type(self) -> str:
        """Human-readable name for this source type."""
