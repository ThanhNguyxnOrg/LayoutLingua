"""Comprehensive test suite for Slice 3A Translation Resilience, Caching, and Storage.

Validates:
- Deep module interface invariants (TranslationService).
- Canonical deterministic cache keys.
- SQLite WAL transactions and multi-threaded concurrency.
- Crash recovery and segment resumption.
- HTTP 429 rate limits respecting Retry-After.
- Fail-fast on 401 AuthenticationError and QuotaExceededError without infinite retries.
- Privacy consent guard enforcement before transmitting data.
- Formula token integrity verification and fail-closed isolation.
- Out-of-order segment response reassembly.
- no_cache flag behavior (bypassing cache while preserving job checkpoints).
- Job conflict detection (fingerprint mismatch).
- Cooperative job cancellation.
"""

from __future__ import annotations

import gc
import tempfile
import threading
import unittest
from pathlib import Path

from layoutlingua.processing.formula.models import FormulaToken, TextSegment
from layoutlingua.translation import (
    AuthenticationError,
    JobCancelledError,
    JobConflictError,
    JobNotFoundError,
    JobStatus,
    MockTranslationProvider,
    PrivacyConsentRequiredError,
    ProviderCapabilities,
    QuotaExceededError,
    RateLimitError,
    TranslationJob,
    TranslationService,
)
from layoutlingua.translation._storage import StorageEngine, compute_cache_key


