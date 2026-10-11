"""Translation package for LayoutLingua with deep resilience, caching, and provider interfaces."""

from layoutlingua.translation.errors import (
    AuthenticationError,
    JobCancelledError,
    JobConflictError,
    JobNotFoundError,
    PrivacyConsentRequiredError,
    ProviderUnavailableError,
    QuotaExceededError,
    RateLimitError,
    TokenIntegrityError,
    TranslationError,
)
from layoutlingua.translation.mock import MockTranslationProvider
from layoutlingua.translation.models import (
    BatchTranslationRequest,
    BatchTranslationResult,
    JobStatus,
    ProviderCapabilities,
    SegmentStatus,
    TranslationJob,
    TranslationJobResult,
)
from layoutlingua.translation.argos import (
    ArgosModelInfo,
    ArgosModelManager,
    ArgosTranslationProvider,
    TranslationRoute,
)
from layoutlingua.translation.provider import BaseTranslationProvider
from layoutlingua.translation.service import TranslationService

__all__ = [
    "ArgosModelInfo",
    "ArgosModelManager",
    "ArgosTranslationProvider",
    "AuthenticationError",
    "BaseTranslationProvider",
    "BatchTranslationRequest",
    "BatchTranslationResult",
    "JobCancelledError",
    "JobConflictError",
    "JobNotFoundError",
    "JobStatus",
    "MockTranslationProvider",
    "PrivacyConsentRequiredError",
    "ProviderCapabilities",
    "ProviderUnavailableError",
    "QuotaExceededError",
    "RateLimitError",
    "SegmentStatus",
    "TokenIntegrityError",
    "TranslationError",
    "TranslationJob",
    "TranslationJobResult",
    "TranslationService",
]
