"""Regression tests for translation-speed guards (no geometry change)."""

import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import requests

import pdf2zh.cache as cache_module
import pdf2zh.converter as converter_module
import pdf2zh.translator as translator_module
from pdf2zh.batch import BATCH_DELIMITER, TranslationBatcher
from pdf2zh.cache import TranslationCache, clean_test_db, init_test_db
from pdf2zh.converter import (
    _is_batchable_segment,
    _is_transient_translation_error,
    apply_glossary,
)
from pdf2zh.translator import (
    CircuitOpenError,
    DeepLXTranslator,
    FormulaPlaceholderError,
    GoogleTranslator,
    RateLimiter,
    SegmentTooLongError,
)


def _status_error(status: int) -> SimpleNamespace:
    return SimpleNamespace(response=SimpleNamespace(status_code=status))


class PerfGuardsTests(unittest.TestCase):
    def test_retry_only_on_throttle_or_server_errors(self):
        self.assertTrue(_is_transient_translation_error(_status_error(429)))
        self.assertTrue(_is_transient_translation_error(_status_error(503)))
        self.assertFalse(_is_transient_translation_error(_status_error(400)))
        self.assertFalse(
            _is_transient_translation_error(
                FormulaPlaceholderError("placeholders changed")
            )
        )

    def test_batchable_only_for_marker_free_prose(self):
        self.assertTrue(_is_batchable_segment("Hello world", 1500))
        self.assertFalse(_is_batchable_segment("see {v0} here", 1500))
        self.assertFalse(_is_batchable_segment("<s1>Title</s1>", 1500))
        self.assertFalse(_is_batchable_segment("a <b0></b0> b", 1500))
        self.assertFalse(_is_batchable_segment("x" * 1501, 1500))

    def test_batcher_isolates_marked_segments(self):
        calls = []

        def mock_translate(text: str) -> str:
            calls.append(text)
            parts = text.split(BATCH_DELIMITER.strip())
            return f" {BATCH_DELIMITER.strip()} ".join(
                f"Dịch: {p.strip()}" for p in parts
            )

        batcher = TranslationBatcher(translate_func=mock_translate)
        results = batcher.batch_translate_segments(
            ["Hello world", "Good morning", "see {v0} here"]
        )
        self.assertEqual(len(calls), 2)
        self.assertTrue(results[0].startswith("Dịch: "))
        self.assertTrue(results[1].startswith("Dịch: "))
        self.assertEqual(results[2], "Dịch: see {v0} here")

    def test_rate_limiter_spaces_requests(self):
        limiter = RateLimiter(max_qps=5.0)
        marks = [time.monotonic()]
        for _ in range(3):
            limiter.wait()
            marks.append(time.monotonic())
        self.assertGreaterEqual(
            marks[3] - marks[0], 2 * limiter._interval - 0.05
        )

    def test_throttle_spaces_google_requests(self):
        translator = GoogleTranslator("en", "vi")
        calls = []

        class StubResponse:
            status_code = 200
            text = '<div class="t0">Xin chào<'

            def raise_for_status(self) -> None:
                pass

        def stub_get(*args, **kwargs) -> StubResponse:
            calls.append(time.monotonic())
            return StubResponse()

        translator.session.get = stub_get  # type: ignore[method-assign]
        self.assertEqual(translator.do_translate("Hello"), "Xin chào")
        self.assertEqual(translator.do_translate("Hello"), "Xin chào")
        self.assertGreaterEqual(calls[1] - calls[0], 0.15)

    def test_int32_mask_keeps_label_semantics(self):
        int_box = np.ones((8, 8), dtype=np.int32)
        float_box = np.ones((8, 8))
        int_box[2:5, 2:5] = 4
        float_box[2:5, 2:5] = 4
        int_box[0:1, 0:1] = 0
        float_box[0:1, 0:1] = 0
        self.assertTrue(bool(int_box.any()) == bool(float_box.any()))
        self.assertEqual(int_box.tolist(), float_box.tolist())


