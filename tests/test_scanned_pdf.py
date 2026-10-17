"""Unit tests for scanned PDF preflight check."""

import pymupdf


def test_scanned_pdf_detection():
    # 1. Scanned PDF: image-only page with 0 text
    scanned_doc = pymupdf.open()
    page = scanned_doc.new_page(width=300, height=400)
    pix = pymupdf.Pixmap(pymupdf.csRGB, 10, 10, bytearray(300), False)
    page.insert_image(page.rect, pixmap=pix)

    total_words = 0
    total_images = 0
    for p in scanned_doc:
        total_words += len(p.get_text().split())
        total_images += len(p.get_images())

    page_count = len(scanned_doc)
    avg_words = total_words / max(1, page_count)
    is_scanned = bool(page_count > 0 and ((avg_words < 12 and total_images > 0) or total_words == 0))
    scanned_doc.close()

    assert is_scanned is True
    assert total_words == 0
    assert total_images == 1

    # 2. Digital Text PDF: vector text page
    digital_doc = pymupdf.open()
    page2 = digital_doc.new_page(width=595, height=842)
    page2.insert_text(
        (50, 50),
        "LayoutLingua preserves digital vector typography, formulas, and structural layouts across languages.",
    )

    total_words2 = 0
    total_images2 = 0
    for p in digital_doc:
        total_words2 += len(p.get_text().split())
        total_images2 += len(p.get_images())

    page_count2 = len(digital_doc)
    avg_words2 = total_words2 / max(1, page_count2)
    is_scanned2 = bool(page_count2 > 0 and ((avg_words2 < 12 and total_images2 > 0) or total_words2 == 0))
    digital_doc.close()

    assert is_scanned2 is False
    assert total_words2 > 10
