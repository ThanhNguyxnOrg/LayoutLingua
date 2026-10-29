"""Unit tests for bilingual alternating PDF export."""

import pymupdf
from layoutlingua.typesetting.accumulator import DocumentAccumulator


def test_bilingual_alternating_export():
    # Create 2-page source PDF
    src_doc = pymupdf.open()
    p1 = src_doc.new_page(width=300, height=300)
    p1.insert_text((50, 50), "Source Page 1")
    p2 = src_doc.new_page(width=300, height=300)
    p2.insert_text((50, 50), "Source Page 2")

    accumulator = DocumentAccumulator(source_doc=src_doc)

    # Commit 2 translated staging pages
    st1 = pymupdf.open()
    st1_p = st1.new_page(width=300, height=300)
    st1_p.insert_text((50, 50), "Translated Page 1")

    class MockTx:
        def __init__(self, doc, idx):
            self.staging_doc = doc
            self.source_page_index = idx

    accumulator.commit_page(MockTx(st1, 0))

    st2 = pymupdf.open()
    st2_p = st2.new_page(width=300, height=300)
    st2_p.insert_text((50, 50), "Translated Page 2")
    accumulator.commit_page(MockTx(st2, 1))

    # Test Mono export first
    # In mono mode, len is 2
    # Since accumulator.finish() closes the document, let's test bilingual on a dedicated accumulator
    acc_bi = DocumentAccumulator(source_doc=src_doc)
    acc_bi.commit_pristine_source_page(0)
    acc_bi.commit_pristine_source_page(1)

    bi_bytes = acc_bi.finish(layout_mode="bilingual")
    bi_doc = pymupdf.open(stream=bi_bytes, filetype="pdf")

    # In bilingual mode: 2 source pages + 2 translated pages = 4 alternating pages
    assert len(bi_doc) == 4
    bi_doc.close()
    src_doc.close()