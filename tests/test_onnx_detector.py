"""Tests for ONNX vision layout detection module."""

import numpy as np
import pytest

from layoutlingua.core.ir import GlyphSpan
from layoutlingua.processing.vision import (
    LayoutCategory,
    LayoutRegion,
    OnnxLayoutDetector,
)


def _make_span(span_id: str, x0: float, y0: float, x1: float, y1: float, text: str = "sample") -> GlyphSpan:
    return GlyphSpan(
        span_id=span_id,
        text=text,
        font_name="Helvetica",
        font_size=11.0,
        color=0,
        bbox=(x0, y0, x1, y1),
        origin=(x0, y1),
    )


def test_onnx_detector_availability_without_model() -> None:
    detector = OnnxLayoutDetector()
    assert not detector.is_available()
    assert detector.detect(np.zeros((100, 100, 3), dtype=np.uint8)) == []
    assert not detector.load_model("missing_model.onnx")


def test_onnx_detector_letterbox_and_preprocess() -> None:
    detector = OnnxLayoutDetector()
    img = np.zeros((600, 800, 3), dtype=np.uint8)
    blob, ratio, (pad_x, pad_y) = detector.preprocess(img)

    assert blob.shape == (1, 3, 1024, 1024)
    assert blob.dtype == np.float32
    assert ratio > 0.0
    assert pad_x >= 0.0
    assert pad_y >= 0.0


def test_onnx_detector_postprocess_direct_format() -> None:
    detector = OnnxLayoutDetector(conf_threshold=0.3)
    orig_shape = (800, 600)  # (h, w)
    ratio = 1.0
    pad = (0.0, 0.0)

    # Mock output with shape (1, 2, 6): [x1, y1, x2, y2, score, class_id]
    mock_preds = np.array(
        [[
            [50.0, 50.0, 300.0, 200.0, 0.95, 0.0],  # class 0: Title
            [50.0, 250.0, 500.0, 450.0, 0.88, 5.0],  # class 5: Table
        ]],
        dtype=np.float32,
    )

    regions = detector.postprocess([mock_preds], orig_shape, ratio, pad)
    assert len(regions) == 2
    assert regions[0].category == LayoutCategory.TITLE
    assert regions[0].score == 0.95
    assert regions[0].bbox == (50.0, 50.0, 300.0, 200.0)
    assert regions[1].category == LayoutCategory.TABLE
    assert regions[1].score == 0.88


def test_onnx_detector_postprocess_center_format() -> None:
    detector = OnnxLayoutDetector(conf_threshold=0.4)
    orig_shape = (1000, 1000)
    ratio = 1.0
    pad = (0.0, 0.0)

    # Mock output with shape (1, 1, 14): cx, cy, w, h, class_scores...
    scores = np.zeros(10, dtype=np.float32)
    scores[8] = 0.92  # class 8: Formula

    row = np.concatenate([[200.0, 300.0, 100.0, 50.0], scores])
    mock_preds = np.array([[row]], dtype=np.float32)

    regions = detector.postprocess([mock_preds], orig_shape, ratio, pad)
    assert len(regions) == 1
    assert regions[0].category == LayoutCategory.FORMULA
    assert regions[0].score == 0.92
    # cx=200, cy=300, w=100, h=50 -> x0=150, y0=275, x1=250, y1=325
    assert regions[0].x0 == 150.0
    assert regions[0].y0 == 275.0
    assert regions[0].x1 == 250.0
    assert regions[0].y1 == 325.0


def test_classify_spans_into_layout_categories() -> None:
    detector = OnnxLayoutDetector()
    table_region = LayoutRegion(
        bbox=(50.0, 200.0, 500.0, 400.0),
        category=LayoutCategory.TABLE,
        score=0.9,
    )
    figure_region = LayoutRegion(
        bbox=(50.0, 500.0, 500.0, 700.0),
        category=LayoutCategory.FIGURE,
        score=0.95,
    )

    span1 = _make_span("s1", 60.0, 220.0, 120.0, 240.0, "Table Cell 1")
    span2 = _make_span("s2", 70.0, 520.0, 180.0, 540.0, "Figure Subtitle")
    span3 = _make_span("s3", 50.0, 50.0, 400.0, 70.0, "Regular Body Paragraph")

    classified = detector.classify_spans(
        spans=[span1, span2, span3],
        regions=[table_region, figure_region],
    )

    assert len(classified[LayoutCategory.TABLE]) == 1
    assert classified[LayoutCategory.TABLE][0].text == "Table Cell 1"

    assert len(classified[LayoutCategory.FIGURE]) == 1
    assert classified[LayoutCategory.FIGURE][0].text == "Figure Subtitle"

    assert len(classified[LayoutCategory.TEXT]) == 1
    assert classified[LayoutCategory.TEXT][0].text == "Regular Body Paragraph"


def test_parse_pdf_with_layout_detector(tmp_path) -> None:
    import pymupdf
    from layoutlingua.core.parser import parse_pdf

    test_pdf_path = tmp_path / "test_detector.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=600)
    page.insert_text((50, 100), "Deep Learning Overview", fontsize=16)
    doc.save(str(test_pdf_path))
    doc.close()

    class MockDetector:
        def is_available(self) -> bool:
            return True

        def detect(self, img_bytes: bytes) -> list[LayoutRegion]:
            # Return detected title region at (100, 200, 600, 300) in image pixels (at 150 DPI)
            return [
                LayoutRegion(
                    bbox=(100.0, 200.0, 600.0, 300.0),
                    category=LayoutCategory.TITLE,
                    score=0.98,
                )
            ]

        def to_ir_regions(self, regions, page_num: int):
            return OnnxLayoutDetector.to_ir_regions(regions, page_num)

    ir = parse_pdf(test_pdf_path, layout_detector=MockDetector())
    assert len(ir.pages) == 1
    # Check that region from detector was converted and appended
    onnx_regions = [r for r in ir.pages[0].regions if r.source == "doclayout_yolo"]
    assert len(onnx_regions) == 1
    assert onnx_regions[0].category == "title"
    assert onnx_regions[0].confidence == 0.98
    # 100 * (72 / 150) = 48.0 pt
    assert abs(onnx_regions[0].bbox[0] - 48.0) < 0.1

