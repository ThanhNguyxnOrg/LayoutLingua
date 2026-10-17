"""Unit tests for concurrent batch translation worker pool."""

from layoutlingua.translation.concurrent_pool import concurrent_batch_translate
from layoutlingua.translation.mock import MockTranslationProvider
from layoutlingua.translation.models import TextSegment


def _make_seg(s_id: str, text: str) -> TextSegment:
    return TextSegment(segment_id=s_id, raw_text=text, masked_text=text, tokens=(), span_ids=[s_id])


def test_concurrent_batch_translate_success():
    provider = MockTranslationProvider()

    c1 = [_make_seg("s1", "Hello world"), _make_seg("s2", "Machine learning")]
    c2 = [_make_seg("s3", "Neural networks"), _make_seg("s4", "Deep learning")]
    c3 = [_make_seg("s5", "Gradient descent"), _make_seg("s6", "Backpropagation")]

    progress_ticks = []

    def _on_done(c_idx: int, done_count: int, chunk_res: dict[str, str]):
        progress_ticks.append((c_idx, done_count))

    results = concurrent_batch_translate(
        provider=provider,
        chunks=[c1, c2, c3],
        source_lang="en",
        target_lang="vi",
        max_workers=2,
        on_chunk_done=_on_done,
    )

    assert len(results) == 6
    assert "s1" in results
    assert "s6" in results
    assert len(progress_ticks) == 3


def test_sequential_single_worker():
    provider = MockTranslationProvider()
    c1 = [_make_seg("s1", "First"), _make_seg("s2", "Second")]

    results = concurrent_batch_translate(
        provider=provider,
        chunks=[c1],
        source_lang="en",
        target_lang="vi",
        max_workers=1,
    )

    assert len(results) == 2
    assert "s1" in results
    assert "s2" in results
