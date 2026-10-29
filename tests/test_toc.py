"""Unit tests for PDF Table of Contents (bookmarks) translation."""

import pymupdf
from layoutlingua.processing.toc import translate_toc


def test_translate_toc_mono_and_bilingual():
    doc = pymupdf.open()
    for _ in range(5):
        doc.new_page(width=300, height=300)

    # Set sample academic TOC
    sample_toc = [
        [1, "1. Introduction", 1],
        [1, "2. Methodology", 2],
        [2, "2.1 Algorithm", 3],
        [1, "3. Conclusion", 4],
        [1, "References", 5],
    ]
    doc.set_toc(sample_toc)

    # Test Mono translation (Vietnamese)
    toc_vi = translate_toc(doc, target_lang="vi", bilingual_mode=False)
    assert len(toc_vi) == 5
    assert "Giới thiệu" in toc_vi[0][1]
    assert "Phương pháp" in toc_vi[1][1]
    assert "Thuật toán" in toc_vi[2][1]
    assert "Kết luận" in toc_vi[3][1]
    assert "Tài liệu tham khảo" in toc_vi[4][1]
    # Page indices remain 1, 2, 3, 4, 5
    assert [item[2] for item in toc_vi] == [1, 2, 3, 4, 5]

    # Test Bilingual translation (Page targets doubled)
    toc_bi = translate_toc(doc, target_lang="vi", bilingual_mode=True)
    assert [item[2] for item in toc_bi] == [2, 4, 6, 8, 10]

    doc.close()