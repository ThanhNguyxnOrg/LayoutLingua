"""Functions that can be used for the most common use-cases for layoutlingua."""

import asyncio
import hashlib
import io
import json
import logging
import math
import os
import re
import sys
import tempfile
from asyncio import CancelledError
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from string import Template
from typing import Any, BinaryIO

import numpy as np
import pikepdf
import tqdm
from babeldoc.assets.assets import get_font_and_metadata
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfexceptions import PDFValueError
from pdfminer.pdfinterp import PDFResourceManager
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfparser import PDFParser
from pymupdf import Document, Font

from layoutlingua.cache import TranslationCache
from layoutlingua.converter import TranslateConverter, preferred_translation
from layoutlingua.doclayout import OnnxModel, YoloResult
from layoutlingua.pdfinterp import PDFPageInterpreterEx
from layoutlingua.reading_order import LayoutBox, infer_reading_order_indices
from layoutlingua.rules import (
    classify_preserved_page,
    cluster_table_words,
    formula_regions,
    is_scanned_page,
    matching_table_cells,
    normalize_legacy_vietnamese,
    page_has_image,
    should_translate_table_cell,
    split_text_columns,
)


@dataclass(frozen=True)
class TranslationReport:
    """What a run could not translate, and why.

    The count on its own was ambiguous: a page of diagrams, a document that is
    all scans, and a dropped connection all arrived as the same number, and the
    caller had to guess. Each of those needs the user to do something
    different, so the reasons travel with the count.
    """

    failures: list[str] = field(default_factory=list)
    reasons: Counter = field(default_factory=Counter)
    image_only_pages: set[int] = field(default_factory=set)
    translatable_segments: int = 0
    pages_processed: int = 0

    def __len__(self) -> int:
        return len(self.failures)


NOTO_NAME = "noto"
STYLE_FONT_NAMES = {
    0: NOTO_NAME,
    1: "noto-bold",
    2: "noto-italic",
    3: "noto-bolditalic",
}
BASE14_STYLE_FONTS = {0: "tiro", 1: "tibo", 2: "tiit", 3: "tibi"}

logger = logging.getLogger(__name__)
LARGE_DOCUMENT_SUBSET_PAGE_LIMIT = 200
LARGE_DOCUMENT_BYTE_LIMIT = 50 * 1024 * 1024


def is_large_document(page_count: int, source_size: int = 0) -> bool:
    return (
        page_count >= LARGE_DOCUMENT_SUBSET_PAGE_LIMIT
        or source_size >= LARGE_DOCUMENT_BYTE_LIMIT
    )


def should_subset_fonts(
    page_count: int, skip_subset_fonts: bool, source_size: int = 0
) -> bool:
    """Never subset: the converter writes raw glyph IDs into Identity-H fonts.

    `raw_string()` emits `font.has_glyph(ord(c))` as the CID, so any pass that
    renumbers glyphs repoints every translated character at a different
    outline. It cost Vietnamese every stacked-diacritic letter ("Viet Nam"
    where "Viet" needed U+1EC7) on documents small enough to fall under the old
    page/size threshold. The parameters are kept so the call site still reads
    as a decision rather than a silent omission.
    """
    return False


def pdf_write_options(page_count: int, source_size: int = 0) -> dict[str, int | bool]:
    """Choose fast, low-memory serialization for large documents.

    Recompressing and garbage-collecting every object in a long textbook can
    hold the CPython GIL for tens of seconds.  A light cleanup is almost the same
    size for image-heavy books and lets the GUI finish promptly.
    """
    if is_large_document(page_count, source_size):
        return {"deflate": False, "garbage": 1, "use_objstms": 0}
    return {"deflate": True, "garbage": 3, "use_objstms": 1}


def output_style_font_paths(language: str, regular_path: str) -> dict[int, str]:
    """Resolve regular/bold/italic/bold-italic fonts for translated prose.

    Vietnamese desktop builds run on Windows, where Times New Roman ships with
    all four faces. Other environments retain the existing Unicode font and let
    the converter synthesize missing weight/slant instead of downloading a new
    family at render time.
    """
    regular = str(Path(regular_path))
    result = {style: regular for style in STYLE_FONT_NAMES}
    if Path(regular).name.lower() != "times.ttf":
        return result
    windows_variants = {
        1: Path("C:/Windows/Fonts/timesbd.ttf"),
        2: Path("C:/Windows/Fonts/timesi.ttf"),
        3: Path("C:/Windows/Fonts/timesbi.ttf"),
    }
    for style, path in windows_variants.items():
        if path.is_file():
            result[style] = str(path)
    return result

