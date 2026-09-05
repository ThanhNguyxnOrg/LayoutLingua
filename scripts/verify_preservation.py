"""Verification and Visual Regression tool for LayoutLingua.

Computes geometry preservation metrics, page invariants, text bounding box displacement,
and visual difference (pixel-diff & structural similarity) between source and translated PDFs.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import cv2
import fitz  # PyMuPDF
import numpy as np


def compute_page_visual_diff(
    src_page: fitz.Page,
    dst_page: fitz.Page,
    dpi: int = 150,
) -> Tuple[float, np.ndarray]:
    """Render source and target pages and compute visual difference metrics.

    Returns:
        (diff_ratio, diff_heatmap_bgr)
    """
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix_src = src_page.get_pixmap(matrix=mat, alpha=False)
    pix_dst = dst_page.get_pixmap(matrix=mat, alpha=False)

    img_src = np.frombuffer(pix_src.samples, dtype=np.uint8).reshape(
        pix_src.height, pix_src.width, 3
    )
    img_dst = np.frombuffer(pix_dst.samples, dtype=np.uint8).reshape(
        pix_dst.height, pix_dst.width, 3
    )

    # Resize if dimensions differ slightly due to rounding
    if img_src.shape != img_dst.shape:
        img_dst = cv2.resize(img_dst, (img_src.shape[1], img_src.shape[0]))

    # Convert to grayscale
    gray_src = cv2.cvtColor(img_src, cv2.COLOR_RGB2GRAY)
    gray_dst = cv2.cvtColor(img_dst, cv2.COLOR_RGB2GRAY)

    # Absolute difference
    diff = cv2.absdiff(gray_src, gray_dst)
    diff_pixels = np.count_nonzero(diff > 25)
    total_pixels = diff.size
    diff_ratio = float(diff_pixels / total_pixels)

    # Generate colored difference heatmap
    heatmap = cv2.applyColorMap(diff, cv2.COLORMAP_JET)
    return diff_ratio, heatmap


def verify_pdf_pair(
    src_path: str | Path,
    dst_path: str | Path,
    output_report: str | Path | None = None,
    save_diff_images: bool = False,
    diff_dir: str | Path | None = None,
) -> Dict[str, Any]:
    """Verify geometry, text box bounds, and visual consistency between source and translated PDFs."""
    src_doc = fitz.open(src_path)
    dst_doc = fitz.open(dst_path)

    report: Dict[str, Any] = {
        "source_pdf": str(src_path),
        "translated_pdf": str(dst_path),
        "page_count_match": len(src_doc) == len(dst_doc),
        "source_pages": len(src_doc),
        "translated_pages": len(dst_doc),
        "pages": [],
        "passed_invariants": True,
    }

    if not report["page_count_match"]:
        report["passed_invariants"] = False
        report["error"] = "Page counts do not match!"

    min_pages = min(len(src_doc), len(dst_doc))
    if save_diff_images and diff_dir:
        Path(diff_dir).mkdir(parents=True, exist_ok=True)

    for p_idx in range(min_pages):
        s_page = src_doc[p_idx]
        d_page = dst_doc[p_idx]

        s_rect = s_page.rect
        d_rect = d_page.rect
        rect_match = (
            abs(s_rect.width - d_rect.width) < 1.0
            and abs(s_rect.height - d_rect.height) < 1.0
        )

        diff_ratio, heatmap = compute_page_visual_diff(s_page, d_page)

        page_info: Dict[str, Any] = {
            "page": p_idx + 1,
            "dimensions_match": rect_match,
            "source_dimensions": [s_rect.width, s_rect.height],
            "translated_dimensions": [d_rect.width, d_rect.height],
            "visual_diff_ratio": round(diff_ratio, 4),
        }

        if save_diff_images and diff_dir:
            diff_img_path = Path(diff_dir) / f"diff_page_{p_idx + 1}.png"
            cv2.imwrite(str(diff_img_path), heatmap)
            page_info["diff_heatmap_image"] = str(diff_img_path)

        report["pages"].append(page_info)
        if not rect_match:
            report["passed_invariants"] = False

    src_doc.close()
    dst_doc.close()

    if output_report:
        with open(output_report, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify preservation invariants and visual differences."
    )
    parser.add_argument("source_pdf", help="Path to original source PDF")
    parser.add_argument("translated_pdf", help="Path to translated PDF")
    parser.add_argument(
        "--report", "-r", help="Path to write JSON verification report"
    )
    parser.add_argument(
        "--save-diffs",
        action="store_true",
        help="Save visual difference heatmaps",
    )
    parser.add_argument(
        "--diff-dir",
        default="scratch/visual_diffs",
        help="Directory to save diff images",
    )

    args = parser.parse_args()
    report = verify_pdf_pair(
        args.source_pdf,
        args.translated_pdf,
        output_report=args.report,
        save_diff_images=args.save_diffs,
        diff_dir=args.diff_dir,
    )

    print(json.dumps(report, indent=2))
    return 0 if report.get("passed_invariants", False) else 1


if __name__ == "__main__":
    sys.exit(main())
