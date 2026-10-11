"""Base interface for text and encoding normalizers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class NormalizationResult:
    """Outcome of a text normalization operation."""

    text: str
    applied: bool
    encoding_detected: str | None = None
    warnings: list[str] = field(default_factory=list)


class BaseTextNormalizer(ABC):
    """Abstract base class for all text encoding normalizers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier of the normalizer."""

    @abstractmethod
    def should_apply(
        self,
        text: str,
        font_name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Determine whether this normalizer should process the given text span."""

    @abstractmethod
    def normalize(
        self,
        text: str,
        font_name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> NormalizationResult:
        """Transform text into canonical Unicode, recording detection and warnings."""