noto_list = [
    "am",  # Amharic
    "ar",  # Arabic
    "bn",  # Bengali
    "bg",  # Bulgarian
    "chr",  # Cherokee
    "el",  # Greek
    "gu",  # Gujarati
    "he",  # Hebrew
    "iw",  # Hebrew (legacy)
    "hi",  # Hindi
    "kn",  # Kannada
    "ml",  # Malayalam
    "mr",  # Marathi
    "ru",  # Russian
    "sr",  # Serbian
    "ta",  # Tamil
    "te",  # Telugu
    "th",  # Thai
    "ur",  # Urdu
    "uk",  # Ukrainian
]


def pymupdf_can_round_trip(path: Path) -> bool:
    """Report whether the engine can both read and rewrite this document.

    pikepdf tolerates structural damage that MuPDF later refuses on write, so
    probing with pikepdf let a malformed 517-page book reach `translate_stream`
    and die there with "invalid key in dict". The engine's own round trip is
    the only probe that predicts the failure it is meant to prevent, and it
    costs under a second even on a 48 MB book.
    """
    document = None
    try:
        document = Document(str(path))
        document.save(io.BytesIO())
    except Exception:
        return False
    finally:
        if document is not None:
            try:
                document.close()
            except Exception:
                pass  # a document that failed to save also fails to close
    return True


def check_files(files: list[str]) -> list[str]:
    files = [
        f for f in files if not f.startswith("http://")
    ]  # exclude online files, http
    files = [
        f for f in files if not f.startswith("https://")
    ]  # exclude online files, https
    missing_files = [file for file in files if not os.path.exists(file)]
    return missing_files


def _classify_fully_preserved_page(page_text: str, pageno: int) -> str | None:
    """Name the preserved-page kind, or None when the page needs layout.

    TOC, index, nomenclature, reference, and other preserved pages end with
    every region protected, so running layout inference on them only burns
    ONNX/CPU time to arrive at an all-zero mask. Text-only pages with no
    extractable text translate nothing either way.
    """
    if not page_text.strip():
        return "BLANK"

    preservation = classify_preserved_page(page_text)
    if preservation is not None:
        logger.info(
            "Page %s detected as %s (%s), preserving original layout",
            pageno + 1,
            preservation.kind,
            preservation.detail,
        )
        return preservation.kind
    return None


def translate_document_outlines(
    doc: Document,
    translator: Any,
) -> None:
    """Translate hierarchical PDF bookmarks / outlines in-place."""
    try:
        toc = doc.get_toc()
        if not toc:
            return
        unique_titles = {}
        for item in toc:
            if len(item) >= 2 and item[1]:
                t = str(item[1]).strip()
                if t and t not in unique_titles:
                    unique_titles[t] = t

        lang_out = getattr(translator, "lang_out", "en")
        translated_map = {}
        for raw_title in unique_titles:
            norm_title = normalize_legacy_vietnamese(raw_title)
            preferred = preferred_translation(norm_title, lang_out)
            if preferred is not None:
                translated_map[raw_title] = preferred
            else:
                try:
                    translated_map[raw_title] = translator.translate(norm_title)
                except Exception:
                    translated_map[raw_title] = norm_title

        translated_toc = []
        for item in toc:
            lvl, title, pageno = item[0], str(item[1]), item[2]
            trans_title = translated_map.get(title.strip(), title)
            translated_toc.append([lvl, trans_title, pageno] + list(item[3:]))
        doc.set_toc(translated_toc)
    except Exception as error:
        logger.debug("Failed to translate document outlines: %s", error)



def _layout_cache_for(
    model: OnnxModel | None, ignore_cache: bool
) -> TranslationCache | None:
    """A persistent layout-result cache, or None when caching is off.

    Re-translating a document (another engine, another language) re-renders
    identical pixmaps, so a second run can skip inference entirely. The key
    carries the model identity, so a swapped model never reads stale boxes.
    """
    if model is None or ignore_cache:
        return None
    try:
        fingerprint = Path(model.model_path).stat()
        identity = f"{model.model_path}:{fingerprint.st_mtime_ns}:{fingerprint.st_size}"
    except OSError:
        return None
    return TranslationCache(
        "layout",
        {"model": identity, "stride": model.stride},
    )


def _encode_page_layout(page_layout) -> str:
    rows = []
    for box in page_layout.boxes:
        xyxy = [float(value) for value in np.asarray(box.xyxy).ravel()[:4]]
        rows.append(xyxy + [float(box.conf), float(box.cls)])
    return json.dumps({"names": page_layout.names, "rows": rows})


