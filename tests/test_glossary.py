"""Unit tests for GlossaryManager and multilingual academic taxonomy."""

from layoutlingua.translation.glossary import GlossaryManager


def test_builtin_vietnamese_glossary():
    text = "Theorem 1.1: For any given Matrix and its Eigenvalue, the Proof is direct."
    res = GlossaryManager.apply_glossary(text, source_lang="en", target_lang="vi")
    assert "\u0110\u1ecbnh l\xfd" in res
    assert "Ma tr\u1eadn" in res
    assert "Gi\xe1 tr\u1ecb ri\xeang" in res
    assert "Ch\u1ee9ng minh" in res


def test_token_and_formula_protection():
    text = "Theorem 2: \u27eaLL_FORMULA_1\u27eb is valid. See <b0>Matrix</b0> in \u27eaLL_FORMULA_2\u27eb."
    res = GlossaryManager.apply_glossary(text, source_lang="en", target_lang="vi")
    # Formula tokens and XML tags must remain completely untouched
    assert "\u27eaLL_FORMULA_1\u27eb" in res
    assert "\u27eaLL_FORMULA_2\u27eb" in res
    assert "<b0>" in res
    assert "</b0>" in res
    assert "\u0110\u1ecbnh l\xfd" in res


def test_custom_user_override():
    # User provides their own term override
    custom = "Theorem = Ti\xean \u0111\u1ec1 th\u1ef1c nghi\u1ec7m\nMatrix = B\u1ea3ng s\u1ed1 li\u1ec7u"
    text = "Theorem 3 states that every Matrix has a Determinant."
    res = GlossaryManager.apply_glossary(text, source_lang="en", target_lang="vi", custom_glossary=custom)
    assert "Ti\xean \u0111\u1ec1 th\u1ef1c nghi\u1ec7m" in res
    assert "B\u1ea3ng s\u1ed1 li\u1ec7u" in res
    # Built-in terms still active for other words
    assert "\u0110\u1ecbnh th\u1ee9c" in res


def test_multilingual_glossary():
    text = "Proof of Theorem: By Definition and Algorithm 1."

    # Chinese
    zh = GlossaryManager.apply_glossary(text, source_lang="en", target_lang="zh")
    assert "\u5b9a\u7406\u8bc1\u660e" in zh
    assert "\u5b9a\u4e49" in zh
    assert "\u7b97\u6cd5" in zh

    # Japanese
    ja = GlossaryManager.apply_glossary(text, source_lang="en", target_lang="ja")
    assert "\u5b9a\u7406\u306e\u8a3c\u660e" in ja
    assert "\u5b9a\u7fa9" in ja
    assert "\u30a2\u30eb\u30b4\u30ea\u30ba\u30e0" in ja

    # German
    de = GlossaryManager.apply_glossary(text, source_lang="en", target_lang="de")
    assert "Beweis" in de
    assert "Definition" in de
    assert "Algorithmus" in de

    # French
    fr = GlossaryManager.apply_glossary(text, source_lang="en", target_lang="fr")
    assert "D\xe9monstration" in fr
    assert "D\xe9finition" in fr
    assert "Algorithme" in fr


def test_parse_custom_glossary_formats():
    d = GlossaryManager.parse_custom_glossary({"a": "b", "c": "d"})
    assert d["a"] == "b"
    assert d["c"] == "d"

    s = GlossaryManager.parse_custom_glossary("""Alpha = Beta
Gamma : Delta""")
    assert s["Alpha"] == "Beta"
    assert s["Gamma"] == "Delta"