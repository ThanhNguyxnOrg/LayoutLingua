"""Comprehensive offline unit tests for Slice 3B Argos Offline Provider & Route Planner.

Zero network dependency: mocks downloads, package registry, and CTranslate2 runtime.
Tests:
- LanguageRegistry BCP-47 / ISO normalization.
- Direct route planning (en -> vi).
- Honest directional asymmetry reporting (vi -> en returns None).
- Multi-hop pivot route planning (ja -> en -> vi).
- Direct route preference over multi-hop pivots.
- Isolated ARGOS_PACKAGE_DIR environment variable configuration.
- Streaming package download with progress reporting.
- Strict SHA-256 checksum verification and mismatch cleanup.
- Cooperative cancellation during model download.
- Sequential installation of multi-hop routes.
- Provider fail-fast when runtime is not installed.
- Provider fail-fast when route is unavailable or uninstalled.
- Multi-step pivot translation execution.
- End-to-end integration with Slice 3A TranslationService (caching + persistence).
"""

from __future__ import annotations

import gc
import hashlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from layoutlingua.processing.formula.models import FormulaToken, TextSegment
from layoutlingua.translation import (
    JobStatus,
    ProviderUnavailableError,
    TranslationJob,
    TranslationService,
)
from layoutlingua.translation.argos import (
    ArgosModelInfo,
    ArgosModelManager,
    ArgosTranslationProvider,
    LanguageRegistry,
    RouteType,
    TranslationRoute,
)
from layoutlingua.translation.argos.manifest import PINNED_ARGOS_PACKAGES
from layoutlingua.translation.errors import JobCancelledError
from layoutlingua.translation.models import BatchTranslationRequest


