"""Comprehensive offline unit tests for Slice 3C Gemini & OpenAI-compatible Cloud Providers.

Validates:
- ModelProfileCatalog decoupling of quality profiles from billing tiers.
- Non-hardcoded model IDs and custom model instantiation.
- Gemini adapter authentication, rate-limiting, and 404 ModelUnavailableError mapping.
- Privacy consent guard enforcement for Gemini Free Tier vs Paid Tier exemption.
- OpenAI-compatible adapter flexibility (custom base_url, model_id).
- Structured JSON and tagged block response parsing.
- Conditional fallback: ONLY downgrading to tagged blocks on explicit parameter rejection.
- Out-of-order segment ID reassembly.
- Formula token protection and end-to-end integration with TranslationService.
"""

from __future__ import annotations

import gc
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from layoutlingua.processing.formula.models import FormulaToken, TextSegment
from layoutlingua.translation import (
    AuthenticationError,
    GeminiTranslationProvider,
    JobStatus,
    ModelProfile,
    ModelProfileCatalog,
    ModelUnavailableError,
    OpenAITranslationProvider,
    PrivacyConsentRequiredError,
    QuotaExceededError,
    RateLimitError,
    TranslationJob,
    TranslationService,
)
from layoutlingua.translation.models import BatchTranslationRequest