class TestSlice3ATranslationResilience(unittest.TestCase):
    """Test suite exercising TranslationService deep module and internal invariants."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_layoutlingua.sqlite"
        self._services: list[TranslationService] = []
        self._storages: list[StorageEngine] = []

    def tearDown(self) -> None:
        for s in self._services:
            try:
                s.close()
            except Exception:
                pass
        for st in self._storages:
            try:
                st.close()
            except Exception:
                pass
        gc.collect()
        try:
            self.temp_dir.cleanup()
        except PermissionError:
            pass

    def _make_service(self, provider, **kwargs) -> TranslationService:
        kwargs.setdefault("db_path", self.db_path)
        service = TranslationService(provider=provider, **kwargs)
        self._services.append(service)
        return service

    def _make_storage(self) -> StorageEngine:
        storage = StorageEngine(db_path=self.db_path)
        self._storages.append(storage)
        return storage

    def _create_sample_segments(self, count: int = 5, with_formulas: bool = True) -> tuple[TextSegment, ...]:
        """Helper to create synthetic TextSegments for testing."""
        segs: list[TextSegment] = []
        for i in range(count):
            if with_formulas and i % 2 == 1:
                token = FormulaToken(
                    token_id=0,
                    placeholder="<b0></b0>",
                    raw_content=r"\int_0^\infty e^{-x} dx",
                )
                raw_text = f"Theorem {i}: The integral is equal to 1."
                masked_text = f"Theorem {i}: The integral <b0></b0> is equal to 1."
                segs.append(
                    TextSegment(
                        segment_id=f"seg_{i}",
                        raw_text=raw_text,
                        masked_text=masked_text,
                        tokens=[token],
                    )
                )
            else:
                text = f"Section {i}: Introductory overview text."
                segs.append(
                    TextSegment(
                        segment_id=f"seg_{i}",
                        raw_text=text,
                        masked_text=text,
                    )
                )
        return tuple(segs)

    # -------------------------------------------------------------------------
    # 1. Cache Round-trip and Hit Skip
    # -------------------------------------------------------------------------

    def test_cache_hit_bypasses_provider(self) -> None:
        """Verify that identical segments on subsequent runs hit cache and avoid calling provider."""
        provider = MockTranslationProvider()
        service = self._make_service(provider=provider)

        segments = self._create_sample_segments(count=4)
        job = TranslationJob(
            job_id="job-cache-1",
            document_fingerprint="fp-cache-1",
            source_language="en",
            target_language="vi",
            segments=segments,
        )

        # First run: calls provider
        result1 = service.translate_job(job)
        self.assertEqual(result1.status, JobStatus.COMPLETED)
        self.assertEqual(result1.cache_hits, 0)
        self.assertGreater(result1.provider_calls, 0)
        first_calls = provider.call_count

        # Second run with new job ID but identical text contents
        job2 = TranslationJob(
            job_id="job-cache-2",
            document_fingerprint="fp-cache-2",
            source_language="en",
            target_language="vi",
            segments=segments,
        )
        result2 = service.translate_job(job2)
        self.assertEqual(result2.status, JobStatus.COMPLETED)
        self.assertEqual(result2.cache_hits, 4)
        self.assertEqual(result2.provider_calls, 0)
        # Provider must not have received any additional calls
        self.assertEqual(provider.call_count, first_calls)

    # -------------------------------------------------------------------------
    # 2. Canonical Deterministic Cache Key
    # -------------------------------------------------------------------------

    def test_canonical_cache_key_determinism(self) -> None:
        """Verify hash is stable and strictly distinguishes model, prompt, and normalizer versions."""
        key1 = compute_cache_key(
            provider="gemini",
            model="gemini-3.1-flash-lite",
            source_language="en",
            target_language="vi",
            prompt_version="v1",
            normalizer_version="unicode-nfc-v1",
            glossary_version="gloss-v0",
            generation_settings_hash="temp0",
            normalized_text="Hello world",
        )
        key2 = compute_cache_key(
            provider="gemini",
            model="gemini-3.1-flash-lite",
            source_language="en",
            target_language="vi",
            prompt_version="v1",
            normalizer_version="unicode-nfc-v1",
            glossary_version="gloss-v0",
            generation_settings_hash="temp0",
            normalized_text="Hello world",
        )
        self.assertEqual(key1, key2)

        # Altering model must change key
        key_different_model = compute_cache_key(
            provider="gemini",
            model="gemini-pro",
            source_language="en",
            target_language="vi",
            prompt_version="v1",
            normalizer_version="unicode-nfc-v1",
            glossary_version="gloss-v0",
            generation_settings_hash="temp0",
            normalized_text="Hello world",
        )
        self.assertNotEqual(key1, key_different_model)

        # Altering prompt version must change key
        key_different_prompt = compute_cache_key(
            provider="gemini",
            model="gemini-3.1-flash-lite",
            source_language="en",
            target_language="vi",
            prompt_version="v2",
            normalizer_version="unicode-nfc-v1",
            glossary_version="gloss-v0",
            generation_settings_hash="temp0",
            normalized_text="Hello world",
        )
        self.assertNotEqual(key1, key_different_prompt)

    # -------------------------------------------------------------------------
    # 3. SQLite Concurrency and Thread Safety
    # -------------------------------------------------------------------------

    def test_storage_concurrency_multi_threaded(self) -> None:
        """Ensure WAL mode and busy timeout allow concurrent reads and writes without crashing."""
        storage = self._make_storage()
        errors: list[Exception] = []

        def worker(worker_id: int) -> None:
            try:
                for i in range(20):
                    key = f"key_{worker_id}_{i}"
                    # Perform atomic batch commit
                    storage.commit_batch_success(
                        job_id=f"job_concurrent_{worker_id}",
                        results=[
                            {
                                "segment_id": f"s_{worker_id}_{i}",
                                "cache_key": key,
                                "translated_text": f"Trans {worker_id} {i}",
                                "provider": "mock",
                                "model": "m1",
                                "source_language": "en",
                                "target_language": "vi",
                                "source_text": f"Src {worker_id} {i}",
                                "prompt_version": "v1",
                                "glossary_version": "v0",
                                "settings_hash": "default",
                            }
                        ],
                    )
                    # Perform read
                    storage.lookup_cache(key)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(w,)) for w in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"Concurrent workers encountered errors: {errors}")

    # -------------------------------------------------------------------------
    # 4. Crash Recovery and Partial Segment Resumption
    # -------------------------------------------------------------------------

    def test_crash_recovery_resumes_incomplete_segments(self) -> None:
        """Simulate a crash/failure midway and verify resumption only translates pending segments."""
        # Provider configured with smaller batch size (2 segments per batch)
        caps = ProviderCapabilities(max_batch_segments=2)
        provider = MockTranslationProvider(capabilities=caps)
        service = self._make_service(provider=provider)

        segments = self._create_sample_segments(count=6, with_formulas=False)
        job = TranslationJob(
            job_id="job-crash-test",
            document_fingerprint="fp-crash-test",
            source_language="en",
            target_language="vi",
            segments=segments,
        )

        # Allow first batch call to succeed, fail on second and subsequent calls
        orig_translate = provider.translate_batch
        call_tracker = {"calls": 0}

        def mock_translate_batch(req):
            call_tracker["calls"] += 1
            if call_tracker["calls"] == 1:
                return orig_translate(req)
            raise QuotaExceededError("Account monthly limit exceeded")

        provider.translate_batch = mock_translate_batch

        result1 = service.translate_job(job)
        self.assertEqual(result1.status, JobStatus.PARTIAL_FAILED)
        self.assertEqual(len(result1.translated_segments), 2)
        self.assertEqual(len(result1.failed_segments), 4)

        # Now recover provider (account quota restored)
        provider.translate_batch = orig_translate
        provider.call_count = 0

        # Call resume_job to rehydrate and finish
        result2 = service.resume_job("job-crash-test")
        self.assertEqual(result2.status, JobStatus.COMPLETED)
        self.assertEqual(len(result2.translated_segments), 6)
        self.assertEqual(len(result2.failed_segments), 0)
        # Must only call provider for remaining 4 segments (2 batches of 2)
        self.assertEqual(provider.call_count, 2)

    # -------------------------------------------------------------------------
    # 5. Rate Limit HTTP 429 & Retry-After
    # -------------------------------------------------------------------------

    def test_rate_limit_429_respects_retry_after(self) -> None:
        """Verify that transient 429 errors pause for retry_after and succeed on retry."""
        provider = MockTranslationProvider(
            fail_first_n_calls=2,
            fail_with_error=RateLimitError("Too Many Requests", retry_after=0.02),
        )
        service = self._make_service(
            provider=provider,
            max_retries=3,
            base_backoff=0.01,
        )

        segments = self._create_sample_segments(count=2, with_formulas=False)
        job = TranslationJob(
            job_id="job-429-test",
            document_fingerprint="fp-429-test",
            source_language="en",
            target_language="vi",
            segments=segments,
        )

        result = service.translate_job(job)
        self.assertEqual(result.status, JobStatus.COMPLETED)
        self.assertEqual(len(result.translated_segments), 2)
        # Failed 2 times, succeeded on 3rd attempt
        self.assertEqual(provider.call_count, 3)

    # -------------------------------------------------------------------------
    # 6. Non-Transient Fail-Fast (401 Auth & Quota)
    # -------------------------------------------------------------------------

    def test_auth_401_fails_fast_without_retrying(self) -> None:
        """Verify 401 AuthenticationError aborts immediately with 1 call attempt."""
        provider = MockTranslationProvider(
            simulate_error=AuthenticationError("Invalid API key provided"),
        )
        service = self._make_service(
            provider=provider,
            max_retries=3,
        )

        segments = self._create_sample_segments(count=2)
        job = TranslationJob(
            job_id="job-auth-fail",
            document_fingerprint="fp-auth-fail",
            source_language="en",
            target_language="vi",
            segments=segments,
        )

        result = service.translate_job(job)
        self.assertEqual(result.status, JobStatus.FAILED)
        # Must NOT retry 3 times: exactly 1 call
        self.assertEqual(provider.call_count, 1)

    def test_quota_exceeded_fails_fast_without_retrying(self) -> None:
        """Verify QuotaExceededError aborts immediately with 1 call attempt."""
        provider = MockTranslationProvider(
            simulate_error=QuotaExceededError("Monthly quota exhausted"),
        )
        service = self._make_service(
            provider=provider,
            max_retries=3,
        )

        segments = self._create_sample_segments(count=2)
        job = TranslationJob(
            job_id="job-quota-fail",
            document_fingerprint="fp-quota-fail",
            source_language="en",
            target_language="vi",
            segments=segments,
        )

        result = service.translate_job(job)
        self.assertEqual(result.status, JobStatus.FAILED)
        self.assertEqual(provider.call_count, 1)

    # -------------------------------------------------------------------------
    # 7. Privacy Consent Guard
    # -------------------------------------------------------------------------

    def test_privacy_consent_guard_blocks_unauthorized_data_use(self) -> None:
        """Verify provider requiring data use consent halts before transmitting any text."""
        caps = ProviderCapabilities(
            requires_data_use_consent=True,
            tier="free",
            policy_version="2026-06",
        )
        provider = MockTranslationProvider(capabilities=caps)
        service = self._make_service(provider=provider)

        segments = self._create_sample_segments(count=2)
        job = TranslationJob(
            job_id="job-privacy-test",
            document_fingerprint="fp-privacy-test",
            source_language="en",
            target_language="vi",
            segments=segments,
        )

        # 1. Calling without consent raises PrivacyConsentRequiredError
        with self.assertRaises(PrivacyConsentRequiredError) as ctx:
            service.translate_job(job)

        self.assertEqual(ctx.exception.provider_id, "mock")
        self.assertEqual(ctx.exception.tier, "free")
        self.assertEqual(ctx.exception.policy_version, "2026-06")
        # Ensure zero calls to provider
        self.assertEqual(provider.call_count, 0)

        # 2. Record explicit consent
        service.record_privacy_consent(
            provider_id="mock",
            tier="free",
            policy_version="2026-06",
        )

        # 3. Calling again succeeds cleanly
        result = service.translate_job(job)
        self.assertEqual(result.status, JobStatus.COMPLETED)
        self.assertGreater(provider.call_count, 0)

    # -------------------------------------------------------------------------
    # 8. Token Integrity Fail-Closed Isolation
    # -------------------------------------------------------------------------

    def test_corrupted_tokens_fail_closed_and_bypass_cache(self) -> None:
        """Verify that provider corrupting formula tokens results in FAILED segment and no cache commit."""
        provider = MockTranslationProvider(corrupt_tokens=True)
        service = self._make_service(provider=provider)

        # Create 1 segment with formula and 1 segment without
        token = FormulaToken(token_id=0, placeholder="<b0></b0>", raw_content=r"\alpha + \beta")
        seg_with_math = TextSegment(
            segment_id="math_seg",
            raw_text="The formula is <b0></b0>.",
            masked_text="The formula is <b0></b0>.",
            tokens=[token],
        )
        seg_plain = TextSegment(
            segment_id="plain_seg",
            raw_text="Plain sentence.",
            masked_text="Plain sentence.",
        )

        job = TranslationJob(
            job_id="job-token-corrupt",
            document_fingerprint="fp-token-corrupt",
            source_language="en",
            target_language="vi",
            segments=(seg_with_math, seg_plain),
        )

        result = service.translate_job(job)
        # Math segment should fail verification, plain segment succeeds
        self.assertEqual(result.status, JobStatus.PARTIAL_FAILED)
        self.assertIn("plain_seg", result.translated_segments)
        self.assertIn("math_seg", result.failed_segments)

        # Verify that math segment was NOT committed to translation_cache
        storage = self._make_storage()
        math_cache_key = compute_cache_key(
            provider="mock",
            model="deterministic-v1",
            source_language="en",
            target_language="vi",
            prompt_version="translation-v1",
            normalizer_version="unicode-nfc-v1",
            glossary_version="v0",
            generation_settings_hash="default",
            normalized_text="The formula is <b0></b0>.",
        )
        self.assertIsNone(storage.lookup_cache(math_cache_key))

    # -------------------------------------------------------------------------
    # 9. Out-of-Order Segment Response
    # -------------------------------------------------------------------------

    def test_out_of_order_segment_reassembly(self) -> None:
        """Verify that when provider returns segments in reverse order, engine reassembles by ID."""
        provider = MockTranslationProvider(reorder_segments=True)
        service = self._make_service(provider=provider)

        segments = self._create_sample_segments(count=4, with_formulas=False)
        job = TranslationJob(
            job_id="job-reorder-test",
            document_fingerprint="fp-reorder-test",
            source_language="en",
            target_language="vi",
            segments=segments,
        )

        result = service.translate_job(job)
        self.assertEqual(result.status, JobStatus.COMPLETED)
        # Check all 4 segments mapped correctly
        for i in range(4):
            self.assertIn(f"seg_{i}", result.translated_segments)

    # -------------------------------------------------------------------------
    # 10. no_cache Behavior
    # -------------------------------------------------------------------------

    def test_no_cache_skips_cache_while_preserving_job_checkpoints(self) -> None:
        """Verify no_cache=True skips translation_cache read/write but preserves job state."""
        provider = MockTranslationProvider()
        service = self._make_service(provider=provider, no_cache=True)

        segments = self._create_sample_segments(count=2, with_formulas=False)
        job = TranslationJob(
            job_id="job-no-cache-test",
            document_fingerprint="fp-no-cache-test",
            source_language="en",
            target_language="vi",
            segments=segments,
        )

        result = service.translate_job(job)
        self.assertEqual(result.status, JobStatus.COMPLETED)

        # Check that translation_cache table is empty
        storage = self._make_storage()
        cache_key = compute_cache_key(
            provider="mock",
            model="deterministic-v1",
            source_language="en",
            target_language="vi",
            prompt_version="translation-v1",
            normalizer_version="unicode-nfc-v1",
            glossary_version="v0",
            generation_settings_hash="default",
            normalized_text=segments[0].masked_text,
        )
        self.assertIsNone(storage.lookup_cache(cache_key))

        # But job checkpoint state MUST exist and be COMPLETED
        info = storage.get_job_info("job-no-cache-test")
        self.assertEqual(info["status"], JobStatus.COMPLETED.value)
        self.assertEqual(info["completed_segments"], 2)

    # -------------------------------------------------------------------------
    # 11. Job Conflict Detection
    # -------------------------------------------------------------------------

    def test_job_conflict_detection(self) -> None:
        """Verify that reusing a job_id with a different fingerprint raises JobConflictError."""
        provider = MockTranslationProvider()
        service = self._make_service(provider=provider)

        segments = self._create_sample_segments(count=2)
        job1 = TranslationJob(
            job_id="job-unique-id",
            document_fingerprint="fingerprint-A",
            source_language="en",
            target_language="vi",
            segments=segments,
        )
        service.translate_job(job1)

        # Now try to register same job_id with different fingerprint
        job2 = TranslationJob(
            job_id="job-unique-id",
            document_fingerprint="fingerprint-B",
            source_language="en",
            target_language="vi",
            segments=segments,
        )
        with self.assertRaises(JobConflictError):
            service.translate_job(job2)

    # -------------------------------------------------------------------------
    # 12. Cooperative Job Cancellation
    # -------------------------------------------------------------------------

    def test_job_cancellation(self) -> None:
        """Verify that cancel_job stops execution and records CANCELLED status."""
        provider = MockTranslationProvider()
        service = self._make_service(provider=provider)

        service.cancel_job("job-cancel-test")

        segments = self._create_sample_segments(count=3)
        job = TranslationJob(
            job_id="job-cancel-test",
            document_fingerprint="fp-cancel-test",
            source_language="en",
            target_language="vi",
            segments=segments,
        )

        result = service.translate_job(job)
        self.assertEqual(result.status, JobStatus.CANCELLED)
        self.assertEqual(provider.call_count, 0)