def _decode_page_layout(payload: str):
    """Rebuild a cached layout result, or None when the cache entry is bad."""
    try:
        data = json.loads(payload)
        names = data["names"]
        if isinstance(names, dict):
            names = {
                int(key) if key.lstrip("-").isdigit() else key: value
                for key, value in names.items()
            }
        rows = np.array(
            [[float(value) for value in row] for row in data["rows"]],
            dtype=np.float64,
        )
        if rows.size == 0:
            rows = rows.reshape(0, 6)
        if rows.ndim != 2 or rows.shape[1] != 6:
            return None
        return YoloResult(boxes=rows, names=names)
    except (ValueError, KeyError, TypeError):
        return None


def _predict_page_layout(model, cache, pix, image, imgsz, ignore_cache):
    """Run layout inference, reusing a cached result for identical pages."""
    if cache is None:
        return model.predict(image, imgsz=imgsz)[0]
    key = f"{imgsz}:{hashlib.blake2b(pix.samples, digest_size=16).hexdigest()}"
    try:
        cached = cache.get(key)
    except Exception:
        cached = None
    if cached is not None:
        decoded = _decode_page_layout(cached)
        if decoded is not None:
            return decoded
    page_layout = model.predict(image, imgsz=imgsz)[0]
    if not ignore_cache:
        try:
            cache.set(key, _encode_page_layout(page_layout))
        except Exception:
            logger.debug("Could not cache page layout", exc_info=False)
    return page_layout