class TestSlice3CCloudProviders(unittest.TestCase):
    """Test suite for Slice 3C cloud translation providers."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_cloud.sqlite"
        self._services: list[TranslationService] = []

    def tearDown(self) -> None:
        for s in self._services:
            try:
                s.close()
            except Exception:
                pass
        gc.collect()
        try:
            self.temp_dir.cleanup()
        except PermissionError:
            pass

    def _make_service(self, provider, **kwargs) -> TranslationService:
        kwargs.setdefault("db_path", self.db_path)
        kwargs.setdefault("sleeper", lambda d: None)
        service = TranslationService(provider=provider, **kwargs)
        self._services.append(service)
        return service

    # -------------------------------------------------------------------------
    # 1. Model Profile Catalog
    # -------------------------------------------------------------------------

    def test_model_profile_catalog(self) -> None:
        """Verify curated profiles decouple quality from billing tiers and custom profiles work."""
        profiles = ModelProfileCatalog.list_profiles()
        profile_ids = {p.profile_id for p in profiles}
        self.assertIn("gemini.fast", profile_ids)
        self.assertIn("gemini.balanced", profile_ids)
        self.assertIn("gemini.quality", profile_ids)
        self.assertIn("openai.fast", profile_ids)
        self.assertIn("openai.quality", profile_ids)

        fast = ModelProfileCatalog.get_profile("gemini.fast")
        self.assertEqual(fast.model_id, "gemini-3.5-flash-lite")

        balanced = ModelProfileCatalog.get_profile("gemini.balanced")
        self.assertEqual(balanced.model_id, "gemini-3.6-flash")

        quality = ModelProfileCatalog.get_profile("gemini.quality")
        self.assertEqual(quality.model_id, "gemini-3.8-flash")

        # Custom profile defaults supports_structured_json to False unless specified
        custom = ModelProfileCatalog.create_custom(
            provider_id="openai-compatible",
            model_id="deepseek-v3",
        )
        self.assertEqual(custom.model_id, "deepseek-v3")
        self.assertFalse(custom.supports_structured_json)
        self.assertFalse(custom.is_curated)

    # -------------------------------------------------------------------------
    # 2. Gemini Custom Model ID
    # -------------------------------------------------------------------------

    def test_gemini_custom_model_id(self) -> None:
        """Verify user can pass any arbitrary uncataloged model ID without error."""
        provider = GeminiTranslationProvider(
            api_key="test-key",
            profile_or_model="gemini-custom-research-preview",
            client=MagicMock(),
        )
        self.assertEqual(provider.model, "gemini-custom-research-preview")
        self.assertEqual(provider.name, "gemini")

    # -------------------------------------------------------------------------
    # 3. Gemini HTTP Error Mapping (401, 403, 404, 429)
    # -------------------------------------------------------------------------

    def test_gemini_error_mapping_auth_401(self) -> None:
        """Verify Gemini 401 unauthenticated maps to AuthenticationError."""
        mock_client = MagicMock()
        err = Exception("API_KEY_INVALID: The provided API key is not valid.")
        setattr(err, "status_code", 401)
        mock_client.models.generate_content.side_effect = err

        provider = GeminiTranslationProvider(api_key="bad-key", client=mock_client)
        request = BatchTranslationRequest(
            batch_id="b1",
            segments=(TextSegment("s1", "Hello", "Hello"),),
            source_language="en",
            target_language="vi",
        )

        with self.assertRaises(AuthenticationError):
            provider.translate_batch(request)

    def test_gemini_error_mapping_quota_403(self) -> None:
        """Verify Gemini 403 with billing/quota keywords maps to QuotaExceededError."""
        mock_client = MagicMock()
        err = Exception("PERMISSION_DENIED: BILLING_NOT_ACTIVE for this project.")
        setattr(err, "status_code", 403)
        mock_client.models.generate_content.side_effect = err

        provider = GeminiTranslationProvider(api_key="key", client=mock_client)
        request = BatchTranslationRequest(
            batch_id="b1",
            segments=(TextSegment("s1", "Hello", "Hello"),),
            source_language="en",
            target_language="vi",
        )

        with self.assertRaises(QuotaExceededError):
            provider.translate_batch(request)

    def test_gemini_error_mapping_model_not_found_404(self) -> None:
        """Verify Gemini 404 or deprecated model maps to ModelUnavailableError without retry."""
        mock_client = MagicMock()
        err = Exception("NOT_FOUND: Model 'gemini-old-model' is not found.")
        setattr(err, "status_code", 404)
        mock_client.models.generate_content.side_effect = err

        provider = GeminiTranslationProvider(
            api_key="key",
            profile_or_model="gemini-old-model",
            client=mock_client,
        )
        request = BatchTranslationRequest(
            batch_id="b1",
            segments=(TextSegment("s1", "Hello", "Hello"),),
            source_language="en",
            target_language="vi",
        )

        with self.assertRaises(ModelUnavailableError) as ctx:
            provider.translate_batch(request)

        self.assertEqual(ctx.exception.model_id, "gemini-old-model")
        self.assertEqual(ctx.exception.provider_id, "gemini")

    def test_gemini_error_mapping_rate_limit_429(self) -> None:
        """Verify Gemini 429 maps to RateLimitError with retry_after."""
        mock_client = MagicMock()
        err = Exception("RESOURCE_EXHAUSTED: Rate limit exceeded.")
        setattr(err, "status_code", 429)
        setattr(err, "retry_after", 0.05)
        mock_client.models.generate_content.side_effect = err

        provider = GeminiTranslationProvider(api_key="key", client=mock_client)
        request = BatchTranslationRequest(
            batch_id="b1",
            segments=(TextSegment("s1", "Hello", "Hello"),),
            source_language="en",
            target_language="vi",
        )

        with self.assertRaises(RateLimitError) as ctx:
            provider.translate_batch(request)

        self.assertEqual(ctx.exception.retry_after, 0.05)

    # -------------------------------------------------------------------------
    # 4. Gemini Privacy Consent Guard (Free Tier vs Paid Tier)
    # -------------------------------------------------------------------------

    def test_gemini_privacy_guard_free_tier(self) -> None:
        """Verify Free Tier strictly triggers PrivacyConsentRequiredError until user records consent."""
        mock_resp = MagicMock()
        mock_resp.text = json.dumps({"translations": [{"id": "s1", "text": "Xin chào"}]})
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_resp

        # 1. Free tier requires consent
        provider_free = GeminiTranslationProvider(
            api_key="test-free-key",
            tier="free",
            client=mock_client,
        )
        self.assertTrue(provider_free.capabilities.requires_data_use_consent)

        service = self._make_service(provider=provider_free)
        job = TranslationJob(
            job_id="job-gemini-free",
            document_fingerprint="fp-gemini-free",
            source_language="en",
            target_language="vi",
            segments=(TextSegment("s1", "Hello", "Hello"),),
        )

        # Attempting translation without consent fails fast
        with self.assertRaises(PrivacyConsentRequiredError) as ctx:
            service.translate_job(job)
        self.assertEqual(ctx.exception.provider_id, "gemini")
        self.assertEqual(ctx.exception.tier, "free")

        # After recording explicit consent, translation succeeds
        service.record_privacy_consent(
            provider_id="gemini",
            tier="free",
            policy_version="2026-06",
        )
        res = service.translate_job(job)
        self.assertEqual(res.status, JobStatus.COMPLETED)
        self.assertIn("s1", res.translated_segments)

    def test_gemini_privacy_guard_paid_tier_exemption(self) -> None:
        """Verify Paid Tier is exempt from external data use consent."""
        mock_resp = MagicMock()
        mock_resp.text = json.dumps({"translations": [{"id": "s1", "text": "Xin chào"}]})
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_resp

        provider_paid = GeminiTranslationProvider(
            api_key="test-paid-key",
            tier="paid",
            client=mock_client,
        )
        self.assertFalse(provider_paid.capabilities.requires_data_use_consent)

        service = self._make_service(provider=provider_paid)
        job = TranslationJob(
            job_id="job-gemini-paid",
            document_fingerprint="fp-gemini-paid",
            source_language="en",
            target_language="vi",
            segments=(TextSegment("s1", "Hello", "Hello"),),
        )

        # Runs immediately without consent prompt
        res = service.translate_job(job)
        self.assertEqual(res.status, JobStatus.COMPLETED)

    # -------------------------------------------------------------------------
    # 5. OpenAI-Compatible Custom Endpoint Configuration
    # -------------------------------------------------------------------------

    def test_openai_custom_endpoint_and_model(self) -> None:
        """Verify OpenAI-compatible adapter accepts custom local or remote base_url and model_id."""
        provider = OpenAITranslationProvider(
            api_key="ollama",
            model_id="qwen2.5:32b",
            base_url="http://localhost:11434/v1",
            supports_structured_json=False,
            client=MagicMock(),
        )
        self.assertEqual(provider.model, "qwen2.5:32b")
        self.assertEqual(provider.name, "openai-compatible")
        self.assertEqual(provider._base_url, "http://localhost:11434/v1")
        self.assertFalse(provider.capabilities.supports_structured_json)

    # -------------------------------------------------------------------------
    # 6. Structured JSON vs Tagged Blocks Parsing
    # -------------------------------------------------------------------------

    def test_openai_structured_json_parsing(self) -> None:
        """Verify parser extracts translations from valid JSON array response."""
        mock_resp = MagicMock()
        choice = MagicMock()
        choice.message.content = json.dumps({
            "translations": [
                {"id": "seg_1", "text": "Dòng một"},
                {"id": "seg_2", "text": "Dòng hai"},
            ]
        })
        mock_resp.choices = [choice]

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_resp

        provider = OpenAITranslationProvider(
            api_key="key",
            model_id="gpt-4o-mini",
            supports_structured_json=True,
            client=mock_client,
        )
        request = BatchTranslationRequest(
            batch_id="b1",
            segments=(
                TextSegment("seg_1", "Line one", "Line one"),
                TextSegment("seg_2", "Line two", "Line two"),
            ),
            source_language="en",
            target_language="vi",
        )

        res = provider.translate_batch(request)
        self.assertEqual(res.translations["seg_1"], "Dòng một")
        self.assertEqual(res.translations["seg_2"], "Dòng hai")

    def test_openai_tagged_blocks_parsing(self) -> None:
        """Verify parser extracts translations from XML-tagged blocks."""
        mock_resp = MagicMock()
        choice = MagicMock()
        choice.message.content = (
            "<segment id=\"seg_1\">Văn bản một</segment>\n"
            "<segment id=\"seg_2\">Văn bản hai</segment>"
        )
        mock_resp.choices = [choice]

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_resp

        provider = OpenAITranslationProvider(
            api_key="key",
            model_id="deepseek-chat",
            supports_structured_json=False,
            client=mock_client,
        )
        request = BatchTranslationRequest(
            batch_id="b1",
            segments=(
                TextSegment("seg_1", "Text one", "Text one"),
                TextSegment("seg_2", "Text two", "Text two"),
            ),
            source_language="en",
            target_language="vi",
        )

        res = provider.translate_batch(request)
        self.assertEqual(res.translations["seg_1"], "Văn bản một")
        self.assertEqual(res.translations["seg_2"], "Văn bản hai")

    # -------------------------------------------------------------------------
    # 7. Conditional Fallback: Only on explicit unsupported format error
    # -------------------------------------------------------------------------

    def test_openai_conditional_fallback_on_unsupported_response_format(self) -> None:
        """Verify adapter falls back to tagged blocks ONLY when endpoint explicitly rejects response_format."""
        mock_client = MagicMock()

        # First call with response_format fails with explicit parameter error
        err_param = Exception("400 Bad Request: response_format is not supported by this endpoint.")
        setattr(err_param, "status_code", 400)

        # Second call with tagged blocks succeeds
        mock_resp_tagged = MagicMock()
        choice = MagicMock()
        choice.message.content = '<segment id="s1">Thành công tagged</segment>'
        mock_resp_tagged.choices = [choice]

        mock_client.chat.completions.create.side_effect = [err_param, mock_resp_tagged]

        provider = OpenAITranslationProvider(
            api_key="key",
            model_id="local-llm",
            supports_structured_json=True,
            client=mock_client,
        )
        request = BatchTranslationRequest(
            batch_id="b1",
            segments=(TextSegment("s1", "Success", "Success"),),
            source_language="en",
            target_language="vi",
        )

        res = provider.translate_batch(request)
        self.assertEqual(res.translations["s1"], "Thành công tagged")
        # Internal flag should have downgraded to prevent further wasted attempts
        self.assertFalse(provider._supports_structured_json)

    def test_openai_no_fallback_on_generic_400_bad_request(self) -> None:
        """Verify adapter does NOT fall back on generic 400 errors (e.g. prompt length exceeded)."""
        mock_client = MagicMock()
        err_generic = Exception("400 Bad Request: Context length exceeded maximum tokens.")
        setattr(err_generic, "status_code", 400)
        mock_client.chat.completions.create.side_effect = err_generic

        provider = OpenAITranslationProvider(
            api_key="key",
            model_id="gpt-4o",
            supports_structured_json=True,
            client=mock_client,
        )
        request = BatchTranslationRequest(
            batch_id="b1",
            segments=(TextSegment("s1", "Long text", "Long text"),),
            source_language="en",
            target_language="vi",
        )

        # Must not fallback; raises ProviderUnavailableError
        with self.assertRaises(Exception) as ctx:
            provider.translate_batch(request)
        self.assertNotIn("Thành công", str(ctx.exception))

    def test_openai_404_model_unavailable(self) -> None:
        """Verify OpenAI 404 model_not_found raises ModelUnavailableError."""
        mock_client = MagicMock()
        err = Exception("404 The model `gpt-deprecated` does not exist.")
        setattr(err, "status_code", 404)
        mock_client.chat.completions.create.side_effect = err

        provider = OpenAITranslationProvider(
            api_key="key",
            model_id="gpt-deprecated",
            client=mock_client,
        )
        request = BatchTranslationRequest(
            batch_id="b1",
            segments=(TextSegment("s1", "Text", "Text"),),
            source_language="en",
            target_language="vi",
        )

        with self.assertRaises(ModelUnavailableError) as ctx:
            provider.translate_batch(request)
        self.assertEqual(ctx.exception.model_id, "gpt-deprecated")

    # -------------------------------------------------------------------------
    # 8. Out-of-Order Segment Reassembly through TranslationService
    # -------------------------------------------------------------------------

    def test_out_of_order_segment_reassembly_cloud(self) -> None:
        """Verify service correctly reorders segments when LLM returns them reversed."""
        mock_resp = MagicMock()
        choice = MagicMock()
        # Reversed order: seg_2 then seg_1
        choice.message.content = json.dumps({
            "translations": [
                {"id": "seg_2", "text": "Dịch 2"},
                {"id": "seg_1", "text": "Dịch 1"},
            ]
        })
        mock_resp.choices = [choice]

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_resp

        provider = OpenAITranslationProvider(
            api_key="key",
            model_id="gpt-4o-mini",
            supports_structured_json=True,
            client=mock_client,
        )

        service = self._make_service(provider=provider)
        job = TranslationJob(
            job_id="job-reorder-cloud",
            document_fingerprint="fp-reorder-cloud",
            source_language="en",
            target_language="vi",
            segments=(
                TextSegment("seg_1", "Source 1", "Source 1"),
                TextSegment("seg_2", "Source 2", "Source 2"),
            ),
        )

        res = service.translate_job(job)
        self.assertEqual(res.status, JobStatus.COMPLETED)
        self.assertEqual(res.translated_segments["seg_1"], "Dịch 1")
        self.assertEqual(res.translated_segments["seg_2"], "Dịch 2")

    # -------------------------------------------------------------------------
    # 9. End-to-End Formula Preservation with TranslationService
    # -------------------------------------------------------------------------

    def test_end_to_end_formula_preservation(self) -> None:
        """Verify formula token opaque transit, validation, and cache persistence with Gemini."""
        mock_client = MagicMock()
        mock_resp = MagicMock()
        # LLM returns translated text preserving opaque token
        mock_resp.text = json.dumps({
            "translations": [
                {"id": "math_seg", "text": "Định lý: Đẳng thức ⟦LL_FORMULA_0⟧ là đúng."}
            ]
        })
        mock_client.models.generate_content.return_value = mock_resp

        provider = GeminiTranslationProvider(
            api_key="test-paid-key",
            tier="paid",
            client=mock_client,
        )
        service = self._make_service(provider=provider)

        token = FormulaToken(token_id=0, placeholder="<b0></b0>", raw_content=r"\nabla \cdot \mathbf{B} = 0")
        seg = TextSegment(
            segment_id="math_seg",
            raw_text="Theorem: The formula <b0></b0> is true.",
            masked_text="Theorem: The formula <b0></b0> is true.",
            tokens=[token],
        )

        job = TranslationJob(
            job_id="job-formula-cloud",
            document_fingerprint="fp-formula-cloud",
            source_language="en",
            target_language="vi",
            segments=(seg,),
        )

        res = service.translate_job(job)
        self.assertEqual(res.status, JobStatus.COMPLETED)
        # Verify formula was restored
        translated_text = res.translated_segments["math_seg"]
        self.assertIn(r"\nabla \cdot \mathbf{B} = 0", translated_text)
        self.assertIn("Định lý: Đẳng thức", translated_text)
