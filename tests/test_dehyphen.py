"""Tests for line-break dehyphenation module."""

from layoutlingua.processing.dehyphen import dehyphenate_text


def test_dehyphenate_broken_syllables():
    assert dehyphenate_text("distri-\n bution of data") == "distribution of data"
    assert dehyphenate_text("algo-\nrithm analysis") == "algorithm analysis"
    assert dehyphenate_text("optimi-\n  zation method") == "optimization method"
    assert dehyphenate_text("re-\n presentation") == "representation"
    assert dehyphenate_text("con-\nnectivity") == "connectivity"


def test_preserve_compounds_and_model_names():
    assert dehyphenate_text("state-of-the-art benchmark") == "state-of-the-art benchmark"
    assert dehyphenate_text("fine-tuned LLM") == "fine-tuned LLM"
    assert dehyphenate_text("U-Net architecture") == "U-Net architecture"
    assert dehyphenate_text("X-ray imaging") == "X-ray imaging"
    assert dehyphenate_text("k-means clustering") == "k-means clustering"
    assert dehyphenate_text("IEEE-ACM transaction") == "IEEE-ACM transaction"


def test_preserve_formula_placeholders_and_tags():
    sample = "Equation <b0></b0> shows ⟦LL_FORMULA_1⟧ with distri-\nbution over <b2></b2>."
    expected = "Equation <b0></b0> shows ⟦LL_FORMULA_1⟧ with distribution over <b2></b2>."
    assert dehyphenate_text(sample) == expected


def test_unicode_soft_hyphens():
    assert dehyphenate_text("pa\u00adrameter") == "parameter"
    assert dehyphenate_text("cal\u2010\n culation") == "calculation"