def translate_patch(
    inf: BinaryIO,
    pages: list[int] | None = None,
    vfont: str = "",
    vchar: str = "",
    thread: int = 0,
    doc_zh: Document = None,
    lang_in: str = "",
    lang_out: str = "",
    service: str = "",
    noto_name: str = "",
    noto: Font = None,
    callback: object = None,
    cancellation_event: asyncio.Event = None,
    model: OnnxModel = None,
    envs: dict = None,
    prompt: Template = None,
    ignore_cache: bool = False,
    style_font_names: dict | None = None,
    style_fonts: dict | None = None,
    synthetic_styles: set[int] | None = None,
    glossary: Any = None,
    **kwarg: Any,
) -> None:
    rsrcmgr = PDFResourceManager()
    layout = {}
    layout_bounds = {}
    # The full extent of each ordinary text region, kept apart from
    # layout_bounds because that one marks a table cell and changes how a
    # paragraph is fitted. This is only a measure to compare line ends against.
    class_bounds = {}
    scanned_pages = set()
    pages_with_images = set()
    thread = max(1, int(thread or 1))
    device = TranslateConverter(
        rsrcmgr,
        vfont,
        vchar,
        thread,
        layout,
        lang_in,
        lang_out,
        service,
        noto_name,
        noto,
        envs,
        prompt,
        ignore_cache,
        layout_bounds,
        style_font_names,
        style_fonts,
        synthetic_styles,
        class_bounds,
        glossary=glossary,
    )

    assert device is not None
    obj_patch = {}
    interpreter = PDFPageInterpreterEx(rsrcmgr, device, obj_patch)
    layout_cache = _layout_cache_for(model, ignore_cache)
    if pages:
        total_pages = len(pages)
    else:
        total_pages = doc_zh.page_count

    parser = PDFParser(inf)
    doc = PDFDocument(parser)
    with tqdm.tqdm(total=total_pages) as progress:
        for pageno, page in enumerate(PDFPage.create_pages(doc)):
            if cancellation_event and cancellation_event.is_set():
                raise CancelledError("task cancelled")
            if pages and (pageno not in pages):
                continue
            progress.update()
            if callback:
                callback(progress)
            page.pageno = pageno
            page_rect = doc_zh[page.pageno].rect
            page_area = page_rect.width * page_rect.height
            page_blocks = doc_zh[page.pageno].get_text("dict")["blocks"]
            if is_scanned_page(page_blocks, page_area):
                scanned_pages.add(pageno)
            if page_has_image(page_blocks):
                pages_with_images.add(pageno)
            # Text-classified pages need no layout inference: TOC, index,
            # nomenclature, references, and other preserved pages end fully
            # protected, and textless pages translate nothing either way.
            page_text = doc_zh[page.pageno].get_text("text")
            preserved_kind = _classify_fully_preserved_page(page_text, pageno)
            if preserved_kind is not None and preserved_kind != "TOC":
                box = np.zeros(
                    (math.ceil(page_rect.height), math.ceil(page_rect.width)),
                    dtype=np.int32,
                )
            else:
                pix = doc_zh[page.pageno].get_pixmap()
                image = np.frombuffer(pix.samples, np.uint8).reshape(
                    pix.height, pix.width, 3
                )[:, :, ::-1]
                # DocLayNet reference size: larger inputs cost pixels squared
                # while boxes rescale to page coordinates either way.
                page_layout = _predict_page_layout(
                    model,
                    layout_cache,
                    pix,
                    image,
                    min(1024, int(pix.height / 32) * 32),
                    ignore_cache,
                )
                box = np.ones((pix.height, pix.width), dtype=np.int32)
                h, w = box.shape
                x_scale = pix.width / page_rect.width if page_rect.width else 1.0
                y_scale = pix.height / page_rect.height if page_rect.height else 1.0
                vcls = ["abandon", "figure", "table", "isolate_formula", "formula_caption"]
                model_table_bounds = []
                # Process non-vcls boxes in ascending confidence order so that
                # higher-confidence boxes overwrite lower-confidence ones
                non_vcls_boxes = [
                    (i, d) for i, d in enumerate(page_layout.boxes)
                    if page_layout.names[int(d.cls)] not in vcls
                ]
                page_class_bounds = class_bounds.setdefault(page.pageno, {})
                page_pymupdf_bounds = {}
                for i, d in reversed(non_vcls_boxes):
                    x0, y0, x1, y1 = d.xyxy.squeeze()
                    region_id = i + 2
                    pt_x0 = float(x0) / x_scale
                    pt_y0 = float(y0) / y_scale
                    pt_x1 = float(x1) / x_scale
                    pt_y1 = float(y1) / y_scale
                    page_class_bounds[region_id] = (
                        pt_x0,
                        float(page_rect.height) - pt_y1,
                        pt_x1,
                        float(page_rect.height) - pt_y0,
                    )
                    page_pymupdf_bounds[region_id] = (pt_x0, pt_y0, pt_x1, pt_y1)
                    x0, y0, x1, y1 = (
                        np.clip(int(x0 - 1), 0, w - 1),
                        np.clip(int(h - y1 - 1), 0, h - 1),
                        np.clip(int(x1 + 1), 0, w - 1),
                        np.clip(int(h - y0 + 1), 0, h - 1),
                    )
                    box[y0:y1, x0:x1] = region_id
                for i, d in enumerate(page_layout.boxes):
                    name = page_layout.names[int(d.cls)]
                    if name in vcls:
                        raw_x0, raw_y0, raw_x1, raw_y1 = (
                            float(value) for value in d.xyxy.squeeze()
                        )
                        if name == "abandon":
                            d_conf = float(getattr(d, "conf", 0.0))
                            is_suppressed = False
                            for _, nv_box in non_vcls_boxes:
                                nv_xyxy = [float(v) for v in nv_box.xyxy.squeeze()]
                                nv_cls_name = page_layout.names[int(nv_box.cls)]
                                if (nv_cls_name == "title" or d_conf <= float(getattr(nv_box, "conf", 0.0))) and not (
                                    raw_x1 <= nv_xyxy[0]
                                    or raw_x0 >= nv_xyxy[2]
                                    or raw_y1 <= nv_xyxy[1]
                                    or raw_y0 >= nv_xyxy[3]
                                ):
                                    is_suppressed = True
                                    break
                            if is_suppressed:
                                continue
                        if name == "table":
                            model_table_bounds.append(
                                (raw_x0, raw_y0, raw_x1, raw_y1)
                            )
                        x0, y0, x1, y1 = raw_x0, raw_y0, raw_x1, raw_y1
                        x0, y0, x1, y1 = (
                            np.clip(int(x0 - 1), 0, w - 1),
                            np.clip(int(h - y1 - 1), 0, h - 1),
                            np.clip(int(x1 + 1), 0, w - 1),
                            np.clip(int(h - y0 + 1), 0, h - 1),
                        )
                        box[y0:y1, x0:x1] = 0

                # A model-detected table stays protected unless PyMuPDF can split
                # that same region into cells. Each reliable cell gets its own class
                # so its text is translated independently while the original grid,
                # fills and borders remain untouched.
                source_page = doc_zh[page.pageno]
                try:
                    detected_tables = source_page.find_tables().tables
                except Exception as error:
                    logger.warning(
                        "Page %s table-cell detection failed; preserving tables: %s",
                        pageno + 1,
                        error,
                    )
                    detected_tables = []
                next_class = len(page_layout.boxes) + 2
                page_bounds = layout_bounds.setdefault(page.pageno, {})
                page_height = float(page_rect.height)
                page_words = source_page.get_text("words", sort=True)
                for table_bounds in model_table_bounds:
                    for cell in matching_table_cells(table_bounds, detected_tables):
                        cx0 = max(float(cell[0]), table_bounds[0])
                        cy0 = max(float(cell[1]), table_bounds[1])
                        cx1 = min(float(cell[2]), table_bounds[2])
                        cy1 = min(float(cell[3]), table_bounds[3])
                        if cx1 - cx0 <= 4 or cy1 - cy0 <= 1:
                            continue
                        cell_words = [
                            word
                            for word in page_words
                            if cx0 <= (float(word[0]) + float(word[2])) / 2 <= cx1
                            and cy0 <= (float(word[1]) + float(word[3])) / 2 <= cy1
                        ]
                        for cluster in cluster_table_words(
                            cell_words, (cx0, cy0, cx1, cy1)
                        ):
                            if not should_translate_table_cell(cluster.text):
                                continue
                            for word in cluster.words:
                                wx0, wy0, wx1, wy1 = (
                                    float(value) for value in word[:4]
                                )
                                px0, py0, px1, py1 = (
                                    np.clip(int(wx0 - 1), 0, w - 1),
                                    np.clip(int(h - wy1 - 1), 0, h - 1),
                                    np.clip(int(wx1 + 1), 0, w - 1),
                                    np.clip(int(h - wy0 + 1), 0, h - 1),
                                )
                                box[py0:py1, px0:px1] = next_class
                            bx0, by0, bx1, by1 = cluster.bbox
                            content_y0 = min(by0, *(float(word[1]) for word in cluster.words))
                            content_y1 = max(by1, *(float(word[3]) for word in cluster.words))
                            padded = (
                                bx0 + 2.0,
                                page_height - content_y1,
                                bx1 - 2.0,
                                page_height - content_y0,
                            )
                            if padded[2] > padded[0] and padded[3] > padded[1]:
                                page_bounds[next_class] = padded
                            next_class += 1

                # Technical documents often use ordinary prose fonts for equations.
                # Protect operator-only blocks and stacked identifiers before the
                # converter can reflow them. A one-point pad catches their rules and
                # small subscripts without swallowing adjacent prose.
                fallback_formulas = formula_regions(
                    source_page.get_text("blocks", sort=True),
                    page_words,
                    stacked_exclusions=model_table_bounds,
                )
                for fx0, fy0, fx1, fy1 in fallback_formulas:
                    bx0, by0, bx1, by1 = (
                        np.clip(int(fx0 - 1), 0, w - 1),
                        np.clip(int(h - fy1 - 1), 0, h - 1),
                        np.clip(int(fx1 + 1), 0, w - 1),
                        np.clip(int(h - fy0 + 1), 0, h - 1),
                    )
                    box[by0:by1, bx0:bx1] = 0

                # Split borderless multi-column text (a symbol reference with
                # no ruling lines): one region grouping every column reflows
                # over itself. Each column slice gets its own class with a
                # narrow width budget, so paragraphs stay in their column.
                if page_words:
                    for region_id, pt_rect in list(page_pymupdf_bounds.items()):
                        slices = split_text_columns(
                            [word for word in page_words if len(word) >= 4],
                            pt_rect,
                        )
                        if len(slices) < 2:
                            continue
                        for (col_x0, col_y0, col_x1, col_y1) in slices:
                            px0 = int(np.clip(col_x0 * x_scale, 0, w - 1))
                            px1 = int(np.clip(col_x1 * x_scale, 0, w - 1))
                            py0 = int(np.clip(h - col_y1 * y_scale - 1, 0, h - 1))
                            py1 = int(np.clip(h - col_y0 * y_scale + 1, 0, h - 1))
                            if px1 <= px0 or py1 <= py0:
                                continue
                            sub_box = box[py0:py1, px0:px1]
                            column_mask = sub_box == region_id
                            if not column_mask.any():
                                continue
                            column_id = next_class
                            next_class += 1
                            sub_box[column_mask] = column_id
                            col_bound = (
                                col_x0,
                                float(page_rect.height) - col_y1,
                                col_x1,
                                float(page_rect.height) - col_y0,
                            )
                            page_class_bounds[column_id] = col_bound
                            page_bounds[column_id] = col_bound

                if page_class_bounds:
                    ro_boxes = [
                        LayoutBox(
                            id=str(cid),
                            x0=bound[0],
                            y0=bound[1],
                            x1=bound[2],
                            y1=bound[3],
                            cls=cid,
                        )
                        for cid, bound in page_class_bounds.items()
                    ]
                    ro_indices = infer_reading_order_indices(
                        ro_boxes, float(page_rect.width), float(page_rect.height)
                    )
                    device.page_reading_order[page.pageno] = [
                        ro_boxes[idx].cls for idx in ro_indices
                    ]

            layout[page.pageno] = box
            if pageno in scanned_pages:
                device.scanned_pages.add(pageno)
            if pageno in pages_with_images:
                device.pages_with_images.add(pageno)
            page.page_xref = doc_zh.get_new_xref()
            doc_zh.update_object(page.page_xref, "<<>>")
            doc_zh.update_stream(page.page_xref, b"")
            doc_zh[page.pageno].set_contents(page.page_xref)
            interpreter.process_page(page)

    translate_document_outlines(doc_zh, device.translator)
    device.close()
    return obj_patch, TranslationReport(
        failures=device.translation_failures,
        reasons=device.failure_reasons,
        image_only_pages=device.image_only_pages,
        translatable_segments=device.translatable_segments,
        pages_processed=total_pages,
    )


