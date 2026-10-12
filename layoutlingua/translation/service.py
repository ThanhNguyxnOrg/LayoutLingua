"""Deep module facade providing resilient, cached, and transactional translation services."""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Callable

from layoutlingua.core.ir import DocumentIR
from layoutlingua.processing.formula.isolator import FormulaIsolator
from layoutlingua.processing.formula.models import FormulaToken, TextSegment
from layoutlingua.translation._resilience import ResilientExecutor, TokenBucketRateLimiter
from layoutlingua.translation._storage import StorageEngine, compute_cache_key
from layoutlingua.translation.errors import (
    JobCancelledError,
    JobNotFoundError,
    PrivacyConsentRequiredError,
    TokenIntegrityError,
)
from layoutlingua.translation.models import (
    BatchTranslationRequest,
    JobStatus,
    SegmentStatus,
    TranslationJob,
    TranslationJobResult,
)
from layoutlingua.translation.provider import BaseTranslationProvider

# Placeholder regex for converting between <bN></bN> and opaque ⟦LL_FORMULA_XXXX⟧
_XML_TAG_PATTERN = re.compile(r"<b(\d+)></b\1>")
_OPAQUE_PATTERN = re.compile(r"⟦LL_FORMULA_(\d+)⟧")


def _to_opaque_placeholders(text: str) -> str:
    """Convert <bN></bN> tags to opaque brackets ⟦LL_FORMULA_N⟧ to avoid LLM markup confusion."""
    return _XML_TAG_PATTERN.sub(r"⟦LL_FORMULA_\1⟧", text)


def _from_opaque_placeholders(text: str) -> str:
    """Restore opaque brackets ⟦LL_FORMULA_N⟧ back to canonical <bN></bN> format."""
    return _OPAQUE_PATTERN.sub(r"<b\1></b\1>", text)


def extract_document_segments(
    doc_ir: DocumentIR,
    isolator: FormulaIsolator | None = None,
) -> list[TextSegment]:
    """Extract translatable TextSegments from DocumentIR, enforcing fail-closed block suppression.

    Strictly excludes:
    - blocks with block_type == "formula"
    - blocks with block_type == "table_rejected"
    - blocks whose ID is registered in doc_ir.metadata["preserved_block_ids"] or page.metadata["preserved_block_ids"]
    """
    iso = isolator or FormulaIsolator()
    doc_preserved: set[str] = set()
    if hasattr(doc_ir, "metadata") and isinstance(doc_ir.metadata, dict):
        p_ids = doc_ir.metadata.get("preserved_block_ids", set())
        if isinstance(p_ids, (set, list, tuple)):
            doc_preserved.update(p_ids)

    segments: list[TextSegment] = []
    for page in doc_ir.pages:
        page_preserved = set(doc_preserved)
        if hasattr(page, "metadata") and isinstance(page.metadata, dict):
            p_ids = page.metadata.get("preserved_block_ids", set())
            if isinstance(p_ids, (set, list, tuple)):
                page_preserved.update(p_ids)

        for block in page.blocks:
            if (
                block.block_type in ("formula", "table_rejected")
                or block.block_id in page_preserved
            ):
                continue
            if not block.text.strip():
                continue

            segment = iso.isolate_block(block)
            segments.append(segment)

    return segments


