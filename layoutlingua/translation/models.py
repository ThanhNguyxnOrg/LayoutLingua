"""Data models for translation jobs, segment statuses, and provider capabilities."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from layoutlingua.processing.formula.models import TextSegment


class JobStatus(str, Enum):
    """Lifecycle statuses for document translation jobs."""

    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    PARTIAL_FAILED = "PARTIAL_FAILED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class SegmentStatus(str, Enum):
    """Per-segment translation state inside a persistent job."""

    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class ProviderCapabilities:
    """Operational parameters and safety constraints of a translation provider."""

    supports_structured_json: bool = False
    requires_data_use_consent: bool = False
    tier: str = "standard"
    policy_version: str = "1.0"
    max_batch_segments: int = 20
    max_batch_chars: int = 4000
    requests_per_minute: float = 60.0


@dataclass(frozen=True, slots=True)
class TranslationJob:
    """An immutable specification for translating a collection of document segments."""

    job_id: str
    document_fingerprint: str
    source_language: str
    target_language: str
    segments: tuple[TextSegment, ...]
    prompt_version: str = "translation-v1"
    glossary_version: str = "v0"
    generation_settings_hash: str = "default"

    def __post_init__(self) -> None:
        if not self.job_id or not self.job_id.strip():
            raise ValueError("job_id must not be empty.")
        if not self.document_fingerprint or not self.document_fingerprint.strip():
            raise ValueError("document_fingerprint must not be empty.")
        if not isinstance(self.segments, tuple):
            object.__setattr__(self, "segments", tuple(self.segments))


@dataclass(frozen=True, slots=True)
class BatchTranslationRequest:
    """Request payload sent to a TranslationProvider for a batch of segments."""

    batch_id: str
    segments: tuple[TextSegment, ...]
    source_language: str
    target_language: str


@dataclass(frozen=True, slots=True)
class BatchTranslationResult:
    """Translation output returned by a TranslationProvider for a batch."""

    translations: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class TranslationJobResult:
    """Observable outcome returned by TranslationService upon job completion or failure."""

    job_id: str
    status: JobStatus
    translated_segments: dict[str, str] = field(default_factory=dict)
    failed_segments: dict[str, str] = field(default_factory=dict)
    cache_hits: int = 0
    provider_calls: int = 0