class RetryWaitsTests(unittest.TestCase):
    def test_retry_after_delta_seconds(self):
        from pdf2zh.converter import _retry_after_seconds
        exc = SimpleNamespace(response=SimpleNamespace(headers={"Retry-After": "120"}, status_code=429))
        self.assertEqual(_retry_after_seconds(exc), 60.0)

    def test_retry_after_garbage_falls_back(self):
        from pdf2zh.converter import _retry_after_seconds
        exc = SimpleNamespace(response=SimpleNamespace(headers={"Retry-After": "banana"}, status_code=429))
        self.assertIsNone(_retry_after_seconds(exc))

    def test_retry_after_missing_is_none(self):
        from pdf2zh.converter import _retry_after_seconds
        self.assertIsNone(_retry_after_seconds(ValueError("nope")))

    def test_retry_after_http_date_future_and_past(self):
        from email.utils import formatdate
        from pdf2zh.converter import _retry_after_seconds
        future = formatdate(time.time() + 30, usegmt=True)
        past = formatdate(time.time() - 30, usegmt=True)
        dated = lambda raw: SimpleNamespace(
            response=SimpleNamespace(headers={"Retry-After": raw}, status_code=429)
        )
        value = _retry_after_seconds(dated(future))
        self.assertGreater(value, 0.0)
        self.assertLessEqual(value, 60.0)
        self.assertEqual(_retry_after_seconds(dated(past)), 0.0)
        self.assertEqual(
            _retry_after_seconds(
                SimpleNamespace(
                    response=SimpleNamespace(headers={"Retry-After": "2"}, status_code=429)
                )
            ),
            2.0,
        )

    def test_retry_after_wait_never_raises(self):
        from pdf2zh.converter import _RetryAfterWait

        class BadHeaders:
            def get(self, _key):
                raise RuntimeError("broken headers")

        exc = SimpleNamespace(
            response=SimpleNamespace(headers=BadHeaders(), status_code=429)
        )
        self.assertEqual(_RetryAfterWait()(SimpleNamespace(outcome=None)), 0.0)
        state = SimpleNamespace(
            outcome=SimpleNamespace(exception=lambda: exc)
        )
        self.assertEqual(_RetryAfterWait()(state), 0.0)

    def test_breaker_wins_over_wait(self):
        from pdf2zh.translator import CircuitOpenError
        self.assertFalse(_is_transient_translation_error(CircuitOpenError("blocked")))


class CacheCleanupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.test_db = init_test_db()
        self.old_max = cache_module.MAX_CACHE_ROWS
        self.old_probability = cache_module.CLEAN_PROBABILITY
        cache_module.MAX_CACHE_ROWS = 5
        cache_module.CLEAN_PROBABILITY = 1.0

    def tearDown(self) -> None:
        cache_module.MAX_CACHE_ROWS = self.old_max
        cache_module.CLEAN_PROBABILITY = self.old_probability
        clean_test_db(self.test_db)

    def test_cleanup_keeps_newest_rows_under_cap(self):
        cache = TranslationCache("google", {"lang_out": "vi"})
        for index in range(8):
            cache.set(f"segment {index}", f"bản {index}")
        cache_module._maybe_clean_cache()
        self.assertIsNone(cache.get("segment 0"))
        self.assertIsNone(cache.get("segment 1"))
        self.assertIsNone(cache.get("segment 2"))
        self.assertEqual(cache.get("segment 7"), "bản 7")


class CircuitBreakerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.old_count = translator_module._consecutive_429s
        self.old_opened = translator_module._circuit_opened_at
        translator_module._consecutive_429s = 0
        translator_module._circuit_opened_at = None

    def tearDown(self) -> None:
        translator_module._consecutive_429s = self.old_count
        translator_module._circuit_opened_at = self.old_opened

    def test_trips_after_consecutive_429s_and_recovers(self):
        for _ in range(translator_module._CIRCUIT_THRESHOLD - 1):
            translator_module._circuit_record_429()
        translator_module._circuit_allows_request()
        translator_module._circuit_record_429()
        with self.assertRaises(CircuitOpenError):
            translator_module._circuit_allows_request()
        translator_module._circuit_opened_at = (
            time.monotonic() - translator_module._CIRCUIT_COOLDOWN - 1.0
        )
        translator_module._circuit_allows_request()
        translator_module._circuit_record_success()
        translator_module._circuit_allows_request()

    def test_open_circuit_skips_network(self):
        translator = GoogleTranslator("en", "vi")
        translator.session.get = lambda *a, **k: self.fail("network hit")  # type: ignore[method-assign]
        for _ in range(translator_module._CIRCUIT_THRESHOLD):
            translator_module._circuit_record_429()
        with self.assertRaises(CircuitOpenError):
            translator.do_translate("Hello")


class ExternalGlossaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.old_table = converter_module._glossary_table
        self.old_env = os.environ.get("LAYOUTLINGUA_GLOSSARY")
        converter_module._glossary_table = None
        self.records = Path(tempfile.mkdtemp()) / "glossary.jsonl"
        self.records.write_text(
            "\n".join(
                [
                    json.dumps({"src": "neural network", "dst": "mạng nơ-ron"}),
                    json.dumps({"src": "a <b0></b0> b", "dst": "a <b9></b9> b"}),
                ]
            ),
            encoding="utf-8",
        )
        os.environ["LAYOUTLINGUA_GLOSSARY"] = str(self.records)

    def tearDown(self) -> None:
        converter_module._glossary_table = self.old_table
        if self.old_env is None:
            os.environ.pop("LAYOUTLINGUA_GLOSSARY", None)
        else:
            os.environ["LAYOUTLINGUA_GLOSSARY"] = self.old_env

    def test_exact_match_hits_and_damaged_placeholders_skipped(self):
        self.assertEqual(apply_glossary("neural network"), "mạng nơ-ron")
        self.assertIsNone(apply_glossary("a <b0></b0> b"))
        self.assertIsNone(apply_glossary("unlisted segment"))


class DeepLXTranslatorTests(unittest.TestCase):
    def _translator(self, **kwargs):
        translator = DeepLXTranslator("en", "zh", **kwargs)
        translator.session.post = self._stub()
        return translator

    @staticmethod
    def _stub(status=200, payload=None):
        def post(*args, **kwargs):
            response = SimpleNamespace(status_code=status, _payload=payload)
            def raise_for_status():
                if status != 200:
                    error = requests.HTTPError(f"{status} error")
                    error.response = response
                    raise error
            def json():
                if isinstance(payload, Exception):
                    raise payload
                return payload
            response.raise_for_status = raise_for_status
            response.json = json
            return response
        return post

    def test_success_parses_data_and_maps_languages(self):
        translator = self._translator()
        translator.session.post = self._stub(
            payload={"code": 200, "data": "你好", "method": "Free"}
        )
        self.assertEqual(translator.do_translate("Hello"), "你好")
        self.assertEqual(translator._target_code(), "ZH")

    def test_overlong_segment_refused(self):
        translator = self._translator()
        with self.assertRaises(SegmentTooLongError):
            translator.do_translate("x" * 1501)

    def test_429_raises_transient_http_error(self):
        from pdf2zh.converter import _is_transient_translation_error
        translator = self._translator()
        translator.session.post = self._stub(status=429, payload={"code": 429})
        with self.assertRaises(requests.HTTPError) as context:
            translator.do_translate("Hello")
        self.assertEqual(context.exception.response.status_code, 429)
        self.assertTrue(
            _is_transient_translation_error(context.exception)
        )

    def test_non_200_payload_rejected(self):
        translator = self._translator()
        translator.session.post = self._stub(
            payload={"code": 400, "message": "bad tag_handling"}
        )
        with self.assertRaises(RuntimeError):
            translator.do_translate("Hello")

    def test_endpoint_defaults_and_env_override(self):
        self.assertEqual(
            DeepLXTranslator("en", "vi").endpoint, "http://localhost:1188/translate"
        )
        os.environ["DEEPLX_ENDPOINT"] = "http://example.invalid:1188/translate"
        try:
            self.assertEqual(
                DeepLXTranslator("en", "vi").endpoint,
                "http://example.invalid:1188/translate",
            )
        finally:
            del os.environ["DEEPLX_ENDPOINT"]


class LayoutCacheTests(unittest.TestCase):
    def _layout(self):
        boxes = [
            SimpleNamespace(
                xyxy=np.array([10.0, 20.0, 30.0, 40.0]),
                conf=np.float32(0.9),
                cls=np.float32(1.0),
            ),
            SimpleNamespace(
                xyxy=np.array([50.0, 60.0, 70.0, 80.0]),
                conf=np.float32(0.5),
                cls=np.float32(0.0),
            ),
        ]
        return SimpleNamespace(boxes=boxes, names={0: "abandon", 1: "text"})

    def test_layout_round_trip_preserves_boxes(self):
        from pdf2zh.high_level import _decode_page_layout, _encode_page_layout
        decoded = _decode_page_layout(_encode_page_layout(self._layout()))
        self.assertEqual(decoded.names, {0: "abandon", 1: "text"})
        self.assertEqual(len(decoded.boxes), 2)
        self.assertAlmostEqual(decoded.boxes[0].xyxy[0], 10.0)
        self.assertAlmostEqual(decoded.boxes[1].conf, 0.5)

    def test_corrupt_layout_cache_falls_back(self):
        from pdf2zh.high_level import _decode_page_layout
        self.assertIsNone(_decode_page_layout("not-json"))
        self.assertIsNone(_decode_page_layout('{"names": {}, "rows": [[1, 2]]}'))
        self.assertIsNone(_decode_page_layout('{"names": {}}'))