class TranslationService:
    """Deep module coordinating caching, persistence, resilience, and formula protection.
    
    Callers interact exclusively via this small, robust interface:
    - translate_job(job, on_progress)
    - resume_job(job_id, on_progress)
    - cancel_job(job_id)
    - record_privacy_consent(provider_id, tier, policy_version)
    """

    def __init__(
        self,
        provider: BaseTranslationProvider,
        db_path: Path | str | None = None,
        no_cache: bool = False,
        max_retries: int = 3,
        base_backoff: float = 0.5,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.provider = provider
        self.no_cache = no_cache
        self._storage = StorageEngine(db_path=db_path)
        self._rate_limiter = TokenBucketRateLimiter(
            requests_per_minute=provider.capabilities.requests_per_minute,
            sleeper=sleeper,
        )
        self._executor = ResilientExecutor(
            max_retries=max_retries,
            base_backoff=base_backoff,
            sleeper=sleeper,
        )
        self._isolator = FormulaIsolator()
        self._cancelled_jobs: set[str] = set()

    def close(self) -> None:
        """Release SQLite resources and active connections."""
        self._storage.close()

    def record_privacy_consent(
        self,
        provider_id: str,
        tier: str,
        policy_version: str,
    ) -> None:
        """Persist explicit user consent for external data use by a provider."""
        self._storage.record_privacy_consent(
            provider_id=provider_id,
            tier=tier,
            policy_version=policy_version,
        )

    def cancel_job(self, job_id: str) -> None:
        """Cooperatively request cancellation of an active or pending job."""
        self._cancelled_jobs.add(job_id)
        self._storage.update_job_status(job_id, JobStatus.CANCELLED)

    def translate_job(
        self,
        job: TranslationJob,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> TranslationJobResult:
        """Execute or resume a translation job with full resilience guarantees."""
        # 1. Register or validate job in persistent storage
        status, completed_count, total_count = self._storage.create_or_validate_job(job)

        # 2. Check for immediate cancellation
        if job.job_id in self._cancelled_jobs:
            self._storage.update_job_status(job.job_id, JobStatus.CANCELLED)
            return self._build_result(job.job_id, cache_hits=0, provider_calls=0, original_segments=job.segments)

        if status == JobStatus.COMPLETED and completed_count == total_count:
            # Job was already completely translated in a prior run
            if on_progress:
                on_progress(total_count, total_count)
            return self._build_result(job.job_id, cache_hits=completed_count, provider_calls=0, original_segments=job.segments)

        # 3. Privacy consent guard (checked BEFORE any text leaves machine)
        caps = self.provider.capabilities
        if caps.requires_data_use_consent:
            has_consent = self._storage.has_privacy_consent(
                provider_id=self.provider.name,
                tier=caps.tier,
                policy_version=caps.policy_version,
            )
            if not has_consent:
                raise PrivacyConsentRequiredError(
                    provider_id=self.provider.name,
                    tier=caps.tier,
                    policy_version=caps.policy_version,
                )

        cache_hits = 0
        provider_calls = 0

        # 4. Process existing cache hits for pending segments
        pending_segments = self._storage.get_pending_segments(job.job_id)
        segment_map = {s.segment_id: s for s in job.segments}

        cached_results_to_commit: list[dict] = []
        unresolved_segments: list[TextSegment] = []

        for p in pending_segments:
            seg_id = p["segment_id"]
            seg = segment_map.get(seg_id)
            if not seg:
                continue

            cache_key = compute_cache_key(
                provider=self.provider.name,
                model=self.provider.model,
                source_language=job.source_language,
                target_language=job.target_language,
                prompt_version=job.prompt_version,
                normalizer_version="unicode-nfc-v1",
                glossary_version=job.glossary_version,
                generation_settings_hash=job.generation_settings_hash,
                normalized_text=seg.masked_text,
            )

            hit_text = None if self.no_cache else self._storage.lookup_cache(cache_key)
            if hit_text is not None:
                # Verify formula tokens in cached translation
                norm_hit = _from_opaque_placeholders(hit_text)
                verification = self._isolator.verify_tokens(seg, norm_hit)
                if verification.is_valid:
                    cache_hits += 1
                    cached_results_to_commit.append(
                        {
                            "segment_id": seg.segment_id,
                            "cache_key": cache_key,
                            "translated_text": norm_hit,
                            "provider": self.provider.name,
                            "model": self.provider.model,
                            "source_language": job.source_language,
                            "target_language": job.target_language,
                            "source_text": seg.masked_text,
                            "prompt_version": job.prompt_version,
                            "glossary_version": job.glossary_version,
                            "settings_hash": job.generation_settings_hash,
                        }
                    )
                    continue

            unresolved_segments.append(seg)

        # Commit initial cache hits atomically
        if cached_results_to_commit:
            self._storage.commit_batch_success(job.job_id, cached_results_to_commit, self.no_cache)
            if on_progress:
                on_progress(len(cached_results_to_commit), len(job.segments))

        if not unresolved_segments:
            return self._build_result(job.job_id, cache_hits=cache_hits, provider_calls=0, original_segments=job.segments)

        # 5. Pack unresolved segments into provider-sized batches
        batches = self._pack_batches(unresolved_segments, caps.max_batch_segments, caps.max_batch_chars)

        # 6. Execute batches with rate limiting, retry, and cancellation checks
        for batch_index, batch_segs in enumerate(batches):
            if job.job_id in self._cancelled_jobs:
                self._storage.update_job_status(job.job_id, JobStatus.CANCELLED)
                break

            # Convert segment masked_text to opaque placeholders for safe LLM transit
            opaque_segs = tuple(
                TextSegment(
                    segment_id=s.segment_id,
                    raw_text=s.raw_text,
                    masked_text=_to_opaque_placeholders(s.masked_text),
                    tokens=s.tokens,
                    span_ids=s.span_ids,
                )
                for s in batch_segs
            )

            request = BatchTranslationRequest(
                batch_id=f"{job.job_id}_batch_{batch_index}",
                segments=opaque_segs,
                source_language=job.source_language,
                target_language=job.target_language,
            )

            def is_cancelled() -> bool:
                return job.job_id in self._cancelled_jobs

            try:
                provider_calls += 1
                batch_result = self._executor.execute(
                    lambda: self.provider.translate_batch(request),
                    rate_limiter=self._rate_limiter,
                    is_cancelled=is_cancelled,
                )
            except JobCancelledError:
                self._storage.update_job_status(job.job_id, JobStatus.CANCELLED)
                break
            except Exception as e:
                # Mark entire batch segments as failed in storage
                failures = [(s.segment_id, str(e)) for s in batch_segs]
                self._storage.record_segment_failures(job.job_id, failures)
                continue

            # 7. Process batch output, verify token integrity, and commit
            valid_results: list[dict] = []
            failures_to_record: list[tuple[str, str]] = []

            for seg in batch_segs:
                raw_translation = batch_result.translations.get(seg.segment_id)
                if raw_translation is None:
                    failures_to_record.append((seg.segment_id, "Missing segment translation in provider response."))
                    continue

                # Restore opaque placeholders back to <bN></bN>
                restored_placeholders = _from_opaque_placeholders(raw_translation)

                # Verify token integrity
                verification = self._isolator.verify_tokens(seg, restored_placeholders)
                if not verification.is_valid:
                    failures_to_record.append(
                        (seg.segment_id, f"Token verification failed: {verification.reason}")
                    )
                    continue

                cache_key = compute_cache_key(
                    provider=self.provider.name,
                    model=self.provider.model,
                    source_language=job.source_language,
                    target_language=job.target_language,
                    prompt_version=job.prompt_version,
                    normalizer_version="unicode-nfc-v1",
                    glossary_version=job.glossary_version,
                    generation_settings_hash=job.generation_settings_hash,
                    normalized_text=seg.masked_text,
                )

                valid_results.append(
                    {
                        "segment_id": seg.segment_id,
                        "cache_key": cache_key,
                        "translated_text": restored_placeholders,
                        "provider": self.provider.name,
                        "model": self.provider.model,
                        "source_language": job.source_language,
                        "target_language": job.target_language,
                        "source_text": seg.masked_text,
                        "prompt_version": job.prompt_version,
                        "glossary_version": job.glossary_version,
                        "settings_hash": job.generation_settings_hash,
                    }
                )

            if valid_results:
                self._storage.commit_batch_success(job.job_id, valid_results, self.no_cache)
            if failures_to_record:
                self._storage.record_segment_failures(job.job_id, failures_to_record)

            if on_progress:
                info = self._storage.get_job_info(job.job_id)
                on_progress(info["completed_segments"], info["total_segments"])

        return self._build_result(job.job_id, cache_hits=cache_hits, provider_calls=provider_calls, original_segments=job.segments)

    def resume_job(
        self,
        job_id: str,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> TranslationJobResult:
        """Reconstruct job from SQLite manifest and resume translating incomplete segments."""
        info = self._storage.get_job_info(job_id)
        raw_segments = self._storage.get_all_segments(job_id)

        segments = tuple(
            TextSegment(
                segment_id=r["segment_id"],
                raw_text=r["source_text"],
                masked_text=r["source_text"],
            )
            for r in raw_segments
        )

        job = TranslationJob(
            job_id=job_id,
            document_fingerprint=info["document_fingerprint"],
            source_language=info["source_language"],
            target_language=info["target_language"],
            segments=segments,
            prompt_version=info["prompt_version"],
            glossary_version=info["glossary_version"],
            generation_settings_hash=info["settings_hash"],
        )

        return self.translate_job(job, on_progress=on_progress)

    def extract_segments(self, doc_ir: DocumentIR) -> list[TextSegment]:
        """Extract translatable TextSegments from DocumentIR, enforcing fail-closed block suppression."""
        return extract_document_segments(doc_ir, isolator=self._isolator)

    def translate_document(
        self,
        doc_ir: DocumentIR,
        target_language: str,
        source_language: str = "en",
        job_id: str | None = None,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> TranslationJobResult:
        """Translate a DocumentIR through the production TranslationService pipeline, strictly omitting suppressed blocks."""
        segments = self.extract_segments(doc_ir)
        jid = job_id or f"job_{doc_ir.doc_id}_{int(time.time() * 1000)}"
        job = TranslationJob(
            job_id=jid,
            document_fingerprint=doc_ir.doc_id or "doc_fingerprint",
            source_language=source_language,
            target_language=target_language,
            segments=tuple(segments),
        )
        return self.translate_job(job, on_progress=on_progress)

    def _pack_batches(
        self,
        segments: list[TextSegment],
        max_segments: int,
        max_chars: int,
    ) -> list[list[TextSegment]]:
        """Greedily pack segments into batches respecting both segment count and character limits."""
        batches: list[list[TextSegment]] = []
        current_batch: list[TextSegment] = []
        current_chars = 0

        for seg in segments:
            seg_len = len(seg.masked_text)
            if current_batch and (
                len(current_batch) >= max_segments or current_chars + seg_len > max_chars
            ):
                batches.append(current_batch)
                current_batch = [seg]
                current_chars = seg_len
            else:
                current_batch.append(seg)
                current_chars += seg_len

        if current_batch:
            batches.append(current_batch)
        return batches

    def _build_result(
        self,
        job_id: str,
        cache_hits: int,
        provider_calls: int,
        original_segments: tuple[TextSegment, ...] | list[TextSegment] | None = None,
    ) -> TranslationJobResult:
        """Construct the immutable TranslationJobResult from storage state."""
        info = self._storage.get_job_info(job_id)
        all_segments = self._storage.get_all_segments(job_id)
        segment_map = {s.segment_id: s for s in original_segments} if original_segments else {}

        translated: dict[str, str] = {}
        failed: dict[str, str] = {}

        for r in all_segments:
            seg_id = r["segment_id"]
            if r["status"] == SegmentStatus.COMPLETED.value:
                # Restore formula tokens if present in masked text
                masked_translated = r["translated_text"] or ""
                seg = segment_map.get(seg_id)
                if seg:
                    translated[seg_id] = self._isolator.restore_translation(seg, masked_translated)
                else:
                    dummy_seg = TextSegment(
                        segment_id=seg_id,
                        raw_text=r["source_text"],
                        masked_text=masked_translated,
                    )
                    translated[seg_id] = self._isolator.restore_translation(dummy_seg, masked_translated)
            elif r["status"] == SegmentStatus.FAILED.value:
                failed[seg_id] = r["error_message"] or "Unknown segment translation error"

        return TranslationJobResult(
            job_id=job_id,
            status=JobStatus(info["status"]),
            translated_segments=translated,
            failed_segments=failed,
            cache_hits=cache_hits,
            provider_calls=provider_calls,
        )
