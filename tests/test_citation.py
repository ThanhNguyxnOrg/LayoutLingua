"""Tests for academic citation anchor shielding."""

from layoutlingua.processing.citation import shield_citations, unshield_citations


def test_shield_and_unshield_citations():
    original = "Transformer [1] architecture achieved SOTA results on benchmarks [2, 3] and [4-7]."
    shielded, mapping = shield_citations(original)

    assert "⟦LL_REF_0⟧" in shielded
    assert "⟦LL_REF_1⟧" in shielded
    assert "⟦LL_REF_2⟧" in shielded
    assert mapping["⟦LL_REF_0⟧"] == "[1]"
    assert mapping["⟦LL_REF_1⟧"] == "[2, 3]"
    assert mapping["⟦LL_REF_2⟧"] == "[4-7]"

    # Simulated translation maintaining tokens
    translated = "Kiến trúc Transformer ⟦LL_REF_0⟧ đạt kết quả SOTA trên benchmark ⟦LL_REF_1⟧ và ⟦LL_REF_2⟧."
    restored = unshield_citations(translated, mapping)

    assert restored == "Kiến trúc Transformer [1] đạt kết quả SOTA trên benchmark [2, 3] và [4-7]."


def test_text_without_citations():
    text = "Plain academic text with no references."
    shielded, mapping = shield_citations(text)
    assert shielded == text
    assert mapping == {}
    assert unshield_citations(shielded, mapping) == text
