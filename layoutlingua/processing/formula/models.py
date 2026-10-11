"""Data models for formula token isolation and structured text segmentation."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class FormulaToken:
    """An isolated mathematical formula or technical invariant token."""

    token_id: int
    placeholder: str  # e.g., "<b0></b0>"
    raw_content: str  # Original math expression or formula text
    bbox: tuple[float, float, float, float] | None = None
    font_name: str | None = None


@dataclass(slots=True)
class TextSegment:
    """A translatable text unit preserving structured formula tokens."""

    segment_id: str
    raw_text: str
    masked_text: str
    tokens: list[FormulaToken] = field(default_factory=list)
    span_ids: list[str] = field(default_factory=list)


@dataclass(slots=True)
class TokenVerificationResult:
    """Result of validating formula placeholder preservation in translated text."""

    is_valid: bool
    reason: str | None = None
    missing_tokens: list[str] = field(default_factory=list)
    duplicate_tokens: list[str] = field(default_factory=list)
    out_of_order: bool = False
    alien_tokens: list[str] = field(default_factory=list)