def translate_stream(
    stream: bytes,
    pages: list[int] | None = None,
    lang_in: str = "",
    lang_out: str = "",
    service: str = "",
    thread: int = 0,
    vfont: str = "",
    vchar: str = "",
    callback: object = None,
    cancellation_event: asyncio.Event = None,
    model: OnnxModel = None,
    envs: dict = None,
    prompt: Template = None,
    skip_subset_fonts: bool = False,
    create_dual: bool = True,
    ignore_cache: bool = False,
    glossary: Any = None,
    **kwarg: Any,
):
    thread = max(1, int(thread or 1))
    source_size = len(stream)
    font_path = download_remote_fonts(lang_out.lower())
    style_paths = output_style_font_paths(lang_out.lower(), font_path)
    style_font_names = dict(STYLE_FONT_NAMES)
    style_fonts = {
        style: Font(style_font_names[style], path)
        for style, path in style_paths.items()
    }
    synthetic_styles = {
        style for style, path in style_paths.items() if style and path == style_paths[0]
    }
    font_list = [(name, None) for name in BASE14_STYLE_FONTS.values()]
    noto_name = NOTO_NAME
    noto = style_fonts[0]
    font_list.extend(
        (style_font_names[style], path) for style, path in style_paths.items()
    )

    doc_en = Document(stream=stream)
    stream = io.BytesIO()
    doc_en.save(stream)
    doc_zh = Document(stream=stream)
    if not create_dual:
        doc_en.close()
    page_count = doc_zh.page_count
    # font_list = [("GoNotoKurrent-Regular.ttf", font_path), ("tiro", None)]
    font_id = {}
    for page in doc_zh:
        for font in font_list:
            font_id[font[0]] = page.insert_font(font[0], font[1])
    xreflen = doc_zh.xref_length()
    for xref in range(1, xreflen):
        for label in ["Resources/", ""]:
            try:
                font_res = doc_zh.xref_get_key(xref, f"{label}Font")
                target_key_prefix = f"{label}Font/"
                if font_res[0] == "xref":
                    resource_xref_id = re.search("(\\d+) 0 R", font_res[1]).group(1)
                    xref = int(resource_xref_id)
                    font_res = ("dict", doc_zh.xref_object(xref))
                    target_key_prefix = ""

                if font_res[0] == "dict":
                    for font in font_list:
                        target_key = f"{target_key_prefix}{font[0]}"
                        font_exist = doc_zh.xref_get_key(xref, target_key)
                        if font_exist[0] == "null":
                            doc_zh.xref_set_key(
                                xref,
                                target_key,
                                f"{font_id[font[0]]} 0 R",
                            )
            except Exception:
                pass

    fp = io.BytesIO()

    doc_zh.save(fp)
    obj_patch, report = translate_patch(fp, **locals())

    for obj_id, ops_new in obj_patch.items():
        # ops_old=doc_en.xref_stream(obj_id)
        # print(obj_id)
        # print(ops_old)
        # print(ops_new.encode())
        doc_zh.update_stream(obj_id, ops_new.encode())

    if create_dual:
        doc_en.insert_file(doc_zh)
        for id in range(page_count):
            doc_en.move_page(page_count + id, id * 2 + 1)
        try:
            zh_toc = doc_zh.get_toc()
            if zh_toc:
                dual_toc = []
                for item in zh_toc:
                    lvl, title, page = item[0], item[1], item[2]
                    dual_page = (page - 1) * 2 + 2 if page > 0 else page
                    dual_toc.append([lvl, title, dual_page] + list(item[3:]))
                doc_en.set_toc(dual_toc)
        except Exception as error:
            logger.debug("Failed to apply dual document outlines: %s", error)

    # Off for every document; see should_subset_fonts. It was also the
    # expensive half of finalizing a textbook, so dropping it costs nothing but
    # the size of the four embedded output faces.
    if should_subset_fonts(page_count, skip_subset_fonts, source_size):
        doc_zh.subset_fonts(fallback=True)
        if create_dual:
            doc_en.subset_fonts(fallback=True)
    write_options = pdf_write_options(page_count, source_size)
    mono = doc_zh.write(**write_options)
    dual = (
        doc_en.write(**write_options)
        if create_dual
        else None
    )
    doc_zh.close()
    if create_dual:
        doc_en.close()
    return (
        mono,
        dual,
        report,
    )


