"""Abstract base interface for translation providers (the single external seam)."""

from __future__ import annotations

from abc import ABC, abstractmethod

from layoutlingua.translation.models import (
    BatchTranslationRequest,
    BatchTranslationResult,
    ProviderCapabilities,
)


class BaseTranslationProvider(ABC):
    """Abstract interface defining the seam for translation backends.
    
    Concrete adapters:
    - MockTranslationProvider (tests and early contract)
    - ArgosTranslationProvider (Slice 3B: zero-key offline)
    - GeminiTranslationProvider (Slice 3C: Google GenAI)
    - OpenAITranslationProvider (Slice 3C: OpenAI-compatible)
    - GoogleRpcTranslationProvider (Slice 3D: experimental throttled)
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier of the provider (e.g. 'mock', 'argos', 'gemini', 'openai')."""

    @property
    @abstractmethod
    def model(self) -> str:
        """Model or engine identifier (e.g. 'deterministic-v1', 'translate-en_vi', 'gemini-3.1-flash-lite')."""

    @property
    @abstractmethod
    def capabilities(self) -> ProviderCapabilities:
        """Operational capabilities, rate limits, and consent requirements."""

    @abstractmethod
    def translate_batch(self, request: BatchTranslationRequest) -> BatchTranslationResult:
        """Translate a batch of text segments.
        
        Must raise standard exceptions on failure:
        - RateLimitError: on rate limits (with retry_after if known)
        - QuotaExceededError: on exhausted account quota
        - AuthenticationError: on 401/403
        - ProviderUnavailableError: on network or server downtime
        - InvalidTranslationResponseError: on malformed responses
        """
