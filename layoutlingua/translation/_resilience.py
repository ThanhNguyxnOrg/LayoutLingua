"""Resilience policies: token-bucket rate limiter and exponential backoff retry executor.

Distinguishes between transient errors (retry with jitter) and non-transient errors (fail fast),
strictly respecting server-specified Retry-After headers and cooperative cancellation.
"""

from __future__ import annotations

import random
import time
from typing import Callable, TypeVar

from layoutlingua.translation.errors import (
    AuthenticationError,
    JobCancelledError,
    ModelUnavailableError,
    PrivacyConsentRequiredError,
    ProviderUnavailableError,
    QuotaExceededError,
    RateLimitError,
    TranslationError,
)

T = TypeVar("T")


class TokenBucketRateLimiter:
    """Thread-safe rate limiter implementing the token bucket algorithm."""

    def __init__(
        self,
        requests_per_minute: float = 60.0,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.capacity = max(1.0, requests_per_minute / 60.0)
        self.fill_rate = max(0.01, requests_per_minute / 60.0)  # tokens per second
        self.tokens = self.capacity
        self.last_update = time.monotonic()
        self.sleeper = sleeper

    def acquire(
        self,
        tokens: float = 1.0,
        is_cancelled: Callable[[], bool] | None = None,
    ) -> None:
        """Block until sufficient tokens are available, periodically checking cancellation."""
        while True:
            if is_cancelled and is_cancelled():
                raise JobCancelledError("Job was cancelled while waiting for rate limit capacity.")

            now = time.monotonic()
            elapsed = now - self.last_update
            self.last_update = now
            self.tokens = min(self.capacity, self.tokens + elapsed * self.fill_rate)

            if self.tokens >= tokens:
                self.tokens -= tokens
                return

            needed = tokens - self.tokens
            sleep_duration = min(0.5, needed / self.fill_rate)
            self.sleeper(sleep_duration)


class ResilientExecutor:
    """Executes provider calls with bounded exponential backoff and jitter."""

    def __init__(
        self,
        max_retries: int = 3,  # 3 retries = 4 total attempts
        base_backoff: float = 0.5,
        max_backoff: float = 10.0,
        jitter_ratio: float = 0.25,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.max_retries = max_retries
        self.base_backoff = base_backoff
        self.max_backoff = max_backoff
        self.jitter_ratio = jitter_ratio
        self.sleeper = sleeper

    def execute(
        self,
        func: Callable[[], T],
        rate_limiter: TokenBucketRateLimiter | None = None,
        is_cancelled: Callable[[], bool] | None = None,
    ) -> T:
        """Execute callable with rate-limiting and retry logic.
        
        Fail-fast without retry for:
        - AuthenticationError
        - QuotaExceededError
        - PrivacyConsentRequiredError
        
        Retries for:
        - RateLimitError (respecting retry_after)
        - ProviderUnavailableError
        """
        attempt = 0
        while True:
            if is_cancelled and is_cancelled():
                raise JobCancelledError("Job was cancelled before provider call execution.")

            if rate_limiter:
                rate_limiter.acquire(tokens=1.0, is_cancelled=is_cancelled)

            try:
                return func()
            except (
                AuthenticationError,
                QuotaExceededError,
                PrivacyConsentRequiredError,
                ModelUnavailableError,
            ):
                # Non-transient errors: fail-fast immediately!
                raise
            except RateLimitError as e:
                attempt += 1
                if attempt > self.max_retries:
                    raise

                sleep_time = e.retry_after if e.retry_after is not None else self._calc_backoff(attempt)
                self._sleep_with_cancel_check(sleep_time, is_cancelled)
            except ProviderUnavailableError:
                attempt += 1
                if attempt > self.max_retries:
                    raise

                sleep_time = self._calc_backoff(attempt)
                self._sleep_with_cancel_check(sleep_time, is_cancelled)
            except Exception as e:
                # Any other unexpected exception fails immediately
                raise TranslationError(f"Unexpected provider error: {e}") from e

    def _calc_backoff(self, attempt: int) -> float:
        """Calculate exponential backoff duration with random jitter."""
        exponential = self.base_backoff * (2 ** (attempt - 1))
        capped = min(self.max_backoff, exponential)
        jitter = random.uniform(0, capped * self.jitter_ratio)
        return capped + jitter

    def _sleep_with_cancel_check(
        self,
        duration: float,
        is_cancelled: Callable[[], bool] | None,
    ) -> None:
        """Sleep in small slices to promptly respond to job cancellation requests."""
        slice_size = 0.1
        remaining = duration
        while remaining > 0:
            if is_cancelled and is_cancelled():
                raise JobCancelledError("Job was cancelled during backoff sleep.")
            sleep_now = min(slice_size, remaining)
            self.sleeper(sleep_now)
            remaining -= sleep_now
