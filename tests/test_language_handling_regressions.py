"""Regression coverage for source scripts, offline routes, and request limits."""

import pytest

from layoutlingua.core.ir import GlyphSpan
from layoutlingua.core.parser import (
    FORMULA_FONT_PATTERN,
    _extract_prose_tokens,
    _is_pure_formula_block,
)
from layoutlingua.processing.text_sanitizer import detect_language_from_text
from layoutlingua.translation.argos import ArgosModelInfo, ArgosModelManager, LanguageRegistry, RouteType
from layoutlingua.translation.google_rpc import _MAX_CHUNK_CHARS, _split_into_chunks


@pytest.mark.parametrize("font", ["ArialUnicodeMS", "ArialUnicodeMS+1", "ABCDEF+ArialUnicodeMS", "NotoSansCJK"])
def test_unicode_fonts_are_not_formula_fonts(font):
    assert FORMULA_FONT_PATTERN.search(font) is None


@pytest.mark.parametrize("font", ["CMEX10", "CMSY10", "FiraCode", "CascadiaCode", "SourceCodePro", "Symbol"])
def test_formula_and_code_fonts_remain_recognized(font):
    assert FORMULA_FONT_PATTERN.search(font)


@pytest.mark.parametrize("text", ["世 界 人 权 宣 言", "世界人权宣言", "日 本 語", "한 국 어", "𠀀 𠀁"])
def test_cjk_prose_is_not_a_formula(text):
    span = GlyphSpan(
        span_id="s1", text=text, bbox=(0, 0, 200, 20),
        font_name="ArialUnicodeMS", font_size=11, color="#000000",
    )
    assert _extract_prose_tokens(text)
    assert not _is_pure_formula_block([span])


def test_empty_and_mathematical_text_do_not_gain_prose_tokens():
    assert _extract_prose_tokens("") == []
    assert _extract_prose_tokens("x = y² + 1") == []


@pytest.mark.parametrize(("text", "language"), [
    ("مرحبا بالعالم", "ar"), ("اﻟﺪﻳﺒﺎﺟﺔ", "ar"),
    ("שלום עולם", "he"), ("שׁלום", "he"),
    ("", "en"), ("123 !?", "en"), ("the rights of all people", "en"),
    ("日本語の翻訳", "ja"),
])
def test_source_script_detection(text, language):
    assert detect_language_from_text(text) == language


@pytest.mark.parametrize("code", ["zh-TW", "zh-tw", "zh-Hant", "zh-hant", "zh-HK", "ZH-HK", " zh-TW "])
def test_argos_traditional_chinese_aliases(code):
    assert LanguageRegistry.to_argos_code(code) == "zt"


@pytest.mark.parametrize(("code", "expected"), [("ZH-HANS", "zh"), ("ZH-CN", "zh"), ("PT-br", "pt"), ("EN", "en"), ("", "")])
def test_argos_other_aliases(code, expected):
    assert LanguageRegistry.to_argos_code(code) == expected


def test_installed_packages_add_direct_and_pivot_routes(tmp_path, monkeypatch):
    manager = ArgosModelManager(packages_dir=tmp_path)
    installed = [
        ArgosModelInfo(from_code=a, to_code=b, package_name=f"{a}_{b}", version="1.0", download_url="", size_bytes=0, is_installed=True)
        for a, b in [("vi", "en"), ("xx", "vi"), ("en", "vi")]
    ]
    monkeypatch.setattr(manager, "list_installed_models", lambda: installed)
    direct = manager.plan_route("vi", "en")
    assert direct.route_type == RouteType.DIRECT
    assert direct.steps[0].is_installed
    pivot = manager.plan_route("xx", "en")
    assert pivot.route_type == RouteType.PIVOT
    assert [(s.from_code, s.to_code) for s in pivot.steps] == [("xx", "vi"), ("vi", "en")]
    catalog = manager.list_available_models()
    assert len({(m.from_code, m.to_code) for m in catalog}) == len(catalog)
    assert next(m for m in catalog if (m.from_code, m.to_code) == ("en", "vi")).is_curated


def test_empty_installed_catalog_does_not_invent_reverse_routes(tmp_path, monkeypatch):
    manager = ArgosModelManager(packages_dir=tmp_path)
    monkeypatch.setattr(manager, "list_installed_models", lambda: [])
    assert manager.plan_route("vi", "en") is None


@pytest.mark.parametrize("punctuation", list("。！？；"))
def test_google_chunks_at_cjk_sentence_boundaries(punctuation):
    sentence = "中文测试" + punctuation
    assert _split_into_chunks(sentence * 3, max_chars=6) == [sentence] * 3


@pytest.mark.parametrize("text", ["中" * 7000, "word " * 1500, "中。英文！" * 1500, "x" * 3000 + " " + "y" * 3000])
def test_google_chunk_limit_and_content_preservation(text):
    chunks = _split_into_chunks(text)
    assert all(0 < len(chunk) <= _MAX_CHUNK_CHARS for chunk in chunks)
    assert "".join(chunks) == text


def test_google_chunking_prefers_whitespace_and_handles_empty_text():
    assert _split_into_chunks("one two three", max_chars=8) == ["one two ", "three"]
    assert _split_into_chunks("") == [""]
    assert _split_into_chunks("exact", max_chars=5) == ["exact"]


@pytest.mark.parametrize("limit", [0, -1])
def test_google_chunking_rejects_invalid_limits(limit):
    with pytest.raises(ValueError, match="positive"):
        _split_into_chunks("text", max_chars=limit)