def convert_to_pdfa(input_path, output_path):
    """
    Convert PDF to PDF/A format

    Args:
        input_path: Path to source PDF file
        output_path: Path to save PDF/A file
    """
    from pikepdf import Dictionary, Name, Pdf

    # Open the PDF file
    pdf = Pdf.open(input_path)

    # Add PDF/A conformance metadata
    metadata = {
        "pdfa_part": "2",
        "pdfa_conformance": "B",
        "title": pdf.docinfo.get("/Title", ""),
        "author": pdf.docinfo.get("/Author", ""),
        "creator": "PDF Math Translate",
    }

    with pdf.open_metadata() as meta:
        meta.load_from_docinfo(pdf.docinfo)
        meta["pdfaid:part"] = metadata["pdfa_part"]
        meta["pdfaid:conformance"] = metadata["pdfa_conformance"]

    # Create OutputIntent dictionary
    output_intent = Dictionary(
        {
            "/Type": Name("/OutputIntent"),
            "/S": Name("/GTS_PDFA1"),
            "/OutputConditionIdentifier": "sRGB IEC61966-2.1",
            "/RegistryName": "http://www.color.org",
            "/Info": "sRGB IEC61966-2.1",
        }
    )

    # Add output intent to PDF root
    if "/OutputIntents" not in pdf.Root:
        pdf.Root.OutputIntents = [output_intent]
    else:
        pdf.Root.OutputIntents.append(output_intent)

    # Save as PDF/A
    pdf.save(output_path, linearize=True)
    pdf.close()


