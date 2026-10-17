"""Concurrent batch translation worker pool for high-throughput document processing.

Coordinates multi-threaded batch translation across cloud APIs (OpenAI, Gemini,
Ollama, DeepSeek) while enforcing bounded concurrency and thread-safe progress tracking.
"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Sequence

from layoutlingua.translation.models import BatchTranslationRequest, TextSegment
from layoutlingua.translation.provider import BaseTranslationProvider


def concurrent_batch_translate(
    provider: BaseTranslationProvider,
    chunks: Sequence[Sequence[TextSegment]],
    source_lang: str,
    target_lang: str,
    max_workers: int = 3,
    on_chunk_done: Callable[[int, int, dict[str, str]], None] | None = None,
) -> dict[str, str]:
    """Translate multiple segment chunks concurrently using a bounded worker pool.

    Args:
        provider: Initialized translation provider.
        chunks: Sequence of segment chunks (each containing e.g. 20-35 segments).
        source_lang: Source language code.
        target_lang: Target language code.
        max_workers: Worker pool concurrency limit (default 3; use 1 for sequential MT).
        on_chunk_done: Callback receiving (chunk_index, done_segments_count, chunk_translations).

    Returns:
        Unified dictionary of segment_id -> translated_text.
    """
    if not chunks:
        return {}

    all_translations: dict[str, str] = {}
    total_segs = sum(len(c) for c in chunks)
    done_segs_lock = threading.Lock()
    done_segs_count = 0

    def _translate_chunk(c_idx: int, chunk: Sequence[TextSegment]) -> tuple[int, dict[str, str]]:
        nonlocal done_segs_count
        req = BatchTranslationRequest(
            batch_id=f"concurrent-batch-{c_idx}",
            source_language=source_lang,
            target_language=target_lang,
            segments=tuple(chunk),
        )
        b_res = provider.translate_batch(req)
        chunk_res = b_res.translations

        with done_segs_lock:
            done_segs_count += len(chunk)
            current_done = done_segs_count

        if on_chunk_done:
            on_chunk_done(c_idx, current_done, chunk_res)

        return c_idx, chunk_res

    effective_workers = max(1, min(max_workers, len(chunks)))

    if effective_workers == 1:
        # Sequential execution path (zero thread overhead)
        for c_idx, chunk in enumerate(chunks):
            _, c_res = _translate_chunk(c_idx, chunk)
            all_translations.update(c_res)
        return all_translations

    # Concurrent thread pool execution path
    with ThreadPoolExecutor(max_workers=effective_workers) as executor:
        future_to_idx = {
            executor.submit(_translate_chunk, c_idx, chunk): c_idx
            for c_idx, chunk in enumerate(chunks)
        }

        for future in as_completed(future_to_idx):
            _, c_res = future.result()
            all_translations.update(c_res)

    return all_translations
