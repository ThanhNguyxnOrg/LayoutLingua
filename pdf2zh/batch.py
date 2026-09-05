"""Translation Batching and Concurrency Optimizer for LayoutLingua.

Batches multiple short text segments (table cells, list items, figure captions)
into consolidated translation payloads with safe delimiters to minimize HTTP round-trips
and avoid rate limiting.
Addresses pain points from Marker #885 and PDFMathTranslate multi-request issues.
"""

from __future__ import annotations

import logging
from typing import Callable, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Delimiter unlikely to occur in standard prose
BATCH_DELIMITER = "\n\n===LL_SPLIT===\n\n"


class TranslationBatcher:
    """Combines short segments into batches for efficient bulk translation."""

    def __init__(
        self,
        translate_func: Callable[[str], str],
        max_batch_chars: int = 1500,
        max_batch_size: int = 15,
        delimiter: str = BATCH_DELIMITER,
    ):
        self.translate_func = translate_func
        self.max_batch_chars = max_batch_chars
        self.max_batch_size = max_batch_size
        self.delimiter = delimiter

    def batch_translate_segments(self, segments: List[str]) -> List[str]:
        """Translate a list of segments using adaptive batching with fallback.

        Segments longer than max_batch_chars or containing formulas are translated individually.
        Short prose segments are grouped into batches.
        """
        if not segments:
            return []

        results: List[Optional[str]] = [None] * len(segments)
        current_batch: List[int] = []  # indices of segments in current batch
        current_batch_len = 0

        def flush_batch() -> None:
            nonlocal current_batch, current_batch_len
            if not current_batch:
                return

            if len(current_batch) == 1:
                idx = current_batch[0]
                results[idx] = self.translate_func(segments[idx])
                current_batch = []
                current_batch_len = 0
                return

            batch_text = self.delimiter.join(segments[i] for i in current_batch)
            try:
                translated_batch = self.translate_func(batch_text)
                parts = translated_batch.split(self.delimiter.strip())
                if len(parts) == len(current_batch):
                    for b_i, p in zip(current_batch, parts):
                        results[b_i] = p.strip()
                else:
                    # Delimiter count mismatched in MT output; fallback individually
                    logger.debug(
                        "Batch delimiter mismatch (%d vs %d); falling back individually",
                        len(parts),
                        len(current_batch),
                    )
                    for b_i in current_batch:
                        results[b_i] = self.translate_func(segments[b_i])
            except Exception as e:
                logger.warning("Batch translation failed (%s); falling back individually", e)
                for b_i in current_batch:
                    try:
                        results[b_i] = self.translate_func(segments[b_i])
                    except Exception:
                        results[b_i] = segments[b_i]

            current_batch = []
            current_batch_len = 0

        for idx, seg in enumerate(segments):
            seg_len = len(seg)
            # If segment is too large or contains complex internal markers, translate separately
            if seg_len > self.max_batch_chars or "{v" in seg:
                flush_batch()
                try:
                    results[idx] = self.translate_func(seg)
                except Exception:
                    results[idx] = seg
                continue

            if (
                current_batch_len + seg_len > self.max_batch_chars
                or len(current_batch) >= self.max_batch_size
            ):
                flush_batch()

            current_batch.append(idx)
            current_batch_len += seg_len

        flush_batch()
        return [r if r is not None else segments[i] for i, r in enumerate(results)]
