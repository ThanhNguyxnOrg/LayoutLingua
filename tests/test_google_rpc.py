import unittest
from layoutlingua.processing.formula.models import TextSegment
from layoutlingua.translation.google_rpc import (
    GoogleRpcTranslationProvider,
    _sanitize_translated_tokens,
    _split_into_chunks,
)
from layoutlingua.translation.models import BatchTranslationRequest


class TestGoogleRpcTranslationProvider(unittest.TestCase):
    def test_token_sanitization(self):
        corrupted = "Theo cong thuc ⟦ LL_FORMULA_0 ⟧ va < b1 > < / b1 > ta co..."
        fixed = _sanitize_translated_tokens(corrupted)
        self.assertIn("⟦LL_FORMULA_0⟧", fixed)
        self.assertIn("<b1></b1>", fixed)

    def test_split_into_chunks_short(self):
        text = "This is a short text."
        chunks = _split_into_chunks(text, max_chars=100)
        self.assertEqual(chunks, [text])

    def test_split_into_chunks_long(self):
        sentences = ["Sentence number one.", "Sentence number two.", "Sentence number three."]
        long_text = " ".join(sentences)
        chunks = _split_into_chunks(long_text, max_chars=30)
        self.assertTrue(len(chunks) >= 2)

    def test_provider_properties(self):
        provider = GoogleRpcTranslationProvider()
        self.assertEqual(provider.name, "google_rpc")
        self.assertEqual(provider.model, "google-nmt-web")
        self.assertFalse(provider.capabilities.supports_structured_json)
        self.assertFalse(provider.capabilities.requires_data_use_consent)

    def test_translate_empty_segment(self):
        provider = GoogleRpcTranslationProvider()
        req = BatchTranslationRequest(
            batch_id="b1",
            source_language="en",
            target_language="vi",
            segments=(
                TextSegment(segment_id="s1", raw_text="", masked_text="", tokens=()),
            ),
        )
        res = provider.translate_batch(req)
        self.assertEqual(res.translations.get("s1"), "")

    def test_normalize_lang_code(self):
        provider = GoogleRpcTranslationProvider()
        self.assertEqual(provider._normalize_lang_code("zh-TW"), "zh-TW")
        self.assertEqual(provider._normalize_lang_code("Chinese (Traditional)"), "zh-TW")
        self.assertEqual(provider._normalize_lang_code("zh-CN"), "zh-CN")
        self.assertEqual(provider._normalize_lang_code("Chinese"), "zh-CN")
        self.assertEqual(provider._normalize_lang_code("Russian"), "ru")
        self.assertEqual(provider._normalize_lang_code("Vietnamese"), "vi")
        self.assertEqual(provider._normalize_lang_code("auto"), "auto")


if __name__ == "__main__":
    unittest.main()

