import tempfile
import unittest
from pathlib import Path

from layoutlingua.processing.formula.models import TextSegment
from layoutlingua.translation.cache import (
    CachedTranslationProvider,
    TranslationCache,
    compute_segment_fingerprint,
)
from layoutlingua.translation.mock import MockTranslationProvider
from layoutlingua.translation.models import BatchTranslationRequest


class TestTranslationCache(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_cache.db"
        self.cache = TranslationCache(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_fingerprint_deterministic(self):
        fp1 = compute_segment_fingerprint("en", "vi", "test-model", "Hello world")
        fp2 = compute_segment_fingerprint("en", "vi", "test-model", "Hello world")
        fp3 = compute_segment_fingerprint("en", "vi", "other-model", "Hello world")
        self.assertEqual(fp1, fp2)
        self.assertNotEqual(fp1, fp3)

    def test_cache_miss_and_subsequent_hit(self):
        inner = MockTranslationProvider()
        cached_provider = CachedTranslationProvider(inner, cache=self.cache)

        seg1 = TextSegment(segment_id="s1", raw_text="Formula ⟦LL_FORMULA_0⟧", masked_text="Formula ⟦LL_FORMULA_0⟧", tokens=())
        seg2 = TextSegment(segment_id="s2", raw_text="Another sentence", masked_text="Another sentence", tokens=())

        req1 = BatchTranslationRequest(
            batch_id="b1",
            source_language="en",
            target_language="vi",
            segments=(seg1, seg2),
        )

        res1 = cached_provider.translate_batch(req1)
        self.assertIn("s1", res1.translations)
        self.assertIn("s2", res1.translations)
        self.assertEqual(cached_provider.last_cache_misses, 2)
        self.assertEqual(cached_provider.last_cache_hits, 0)

        # Second call with same segments should be 100% hits
        res2 = cached_provider.translate_batch(req1)
        self.assertEqual(res2.translations, res1.translations)
        self.assertEqual(cached_provider.last_cache_hits, 2)
        self.assertEqual(cached_provider.last_cache_misses, 0)

    def test_token_preservation_through_cache(self):
        inner = MockTranslationProvider()
        cached_provider = CachedTranslationProvider(inner, cache=self.cache)

        complex_text = "Let ⟦LL_FORMULA_0⟧ and ⟦LL_FORMULA_1⟧ be vectors in <b1></b1>."
        seg = TextSegment(segment_id="s1", raw_text=complex_text, masked_text=complex_text, tokens=())
        req = BatchTranslationRequest(batch_id="b1", source_language="en", target_language="vi", segments=(seg,))

        res1 = cached_provider.translate_batch(req)
        self.assertIn("⟦LL_FORMULA_0⟧", res1.translations["s1"])
        self.assertIn("<b1></b1>", res1.translations["s1"])

        res2 = cached_provider.translate_batch(req)
        self.assertEqual(res2.translations["s1"], res1.translations["s1"])

    def test_empty_segment(self):
        inner = MockTranslationProvider()
        cached_provider = CachedTranslationProvider(inner, cache=self.cache)

        seg = TextSegment(segment_id="s1", raw_text="", masked_text="", tokens=())
        req = BatchTranslationRequest(batch_id="b1", source_language="en", target_language="vi", segments=(seg,))

        res = cached_provider.translate_batch(req)
        self.assertEqual(res.translations.get("s1"), "")

    def test_provider_properties_passthrough(self):
        inner = MockTranslationProvider()
        cached_provider = CachedTranslationProvider(inner, cache=self.cache)

        self.assertEqual(cached_provider.name, "cached_mock")
        self.assertEqual(cached_provider.model, inner.model)
        self.assertEqual(cached_provider.capabilities, inner.capabilities)


if __name__ == "__main__":
    unittest.main()