def translate(
    files: list[str],
    output: str = "",
    pages: list[int] | None = None,
    lang_in: str = "",
    lang_out: str = "",
    service: str = "",
    thread: int = 0,
    vfont: str = "",
    vchar: str = "",
    callback: object = None,
    compatible: bool = False,
    cancellation_event: asyncio.Event = None,
    model: OnnxModel = None,
    envs: dict = None,
    prompt: Template = None,
    skip_subset_fonts: bool = False,
    ignore_cache: bool = False,
    create_dual: bool = False,
    glossary: Any = None,
    **kwarg: Any,
):
    if not files:
        raise PDFValueError("No files to process.")

    missing_files = check_files(files)

    if missing_files:
        print("The following files do not exist:", file=sys.stderr)
        for file in missing_files:
            print(f"  {file}", file=sys.stderr)
        raise PDFValueError("Some files do not exist.")

    result_files = []

    for file in files:
        source_path = Path(file).resolve()
        if source_path.suffix.lower() != ".pdf":
            raise PDFValueError(f"Only PDF input is supported: {source_path}")
        filename = source_path.stem
        processing_path = source_path
        temporary_paths: list[Path] = []

        if not pymupdf_can_round_trip(source_path):
            logger.warning(
                "PDF structure issue detected in %s; translating a repaired temporary copy",
                source_path,
            )
            try:
                with tempfile.NamedTemporaryFile(suffix="-fixed.pdf", delete=False) as temporary:
                    fixed_path = Path(temporary.name)
                with pikepdf.open(source_path, suppress_warnings=True) as fixed_pdf:
                    fixed_pdf.save(fixed_path)
                processing_path = fixed_path
                temporary_paths.append(fixed_path)
            except Exception as error:
                raise PDFValueError(f"Could not repair PDF structure: {source_path}") from error
            if not pymupdf_can_round_trip(processing_path):
                # Say so here rather than letting the same MuPDF syntax error
                # resurface from deep inside the conversion, where it reads as
                # an engine bug instead of an unreadable source document.
                raise PDFValueError(
                    f"PDF structure is damaged beyond repair: {source_path}"
                )

        if compatible:
            with tempfile.NamedTemporaryFile(suffix="-pdfa.pdf", delete=False) as temporary:
                pdfa_path = Path(temporary.name)
            convert_to_pdfa(processing_path, pdfa_path)
            processing_path = pdfa_path
            temporary_paths.append(pdfa_path)

        s_raw = processing_path.read_bytes()
        for temporary_path in temporary_paths:
            temporary_path.unlink(missing_ok=True)

        try:
            s_mono, _s_dual, report = translate_stream(
                s_raw,
                create_dual=create_dual,
                pages=pages,
                lang_in=lang_in,
                lang_out=lang_out,
                service=service,
                thread=thread,
                vfont=vfont,
                vchar=vchar,
                callback=callback,
                cancellation_event=cancellation_event,
                model=model,
                envs=envs,
                prompt=prompt,
                skip_subset_fonts=skip_subset_fonts,
                ignore_cache=ignore_cache,
                glossary=glossary,
                **kwarg,
            )
            if report.failures:
                logger.warning(
                    "%d of the segments in %s could not be translated and were left "
                    "in the source language (%s)",
                    len(report.failures),
                    source_path,
                    ", ".join(
                        f"{reason} x{count}"
                        for reason, count in report.reasons.most_common()
                    ),
                )
            file_mono = Path(output) / f"{filename}-mono.pdf"
            with open(file_mono, "wb") as doc_mono:
                doc_mono.write(s_mono)
            if create_dual and _s_dual:
                file_dual = Path(output) / f"{filename}-dual.pdf"
                with open(file_dual, "wb") as doc_dual:
                    doc_dual.write(_s_dual)
            result_files.append((str(file_mono), report))
        except Exception as error:
            raise PDFValueError(f"Failed to translate {source_path}") from error

    return result_files


