"""Unit tests for text sanitization, ftfy mojibake repair, and abbreviation guarding."""

from layoutlingua.processing.text_sanitizer import (
    sanitize_extracted_text,
    shield_academic_abbreviations,
    unshield_academic_abbreviations,
)


def test_sanitize_mojibake_repair():
    # Broken UTF-8 encoding (mojibake) often found in legacy PDFs
    raw_mojibake = "SchÃ¶ne GrÃ¼Ã\x9fe &amp; test"
    cleaned = sanitize_extracted_text(raw_mojibake)
    assert "Schöne Grüße" in cleaned
    assert "& test" in cleaned


def test_shield_and_unshield_academic_abbreviations():
    sample = "As established by Vaswani et al., the attention block (see Fig. 1) outperforms previous models."
    shielded, mapping = shield_academic_abbreviations(sample)

    assert "⟦LL_ABBR_0⟧" in shielded
    assert "⟦LL_ABBR_1⟧" in shielded
    assert mapping["⟦LL_ABBR_0⟧"].lower() == "et al."
    assert mapping["⟦LL_ABBR_1⟧"].lower() == "fig."

    # Simulated translation maintaining abbreviation tokens
    translated = "Như đã được thiết lập bởi Vaswani ⟦LL_ABBR_0⟧, khối attention (xem ⟦LL_ABBR_1⟧ 1) vượt trội hơn."
    restored = unshield_academic_abbreviations(translated, mapping)

    assert "Vaswani et al." in restored
    assert "xem Fig. 1" in restored
