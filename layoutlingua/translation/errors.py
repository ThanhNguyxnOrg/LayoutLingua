"""Standardized exception taxonomy for LayoutLingua translation engine.

Separates request-level, system-level, and segment-level errors,
distinguishing between transient (retryable) and non-transient (fail-fast) failures.
"""

from __future__ import annotations


class TranslationError(Exception):
    """Base exception for all translation-related failures."""


class JobConflictError(TranslationError):
    """Raised when a job_id already exists with conflicting fingerprint or settings."""


class JobNotFoundError(TranslationError):
    """Raised when attempting to resume or inspect a job that does not exist in storage."""


class JobCancelledError(TranslationError):
    """Raised when a translation job is cooperatively cancelled during execution."""


class RateLimitError(TranslationError):
    """Transient rate limit error (e.g. HTTP 429).
    
    Carries optional retry_after in seconds which the engine must strictly respect.
    """

    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class QuotaExceededError(TranslationError):
    """Non-transient quota exhaustion (e.g. daily/monthly quota spent).
    
    Must fail fast and NOT retry in a loop.
    """


class AuthenticationError(TranslationError):
    """Authentication or authorization failure (e.g. HTTP 401 / 403).
    
    Must fail fast and NOT retry.
    """


class ProviderUnavailableError(TranslationError):
    """Transient transport or server outage (e.g. network timeout, 502/503/504).
    
    Eligible for exponential backoff retry.
    """


class PrivacyConsentRequiredError(TranslationError):
    """Raised when a cloud provider uses customer data without recorded user consent.
    
    Fails fast before any document content is transmitted outside the local machine.
    """

    def __init__(self, provider_id: str, tier: str, policy_version: str, message: str | None = None) -> None:
        msg = message or (
            f"Explicit privacy consent required for provider '{provider_id}' (tier '{tier}', "
            f"policy version '{policy_version}'). Data may be retained/used by the provider."
        )
        super().__init__(msg)
        self.provider_id = provider_id
        self.tier = tier
        self.policy_version = policy_version


class InvalidTranslationResponseError(TranslationError):
    """Raised when a provider returns an unparseable, incomplete, or corrupted payload."""


class TokenIntegrityError(TranslationError):
    """Raised when formula placeholder tokens are modified, lost, or duplicated in translation."""
