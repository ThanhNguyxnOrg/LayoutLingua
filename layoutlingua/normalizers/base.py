"""Abstract base class for text and font encoding normalizers."""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaseTextNormalizer(ABC):
    """Interface for text encoding and font CMap normalizers."""

    @abstractmethod
    def should_apply(self, text: str, font_name: str | None = None) -> bool:
        """Check whether this normalizer is applicable to the text or font."""

    @abstractmethod
    def normalize(self, text: str) -> str:
        """Normalize text into canonical Unicode UTF-8 NFC representation."""
