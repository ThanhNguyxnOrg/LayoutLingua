"""Comprehensive regression tests for multilingual typesetting, syllabic hyphenation,
narrow stacked label expansion, vertical rotated condensation, and post-merge clearance.

Covers:
1. Phonological syllabic hyphenation (`TextFitTester.hyphenate_word`) across Romance/Germanic words.
2. Narrow multi-line column header fitting (`MIPS_Green_Sheet.pdf` Page 2: `p2_block_20_0`, `p2_block_27`, `p2_block_35`).
3. Narrow stacked label leftward expansion & >=70% font floor (`Sotaytoanhoc.pdf` Page 7: `p7_block_9_1` "phút giây" -> "minutos segundos").
4. Post-merge LayoutRegion synchronization & self-collision immunity (`Sotaytoanhoc.pdf` Page 38: `p38_block_37`).
5. Adjacent untranslated text line boundary trimming (`MIPS_Green_Sheet.pdf` Page 2: `IEEE 754 FLOATING-POINT` above `STANDARD` in German).
6. 90-degree vertical rotated margin text condensation (`MIPS_Green_Sheet.pdf` Pages 1 & 2 in Japanese and German).
7. Multilingual end-to-end page transactions across `en`, `vi`, `fr`, `de`, `es`, `pt`, `zh`, `ja`, `ko`.
"""

from __future__ import annotations

import unittest
import pymupdf

from layoutlingua.core.ir import (
    DocumentIR,
    GlyphSpan,
    LayoutRegion,
    PageGeometry,
    PageIR,
    TextBlock,
)
from layoutlingua.typesetting.engine import TypesetEngine, compute_expanded_layout_box
from layoutlingua.typesetting.fitting import TextFitTester
from layoutlingua.typesetting.fonts import FontManager
from layoutlingua.typesetting.models import BlockFittingStatus, OverflowCause, TypesetOptions
from layoutlingua.typesetting.protection import ClearancePlanner


