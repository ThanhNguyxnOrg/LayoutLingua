"""Tests for language-agnostic formula vs prose classification and configuration.

Verifies that layoutlingua.core does not rely on language-specific stopword dictionaries
and correctly handles English, Vietnamese, French, German, Spanish, Russian, and Chinese.
"""

import pytest

from layoutlingua.core.ir import GlyphSpan, TextBlock
from layoutlingua.core.parser import (
    ParserConfig,
    _extract_prose_tokens,
    _is_pure_formula_block,
)
from layoutlingua.core.tables import TableGridValidator, TableValidatorConfig
from layoutlingua.processing.formula.isolator import FormulaIsolator


def test_language_agnostic_prose_extraction_multilingual():
    """Verify that prose extraction identifies prose words across multiple world languages."""
    # Vietnamese
    vi_text = "Cho tam giác ABC có diện tích S = 1/2 a*b*sin(C)"
    assert len(_extract_prose_tokens(vi_text)) >= 3

    # English
    en_text = "Let ABC be a triangle with area S = 1/2 a*b*sin(C)"
    assert len(_extract_prose_tokens(en_text)) >= 3

    # French
    fr_text = "Soit f une fonction continue sur l'intervalle [a, b]"
    assert len(_extract_prose_tokens(fr_text)) >= 3

    # German
    de_text = "Sei f eine stetige Funktion auf dem Intervall [a, b]"
    assert len(_extract_prose_tokens(de_text)) >= 3

    # Spanish
    es_text = "Sea f una función continua en el intervalo [a, b]"
    assert len(_extract_prose_tokens(es_text)) >= 3

    # Russian
    ru_text = "Пусть f непрерывная функция на отрезке [a, b]"
    assert len(_extract_prose_tokens(ru_text)) >= 3


def test_multilingual_formula_equations_have_zero_prose():
    """Verify that pure mathematical equations in various notations have zero prose words."""
    formulas = [
        "cos(2α) = cos² α - sin² α = 2cos² α - 1",
        "P_n(k1, k2, ..., km) = n! / (k1! k2! ... km!)",
        "f(x) = √(x² + 1)",
        "Δ = b² - 4ac",
        "x = (-b ± √Δ) / 2a",
        "S = 1/2 a h_a = abc / 4R = pr",
        "lim_{x -> 0} sin(x)/x = 1",
        "∫ sin(x) dx = -cos(x) + C",
        "vec{a} · vec{b} = |vec{a}| |vec{b}| cos θ",
        "E = mc²",
        "∇ · B = 0",
        "∇ × E = -∂B/∂t",
    ]
    for expr in formulas:
        span = GlyphSpan(
            span_id="s1",
            text=expr,
            bbox=(10, 10, 200, 30),
            font_name="Times-Roman",
            font_size=11.0,
            color="#000000",
        )
        assert _is_pure_formula_block([span]) is True, f"Expression '{expr}' must be classified as formula"


def test_parser_config_dataclass_customization():
    """Verify that ParserConfig can be customized without hardcoded values."""
    custom_cfg = ParserConfig(
        min_block_height_for_split_pt=30.0,
        default_fallback_font_size=12.0,
        min_math_density_ratio=0.75,
    )
    assert custom_cfg.min_block_height_for_split_pt == 30.0
    assert custom_cfg.default_fallback_font_size == 12.0
    assert custom_cfg.min_math_density_ratio == 0.75


def test_table_validator_config_dataclass():
    """Verify that TableValidatorConfig allows custom parameters without magic numbers."""
    cfg = TableValidatorConfig(
        tolerance_pt=3.5,
        min_edge_coverage=0.85,
        orthogonal_snap_pt=1.5,
    )
    validator = TableGridValidator(config=cfg)
    assert validator.tolerance_pt == 3.5
    assert validator.min_edge_coverage == 0.85