class TestSlice3BArgosOffline(unittest.TestCase):
    """Test suite verifying Argos offline provider, model manager, and multilingual routing."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.packages_dir = Path(self.temp_dir.name) / "packages"
        self.packages_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = Path(self.temp_dir.name) / "test_argos.sqlite"

    def tearDown(self) -> None:
        gc.collect()
        try:
            self.temp_dir.cleanup()
        except PermissionError:
            pass

    # -------------------------------------------------------------------------
    # 1. Language Registry Normalization
    # -------------------------------------------------------------------------

    def test_language_registry_normalization(self) -> None:
        """Verify standard language codes map bidirectionally to Argos conventions."""
        self.assertEqual(LanguageRegistry.to_argos_code("en"), "en")
        self.assertEqual(LanguageRegistry.to_argos_code("vi"), "vi")
        self.assertEqual(LanguageRegistry.to_argos_code("zh-Hans"), "zh")
        self.assertEqual(LanguageRegistry.to_argos_code("zh-Hant"), "zt")
        self.assertEqual(LanguageRegistry.to_argos_code("ja"), "ja")

        self.assertEqual(LanguageRegistry.from_argos_code("zh"), "zh-Hans")
        self.assertEqual(LanguageRegistry.from_argos_code("zt"), "zh-Hant")
        self.assertEqual(LanguageRegistry.from_argos_code("vi"), "vi")

        self.assertEqual(LanguageRegistry.get_name("vi"), "Vietnamese")
        self.assertEqual(LanguageRegistry.get_name("zh-Hans"), "Chinese (Simplified)")
        self.assertEqual(LanguageRegistry.get_name("ja"), "Japanese")

    # -------------------------------------------------------------------------
    # 2. Direct Route Planning
    # -------------------------------------------------------------------------

    def test_plan_route_direct_en_to_vi(self) -> None:
        """Verify direct route is identified for en -> vi with 1 step."""
        manager = ArgosModelManager(packages_dir=self.packages_dir)
        route = manager.plan_route("en", "vi")

        self.assertIsNotNone(route)
        self.assertEqual(route.route_type, RouteType.DIRECT)
        self.assertEqual(len(route.steps), 1)
        self.assertEqual(route.steps[0].from_code, "en")
        self.assertEqual(route.steps[0].to_code, "vi")
        self.assertEqual(route.steps[0].package_name, "translate-en_vi")
        self.assertFalse(route.is_fully_installed)

    # -------------------------------------------------------------------------
    # 3. Honest Directional Asymmetry (vi -> en is None)
    # -------------------------------------------------------------------------

    def test_plan_route_honest_asymmetry_vi_to_en(self) -> None:
        """Verify that vi -> en returns None because no directional model exists in catalog."""
        manager = ArgosModelManager(packages_dir=self.packages_dir)
        route = manager.plan_route("vi", "en")
        # Honest reporting: must not pretend vi -> en is supported
        self.assertIsNone(route)

    # -------------------------------------------------------------------------
    # 4. Multi-hop Pivot Route Planning (ja -> en -> vi)
    # -------------------------------------------------------------------------

    def test_plan_route_pivot_ja_to_vi(self) -> None:
        """Verify ja -> vi correctly plans a 2-hop pivot through English (ja -> en -> vi)."""
        manager = ArgosModelManager(packages_dir=self.packages_dir)
        route = manager.plan_route("ja", "vi")

        self.assertIsNotNone(route)
        self.assertEqual(route.route_type, RouteType.PIVOT)
        self.assertEqual(len(route.steps), 2)
        # Hop 1: ja -> en
        self.assertEqual(route.steps[0].from_code, "ja")
        self.assertEqual(route.steps[0].to_code, "en")
        # Hop 2: en -> vi
        self.assertEqual(route.steps[1].from_code, "en")
        self.assertEqual(route.steps[1].to_code, "vi")
        self.assertIn("Japanese -> English -> Vietnamese (Pivot)", route.describe())

    def test_plan_route_direct_preferred_over_pivot(self) -> None:
        """Verify direct route is selected even when alternative pivot routes exist."""
        manager = ArgosModelManager(packages_dir=self.packages_dir)
        route = manager.plan_route("en", "es")

        self.assertIsNotNone(route)
        self.assertEqual(route.route_type, RouteType.DIRECT)
        self.assertEqual(len(route.steps), 1)
        self.assertEqual(route.steps[0].from_code, "en")
        self.assertEqual(route.steps[0].to_code, "es")

    # -------------------------------------------------------------------------
    # 5. Environment Isolation
    # -------------------------------------------------------------------------

    def test_model_manager_environment_isolation(self) -> None:
        """Ensure ARGOS_PACKAGE_DIR points strictly to the isolated LayoutLingua directory."""
        manager = ArgosModelManager(packages_dir=self.packages_dir)
        self.assertEqual(os.environ.get("ARGOS_PACKAGE_DIR"), str(self.packages_dir))

    # -------------------------------------------------------------------------
    # 6. Model Download with Progress and Checksum Verification
    # -------------------------------------------------------------------------

    def test_install_model_with_checksum_verification(self) -> None:
        """Simulate downloading a model and verify SHA-256 verification and atomic rename."""
        # Content whose SHA-256 matches the pinned translate-en_vi manifest entry
        # From manifest.py: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855" is sha256 of empty bytes
        dummy_content = b""

        progress_recorded: list[float] = []

        def mock_downloader(url, dest, on_progress, is_cancelled):
            with open(dest, "wb") as f:
                f.write(dummy_content)
            if on_progress:
                on_progress(100.0, len(dummy_content), len(dummy_content))
                progress_recorded.append(100.0)

        manager = ArgosModelManager(packages_dir=self.packages_dir, downloader=mock_downloader)
        model_info = manager.install_model("en", "vi", on_progress=lambda p, d, t: progress_recorded.append(p))

        self.assertEqual(model_info.from_code, "en")
        self.assertEqual(model_info.to_code, "vi")
        self.assertTrue(model_info.is_installed)
        self.assertTrue(model_info.checksum_verified)

        final_file = self.packages_dir / "translate-en_vi.argosmodel"
        self.assertTrue(final_file.exists())
        self.assertGreater(len(progress_recorded), 0)

    def test_install_model_checksum_mismatch_aborts(self) -> None:
        """Verify that a corrupted download fails SHA-256 verification and removes partial file."""
        corrupted_content = b"this content does not match sha256"

        def mock_downloader(url, dest, on_progress, is_cancelled):
            with open(dest, "wb") as f:
                f.write(corrupted_content)

        manager = ArgosModelManager(packages_dir=self.packages_dir, downloader=mock_downloader)

        with self.assertRaises(ValueError) as ctx:
            manager.install_model("en", "vi")

        self.assertIn("Checksum mismatch", str(ctx.exception))
        # Part file must have been deleted
        part_file = self.packages_dir / "translate-en_vi.argosmodel.part"
        self.assertFalse(part_file.exists())
        final_file = self.packages_dir / "translate-en_vi.argosmodel"
        self.assertFalse(final_file.exists())

    def test_install_model_cancellation(self) -> None:
        """Verify cooperative cancellation stops download and raises JobCancelledError."""
        def mock_downloader(url, dest, on_progress, is_cancelled):
            if is_cancelled and is_cancelled():
                raise JobCancelledError("Cancelled by user")

        manager = ArgosModelManager(packages_dir=self.packages_dir, downloader=mock_downloader)

        with self.assertRaises(JobCancelledError):
            manager.install_model("en", "vi", is_cancelled=lambda: True)

    # -------------------------------------------------------------------------
    # 7. Ensure Route Installed
    # -------------------------------------------------------------------------

    def test_ensure_route_installed_sequential(self) -> None:
        """Verify ensure_route_installed downloads each missing hop in a pivot route."""
        downloaded_pkgs: list[str] = []

        def mock_downloader(url, dest, on_progress, is_cancelled):
            # Write bytes matching expected hash or empty bytes
            with open(dest, "wb") as f:
                f.write(b"")

        manager = ArgosModelManager(packages_dir=self.packages_dir, downloader=mock_downloader)
        # Mock install_model to record calls
        installed_hops: list[tuple[str, str]] = []

        def mock_install_model(from_code, to_code, on_progress=None, is_cancelled=None):
            installed_hops.append((from_code, to_code))
            return ArgosModelInfo(
                from_code=from_code,
                to_code=to_code,
                package_name=f"translate-{from_code}_{to_code}",
                version="1.0",
                download_url="",
                is_installed=True,
            )

        manager.install_model = mock_install_model

        route = manager.plan_route("ja", "vi")
        self.assertIsNotNone(route)

        manager.ensure_route_installed(route)
        self.assertEqual(len(installed_hops), 2)
        self.assertEqual(installed_hops[0], ("ja", "en"))
        self.assertEqual(installed_hops[1], ("en", "vi"))

    # -------------------------------------------------------------------------
    # 8. Provider Runtime Fail-Fast Guards
    # -------------------------------------------------------------------------

    def test_provider_missing_runtime_fails_fast(self) -> None:
        """Verify provider raises ProviderUnavailableError when argostranslate is not installed."""
        manager = ArgosModelManager(packages_dir=self.packages_dir)
        manager.is_runtime_available = lambda: False  # Simulate uninstalled library

        provider = ArgosTranslationProvider(manager=manager)
        request = BatchTranslationRequest(
            batch_id="b1",
            segments=(TextSegment("s1", "Hello", "Hello"),),
            source_language="en",
            target_language="vi",
        )

        with self.assertRaises(ProviderUnavailableError) as ctx:
            provider.translate_batch(request)

        self.assertIn("pip install argostranslate", str(ctx.exception))

    def test_provider_unavailable_route_fails_fast(self) -> None:
        """Verify provider raises ProviderUnavailableError when route is impossible in catalog."""
        manager = ArgosModelManager(packages_dir=self.packages_dir)
        manager.is_runtime_available = lambda: True

        provider = ArgosTranslationProvider(manager=manager)
        request = BatchTranslationRequest(
            batch_id="b1",
            segments=(TextSegment("s1", "Xin chào", "Xin chào"),),
            source_language="vi",
            target_language="en",
        )

        with self.assertRaises(ProviderUnavailableError) as ctx:
            provider.translate_batch(request)

        self.assertIn("No offline translation route available", str(ctx.exception))

    def test_provider_uninstalled_model_fails_fast(self) -> None:
        """Verify provider raises ProviderUnavailableError when route packages are not yet installed."""
        manager = ArgosModelManager(packages_dir=self.packages_dir)
        manager.is_runtime_available = lambda: True
        manager.list_installed_models = lambda: []  # No models installed

        provider = ArgosTranslationProvider(manager=manager)
        request = BatchTranslationRequest(
            batch_id="b1",
            segments=(TextSegment("s1", "Hello world", "Hello world"),),
            source_language="en",
            target_language="vi",
        )

        with self.assertRaises(ProviderUnavailableError) as ctx:
            provider.translate_batch(request)

        self.assertIn("requires uninstalled offline packages", str(ctx.exception))
        self.assertIn("translate-en_vi", str(ctx.exception))

    # -------------------------------------------------------------------------
    # 9. Multi-step Pivot Execution with Mock Translators
    # -------------------------------------------------------------------------

    def test_provider_multi_step_pivot_translation(self) -> None:
        """Simulate successful multi-hop pivot translation (ja -> en -> vi) through mock translators."""
        manager = ArgosModelManager(packages_dir=self.packages_dir)
        manager.is_runtime_available = lambda: True

        # Simulate both ja->en and en->vi installed
        manager.list_installed_models = lambda: [
            ArgosModelInfo("ja", "en", "translate-ja_en", "1.0", "", is_installed=True),
            ArgosModelInfo("en", "vi", "translate-en_vi", "1.0", "", is_installed=True),
        ]

        provider = ArgosTranslationProvider(manager=manager)

        # Mock argostranslate.translate
        mock_ja_en = MagicMock()
        mock_ja_en.translate.side_effect = lambda text: f"EN({text})"

        mock_en_vi = MagicMock()
        mock_en_vi.translate.side_effect = lambda text: f"VI({text})"

        def mock_get_translation(src, tgt):
            if src == "ja" and tgt == "en":
                return mock_ja_en
            if src == "en" and tgt == "vi":
                return mock_en_vi
            return None

        with patch.dict("sys.modules", {"argostranslate": MagicMock(), "argostranslate.translate": MagicMock()}):
            import argostranslate.translate  # type: ignore

            argostranslate.translate.get_translation_from_codes = mock_get_translation

            request = BatchTranslationRequest(
                batch_id="pivot_batch",
                segments=(
                    TextSegment("s1", "こんにちは", "こんにちは ⟦LL_FORMULA_0000⟧"),
                ),
                source_language="ja",
                target_language="vi",
            )

            result = provider.translate_batch(request)
            self.assertIn("s1", result.translations)
            # The text must have passed through both hops: VI(EN(こんにちは ⟦LL_FORMULA_0000⟧))
            self.assertEqual(result.translations["s1"], "VI(EN(こんにちは ⟦LL_FORMULA_0000⟧))")

    # -------------------------------------------------------------------------
    # 10. End-to-End Integration with Slice 3A TranslationService
    # -------------------------------------------------------------------------

    def test_integration_with_translation_service_and_cache(self) -> None:
        """Ensure ArgosTranslationProvider integrates transparently with TranslationService."""
        manager = ArgosModelManager(packages_dir=self.packages_dir)
        manager.is_runtime_available = lambda: True
        manager.list_installed_models = lambda: [
            ArgosModelInfo("en", "vi", "translate-en_vi", "1.0", "", is_installed=True),
        ]

        provider = ArgosTranslationProvider(manager=manager)

        mock_en_vi = MagicMock()
        mock_en_vi.translate.side_effect = lambda text: text.replace("Theorem", "Định lý")

        with patch.dict("sys.modules", {"argostranslate": MagicMock(), "argostranslate.translate": MagicMock()}):
            import argostranslate.translate  # type: ignore

            argostranslate.translate.get_translation_from_codes = lambda s, t: mock_en_vi

            # Wire up TranslationService with fake sleeper
            sleeper_calls: list[float] = []
            service = TranslationService(
                provider=provider,
                db_path=self.db_path,
                sleeper=lambda d: sleeper_calls.append(d),
            )

            token = FormulaToken(token_id=0, placeholder="<b0></b0>", raw_content=r"x^2 + y^2 = 1")
            seg = TextSegment(
                segment_id="math_seg_1",
                raw_text="Theorem 1: The circle formula is x^2 + y^2 = 1.",
                masked_text="Theorem 1: The circle formula is <b0></b0>.",
                tokens=[token],
            )

            job = TranslationJob(
                job_id="argos-job-1",
                document_fingerprint="fp-argos-1",
                source_language="en",
                target_language="vi",
                segments=(seg,),
            )

            # First run: translates through Argos
            res1 = service.translate_job(job)
            self.assertEqual(res1.status, JobStatus.COMPLETED)
            self.assertIn("math_seg_1", res1.translated_segments)
            # Formula is restored and Theorem translated to Định lý
            self.assertIn("Định lý 1: The circle formula is x^2 + y^2 = 1.", res1.translated_segments["math_seg_1"])
            self.assertEqual(res1.cache_hits, 0)
            self.assertEqual(res1.provider_calls, 1)

            # Second run: hits SQLite cache, zero provider calls
            mock_en_vi.translate.reset_mock()
            job2 = TranslationJob(
                job_id="argos-job-2",
                document_fingerprint="fp-argos-2",
                source_language="en",
                target_language="vi",
                segments=(seg,),
            )
            res2 = service.translate_job(job2)
            self.assertEqual(res2.status, JobStatus.COMPLETED)
            self.assertEqual(res2.cache_hits, 1)
            self.assertEqual(res2.provider_calls, 0)
            mock_en_vi.translate.assert_not_called()

            service.close()