class TestMultilingualLayoutAndHyphenation(unittest.TestCase):
    """Test suite verifying geometric and typographic fixes across all supported languages."""

    def setUp(self) -> None:
        self.fm = FontManager()
        self.tester = TextFitTester(font_manager=self.fm)
        self.options = TypesetOptions()
        self.engine = TypesetEngine(self.options, font_manager=self.fm)

    def test_syllabic_hyphenation_phonological_boundaries(self) -> None:
        """Verify that hyphenate_word splits at valid syllable boundaries without 1-char orphans."""
        for word in ("Hexadécimal", "opérationnel", "Caractère", "segundos", "minutos"):
            parts = self.tester.hyphenate_word(word, avail_w=24.0, font_size=6.5)
            self.assertGreaterEqual(len(parts), 2, f"Expected '{word}' to hyphenate at 24pt width")
            reconstructed = "".join(p[:-1] if p.endswith("-") else p for p in parts)
            self.assertEqual(reconstructed, word)
            for part in parts:
                clean = part.rstrip("-")
                self.assertGreaterEqual(len(clean), 2, f"Orphan fragment '{part}' in {parts}")

    def test_narrow_multiline_column_headers_mips_page2(self) -> None:
        """Verify narrow 3-line column headers ('MIPS opcode', 'Hexadecimal') fit in French/Spanish/German."""
        # p2_block_27 / p2_block_35: 17.1pt wide x 23.0pt tall, 7.0pt original font
        rect_hex = (139.8, 65.6, 156.9, 88.6)
        for trans in ("Hexadécimal", "Hexadecimal", "Hexadezimal", "十六进制", "16進数"):
            fits, sz, cause, lines, _ = self.tester.test_fit(
                rect=rect_hex,
                text=trans,
                orig_font_size=7.0,
                options=self.options,
            )
            self.assertTrue(fits, f"Failed to fit '{trans}' in {rect_hex}: {cause}")
            self.assertEqual(cause, OverflowCause.NONE)
            self.assertGreaterEqual(sz / 7.0, 0.70 - 1e-3, f"Shrink ratio < 0.70 for '{trans}'")

        # p2_block_20_0: 20.2pt wide x 15.0pt tall, 7.0pt original font
        rect_opcode = (8.1, 65.6, 28.3, 80.6)
        for trans in ("Code opérationnel MIPS", "Código de operación MIPS", "MIPS-Opcode", "MIPS操作码"):
            fits, sz, cause, lines, _ = self.tester.test_fit(
                rect=rect_opcode,
                text=trans,
                orig_font_size=7.0,
                options=self.options,
            )
            self.assertTrue(fits, f"Failed to fit '{trans}' in {rect_opcode}: {cause}")
            self.assertEqual(cause, OverflowCause.NONE)
            self.assertGreaterEqual(sz / 7.0, 0.70 - 1e-3, f"Shrink ratio < 0.70 for '{trans}'")

    def test_narrow_stacked_label_leftward_expansion_page7(self) -> None:
        """Verify 'phút giây' -> 'minutos segundos' on Page 7 expands leftward and fits at >=70% scale without hyphenation."""
        doc = pymupdf.open()
        page = doc.new_page(width=420.0, height=595.0)
        page.insert_text((124.6, 146.0), "độ", fontsize=12.1)
        page.insert_text((124.6, 164.0), "phút", fontsize=12.1)
        page.insert_text((124.6, 182.0), "giây", fontsize=12.1)
        page.insert_text((148.6, 165.0), "}", fontsize=18.0)
        page.insert_text((155.7, 165.0), "góc phẳng hoặc cung", fontsize=12.1)

        b_left_sym1 = TextBlock(
            block_id="p7_block_10_0_0",
            bbox=(55.6, 155.9, 61.6, 169.3),
            spans=[GlyphSpan(span_id="s_sym1", text="' ", bbox=(55.6, 155.9, 61.6, 169.3), font_name="Times-Roman", font_size=12.0, color=0)],
            block_type="formula",
        )
        b_left_sym2 = TextBlock(
            block_id="p7_block_11",
            bbox=(55.7, 176.3, 63.7, 189.7),
            spans=[GlyphSpan(span_id="s_sym2", text="'' ", bbox=(55.7, 176.3, 63.7, 189.7), font_name="Times-Roman", font_size=12.0, color=0)],
            block_type="formula",
        )
        b_brace = TextBlock(
            block_id="p7_block_8_1_1",
            bbox=(148.6, 136.7, 154.6, 189.7),
            spans=[GlyphSpan(span_id="s_br", text="}", bbox=(148.6, 136.7, 154.6, 189.7), font_name="Symbol", font_size=12.0, color=0)],
            block_type="formula",
        )
        b_deg = TextBlock(
            block_id="p7_block_9_0",
            bbox=(124.6, 134.9, 137.5, 150.4),
            spans=[GlyphSpan(span_id="s_deg", text="độ", bbox=(124.6, 134.9, 137.5, 150.4), font_name="Times-Roman", font_size=12.1, color=0)],
            block_type="text",
        )
        b_min_sec = TextBlock(
            block_id="p7_block_9_1",
            bbox=(124.6, 153.0, 147.6, 186.5),
            spans=[GlyphSpan(span_id="s_ms", text="phút giây", bbox=(124.6, 153.0, 147.6, 186.5), font_name="Times-Roman", font_size=12.1, color=0)],
            block_type="text",
        )
        b_desc = TextBlock(
            block_id="p7_block_9_2",
            bbox=(155.7, 153.0, 260.4, 168.5),
            spans=[GlyphSpan(span_id="s_desc", text="góc phẳng hoặc cung", bbox=(155.7, 153.0, 260.4, 168.5), font_name="Times-Roman", font_size=12.1, color=0)],
            block_type="text",
        )

        all_blocks = [b_left_sym1, b_left_sym2, b_brace, b_deg, b_min_sec, b_desc]
        expanded = compute_expanded_layout_box(
            block_bbox=b_min_sec.bbox,
            page_blocks=all_blocks,
            page_width=420.0,
            current_block_id="p7_block_9_1",
            margin_padding=20.0,
            scratch_page=page,
            orig_font_size=12.1,
        )
        # Must expand leftward to x0 = 92.6, matching p7_block_9_0 ("độ")
        self.assertAlmostEqual(expanded[0], 92.6, places=1)
        self.assertGreaterEqual(expanded[2] - expanded[0], 54.0)

        page_ir = PageIR(
            page_number=1,
            geometry=PageGeometry(width=420.0, height=595.0),
            blocks=all_blocks,
        )
        doc_ir = DocumentIR(doc_id="test_p7", filename="p7.pdf", page_count=1, pages=[page_ir])

        multilingual_cases = [
            ("es", {"p7_block_9_0": "grado", "p7_block_9_1": "minutos segundos", "p7_block_9_2": "ángulo plano o arco"}),
            ("pt", {"p7_block_9_0": "grau", "p7_block_9_1": "minutos segundos", "p7_block_9_2": "ângulo plano ou arco"}),
            ("fr", {"p7_block_9_0": "degré", "p7_block_9_1": "minutes secondes", "p7_block_9_2": "angle plan ou arc"}),
            ("de", {"p7_block_9_0": "Grad", "p7_block_9_1": "Minuten Sekunden", "p7_block_9_2": "ebener Winkel oder Bogen"}),
            ("en", {"p7_block_9_0": "degree", "p7_block_9_1": "minutes seconds", "p7_block_9_2": "plane angle or arc"}),
            ("zh", {"p7_block_9_0": "度", "p7_block_9_1": "分 秒", "p7_block_9_2": "平面角或弧"}),
            ("ja", {"p7_block_9_0": "度", "p7_block_9_1": "分 秒", "p7_block_9_2": "平面角または弧"}),
            ("ko", {"p7_block_9_0": "도", "p7_block_9_1": "분 초", "p7_block_9_2": "평면각 또는 호"}),
        ]
        for lang, seg_map in multilingual_cases:
            res = self.engine.stage_page_transaction(doc, page_ir, doc_ir, seg_map)
            self.assertFalse(res.is_fallback, f"Fallback triggered for {lang}")
            detail_map = {d.block_id: d for d in res.details}
            d_ms = detail_map["p7_block_9_1"]
            self.assertEqual(d_ms.status, BlockFittingStatus.SUCCESS, f"Failed status in {lang}: {d_ms}")
            self.assertGreaterEqual(d_ms.shrink_ratio, 0.70, f"Shrink notice (<0.70) in {lang}: {d_ms.shrink_ratio}")
            self.assertNotIn("-", d_ms.translated_text, f"Unexpected hyphenation in {lang}: {d_ms.translated_text}")
        doc.close()

    def test_post_merge_layout_region_self_collision_immunity(self) -> None:
        """Verify ClearancePlanner ignores stale pre-merge formula regions that belong to a merged text block."""
        merged_block = TextBlock(
            block_id="p38_block_37",
            bbox=(55.9, 490.9, 357.1, 505.8),
            spans=[
                GlyphSpan(
                    span_id="s1",
                    text="Hệ phương trình đối xứng loại II: Trừ từng vế hai phương trình.",
                    bbox=(55.9, 490.9, 357.1, 505.8),
                    font_name="Times-Roman",
                    font_size=12.0,
                    color=0,
                )
            ],
            block_type="text",
        )
        # Simulate a stale pymupdf LayoutRegion whose bbox matches the merged text block or an absorbed fragment
        stale_region = LayoutRegion(
            region_id="p38_region_37",
            bbox=(348.0, 490.9, 357.1, 505.8),
            category="formula",
            confidence=1.0,
            source="pymupdf",
        )
        page_ir = PageIR(
            page_number=38,
            geometry=PageGeometry(width=420.0, height=595.0),
            blocks=[merged_block],
            regions=[stale_region],
        )
        planner = ClearancePlanner(padding_pt=0.5)
        plan = planner.plan_page_clearance(page_ir, None, [merged_block])
        self.assertTrue(plan.decisions["p38_block_37"].is_approved)
        self.assertIsNone(plan.decisions["p38_block_37"].collision_detail)

    def test_adjacent_untranslated_text_line_boundary_clipping(self) -> None:
        """Verify two consecutive text lines where one is unchanged (e.g., 'STANDARD' in German) do not collide."""
        b_top = TextBlock(
            block_id="p2_block_93",
            bbox=(256.6, 48.75, 346.6, 57.08),
            spans=[
                GlyphSpan(
                    span_id="s_top",
                    text="IEEE 754 FLOATING-POINT",
                    bbox=(256.6, 48.75, 346.6, 57.08),
                    font_name="Times-Bold",
                    font_size=7.0,
                    color=0,
                )
            ],
            block_type="text",
        )
        # Unchanged cognate line directly below (touches by 0.33pt before padding)
        b_bot = TextBlock(
            block_id="p2_block_5",
            bbox=(256.6, 56.75, 295.0, 65.08),
            spans=[
                GlyphSpan(
                    span_id="s_bot",
                    text="STANDARD",
                    bbox=(256.6, 56.75, 295.0, 65.08),
                    font_name="Times-Bold",
                    font_size=7.0,
                    color=0,
                )
            ],
            block_type="text",
        )
        page_ir = PageIR(
            page_number=2,
            geometry=PageGeometry(width=540.0, height=666.0),
            blocks=[b_top, b_bot],
        )
        planner = ClearancePlanner(padding_pt=0.5)
        # Only b_top is in candidate_blocks because b_bot ('STANDARD' -> 'STANDARD') is unchanged in German
        plan = planner.plan_page_clearance(page_ir, None, [b_top])
        self.assertTrue(plan.decisions["p2_block_93"].is_approved)
        self.assertIsNone(plan.decisions["p2_block_93"].collision_detail)

    def test_vertical_rotated_margin_text_condensation(self) -> None:
        """Verify 90-degree rotated margin instructions condense along the vertical axis and keep >=70% font scale."""
        doc = pymupdf.open()
        page = doc.new_page(width=540.0, height=666.0)
        page.insert_text(
            pymupdf.Point(533.0, 418.8),
            "1. Pull along perforation to separate card",
            fontsize=10.0,
            rotate=90,
        )
        b_vert = TextBlock(
            block_id="p2_block_92_1",
            bbox=(526.0, 255.8, 536.0, 418.8),
            spans=[
                GlyphSpan(
                    span_id="s_v",
                    text="1. Pull along perforation to separate card",
                    bbox=(526.0, 255.8, 536.0, 418.8),
                    font_name="Times-Roman",
                    font_size=10.0,
                    color=0,
                    origin=(533.0, 418.8),
                )
            ],
            block_type="text",
        )
        page_ir = PageIR(
            page_number=1,
            geometry=PageGeometry(width=540.0, height=666.0),
            blocks=[b_vert],
        )
        doc_ir = DocumentIR(doc_id="vert_doc", filename="vert.pdf", page_count=1, pages=[page_ir])

        for lang, trans in (
            ("de", "1. Ziehen Sie die Perforation entlang, um die Karte zu trennen"),
            ("ja", "1. ミシン目に沿って引っ張ってカードを切り離します"),
            ("fr", "1. Tirez le long de la perforation pour séparer la carte"),
        ):
            res = self.engine.stage_page_transaction(doc, page_ir, doc_ir, {"p2_block_92_1": trans})
            d = res.details[0]
            self.assertEqual(d.status, BlockFittingStatus.SUCCESS)
            self.assertGreaterEqual(
                d.shrink_ratio,
                0.70 - 1e-3,
                f"Vertical rotated text shrank below 70% in {lang}: {d.shrink_ratio}",
            )
        doc.close()

    def test_word_token_span_boundary_and_colon_ratio_isolation(self) -> None:
        """Verify prose words never coalesce with touching math operator/closing-paren spans and 'a:b' ratios are isolated."""
        from layoutlingua.core.ir import CharInfo
        from layoutlingua.processing.formula.isolator import FormulaIsolator

        iso = FormulaIsolator()

        # 1. '. (hoặc×) ' -> prose 'hoặc' must not coalesce with '×'
        b_hoac = TextBlock(
            block_id="p6_block_3_0_2",
            bbox=(54.0, 224.0, 95.3, 240.3),
            spans=[
                GlyphSpan(
                    span_id="s1",
                    text=". (hoặc",
                    bbox=(54.0, 224.0, 82.9, 240.3),
                    font_name="VNI-Times",
                    font_size=12.0,
                    color=0,
                    chars=[
                        CharInfo(char=".", bbox=(54.0, 224.0, 57.0, 240.3), origin=(54.0, 237.0)),
                        CharInfo(char=" ", bbox=(57.0, 224.0, 60.0, 240.3), origin=(57.0, 237.0)),
                        CharInfo(char="(", bbox=(60.0, 224.0, 64.0, 240.3), origin=(60.0, 237.0)),
                        CharInfo(char="h", bbox=(64.0, 224.0, 70.0, 240.3), origin=(64.0, 237.0)),
                        CharInfo(char="o", bbox=(70.0, 224.0, 74.0, 240.3), origin=(70.0, 237.0)),
                        CharInfo(char="ặ", bbox=(74.0, 224.0, 78.0, 240.3), origin=(74.0, 237.0)),
                        CharInfo(char="c", bbox=(78.0, 224.0, 82.9, 240.3), origin=(78.0, 237.0)),
                    ],
                ),
                GlyphSpan(
                    span_id="s2",
                    text="×",
                    bbox=(82.9, 224.8, 89.5, 240.3),
                    font_name="Symbol",
                    font_size=12.0,
                    color=0,
                    is_math_or_symbol=True,
                    chars=[CharInfo(char="×", bbox=(82.9, 224.8, 89.5, 240.3), origin=(82.9, 237.0))],
                ),
                GlyphSpan(
                    span_id="s3",
                    text=") ",
                    bbox=(88.3, 224.0, 95.3, 240.3),
                    font_name="VNI-Times",
                    font_size=12.0,
                    color=0,
                    chars=[CharInfo(char=")", bbox=(88.3, 224.0, 92.3, 240.3), origin=(88.3, 237.0))],
                ),
            ],
            block_type="text",
        )
        seg_hoac = iso.isolate_block(b_hoac)
        self.assertIn("hoặc", seg_hoac.masked_text)
        self.assertIn("<b0></b0>", seg_hoac.masked_text)
        self.assertEqual(iso.restore_translation(seg_hoac, ". (или <b0></b0>)"), ". (или ×)")

        # 2. 'a:b hoặc ' -> 'a:b' must be isolated as <b0></b0>
        b_ratio = TextBlock(
            block_id="p6_block_3_2_23",
            bbox=(293.5, 246.2, 336.4, 260.0),
            spans=[
                GlyphSpan(
                    span_id="s_ab",
                    text="a:b ",
                    bbox=(293.5, 246.2, 311.5, 260.0),
                    font_name="VNI-Times,Italic",
                    font_size=12.0,
                    color=0,
                    flags=2,
                    chars=[
                        CharInfo(char="a", bbox=(293.5, 246.2, 299.5, 260.0), origin=(293.5, 257.0)),
                        CharInfo(char=":", bbox=(299.5, 246.2, 302.5, 260.0), origin=(299.5, 257.0)),
                        CharInfo(char="b", bbox=(302.5, 246.2, 308.5, 260.0), origin=(302.5, 257.0)),
                        CharInfo(char=" ", bbox=(308.5, 246.2, 311.5, 260.0), origin=(308.5, 257.0)),
                    ],
                ),
                GlyphSpan(
                    span_id="s_h",
                    text="hoặc ",
                    bbox=(311.5, 246.2, 336.4, 260.0),
                    font_name="VNI-Times",
                    font_size=12.0,
                    color=0,
                    chars=[
                        CharInfo(char="h", bbox=(311.5, 246.2, 317.5, 260.0), origin=(311.5, 257.0)),
                        CharInfo(char="o", bbox=(317.5, 246.2, 323.5, 260.0), origin=(317.5, 257.0)),
                        CharInfo(char="ặ", bbox=(323.5, 246.2, 329.5, 260.0), origin=(323.5, 257.0)),
                        CharInfo(char="c", bbox=(329.5, 246.2, 336.4, 260.0), origin=(329.5, 257.0)),
                    ],
                ),
            ],
            block_type="text",
        )
        seg_ratio = iso.isolate_block(b_ratio)
        self.assertEqual(seg_ratio.masked_text, "<b0></b0> hoặc")
        self.assertEqual(iso.restore_translation(seg_ratio, "<b0></b0> или"), "a:b или")

    def test_multilingual_math_glossary_pivot_and_polysemy_healing(self) -> None:
        """Verify VI->RU/FR/DE/ZH glossary pivot and formula-anchored phrase healing."""
        from layoutlingua.translation.glossary import GlossaryManager

        self.assertEqual(
            GlossaryManager.normalize_translation("Bằng", "Степень", "vi", "ru"),
            "Равно",
        )
        self.assertEqual(
            GlossaryManager.normalize_translation("Nhân", "Человек", "vi", "ru"),
            "Умножение",
        )
        self.assertEqual(
            GlossaryManager.normalize_translation("Cung", "Поклон", "vi", "ru"),
            "Дуга",
        )
        self.assertEqual(
            GlossaryManager.normalize_translation("Đơn vị ảo", "Виртуальный блок", "vi", "ru"),
            "Мнимая единица",
        )
        self.assertEqual(
            GlossaryManager.normalize_translation(
                " có vô số nghiệm ",
                "существует бесчисленное множество решений",
                "vi",
                "ru",
            ),
            "бесконечно много решений",
        )
        self.assertEqual(
            GlossaryManager.normalize_translation(
                "(cơ số b=10)",
                "(система счисления <b0></b0>)",
                "vi",
                "ru",
                masked_source_text="( cơ số <b0></b0> )",
            ),
            "(основание <b0></b0>)",
        )
        self.assertEqual(
            GlossaryManager.normalize_translation(
                "a=0, b≠0: (1) vô nghiệm",
                "<b0></b0> неэффективно",
                "vi",
                "ru",
                masked_source_text="<b0></b0> vô nghiệm",
            ),
            "<b0></b0> нет решений",
        )


if __name__ == "__main__":
    unittest.main()