def download_remote_fonts(lang: str):
    lang = lang.lower()
    LANG_NAME_MAP = {
        **{la: "GoNotoKurrent-Regular.ttf" for la in noto_list},
        **{
            la: f"SourceHanSerif{region}-Regular.ttf"
            for region, langs in {
                "CN": ["zh-cn", "zh-hans", "zh"],
                "TW": ["zh-tw", "zh-hant"],
                "JP": ["ja"],
                "KR": ["ko"],
            }.items()
            for la in langs
        },
    }

    font_name = LANG_NAME_MAP.get(lang, "GoNotoKurrent-Regular.ttf")

    # Vietnamese font preference
    if lang == "vi":
        for vi_candidate in (
            Path("C:/Windows/Fonts/times.ttf"),
            Path("C:/Windows/Fonts/arial.ttf"),
            Path("/System/Library/Fonts/Times.ttc"),
            Path("/Library/Fonts/Times New Roman.ttf"),
        ):
            if vi_candidate.exists():
                logger.info(f"use font for vi: {vi_candidate.as_posix()}")
                return vi_candidate.as_posix()

    font_path = None

    # Only inherit NOTO_FONT_PATH if the required font is GoNotoKurrent (non-CJK)
    if font_name == "GoNotoKurrent-Regular.ttf" and "NOTO_FONT_PATH" in os.environ:
        cand = Path(os.environ["NOTO_FONT_PATH"])
        if cand.exists():
            font_path = cand.as_posix()

    # Check bundled assets directory
    if not font_path:
        bundled = Path(__file__).resolve().parents[1] / "app" / "assets" / font_name
        if bundled.exists():
            font_path = bundled.as_posix()

    # Check system fonts for CJK as high-performance offline fallback
    if not font_path:
        system_cjk: dict[str, list[str]] = {
            "zh": ["C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simsun.ttc", "/System/Library/Fonts/PingFang.ttc"],
            "zh-cn": ["C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simsun.ttc", "/System/Library/Fonts/PingFang.ttc"],
            "zh-hans": ["C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simsun.ttc", "/System/Library/Fonts/PingFang.ttc"],
            "zh-tw": ["C:/Windows/Fonts/msjh.ttc", "C:/Windows/Fonts/mingliu.ttc"],
            "zh-hant": ["C:/Windows/Fonts/msjh.ttc", "C:/Windows/Fonts/mingliu.ttc"],
            "ja": ["C:/Windows/Fonts/meiryo.ttc", "C:/Windows/Fonts/msgothic.ttc", "C:/Windows/Fonts/YuGothM.ttc"],
            "ko": ["C:/Windows/Fonts/malgun.ttf"],
        }
        for candidate in system_cjk.get(lang, []):
            if Path(candidate).exists():
                font_path = candidate
                break

    # Download or load from cache via babeldoc
    if not font_path or not Path(font_path).exists():
        try:
            font_path, _ = get_font_and_metadata(font_name)
            font_path = font_path.as_posix()
        except Exception:
            # Final backstop
            font_path = os.environ.get("NOTO_FONT_PATH", "GoNotoKurrent-Regular.ttf")

    logger.info(f"use font: {font_path}")
    return font_path
