"""Vision-based document layout detection using ONNX models (e.g. DocLayout-YOLO).

This module provides high-speed, CPU-friendly document layout analysis using
ONNXRuntime and OpenCV, allowing LayoutLingua to accurately segment complex
scientific documents into titles, paragraphs, tables, figures, formulas, and footers.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Sequence
import logging

import cv2
import numpy as np

try:
    import onnxruntime as ort
except ImportError:
    ort = None  # type: ignore[assignment]

from layoutlingua.core.ir import GlyphSpan

logger = logging.getLogger(__name__)


class LayoutCategory(str, Enum):
    """Semantic layout category for detected regions."""

    TITLE = "title"
    TEXT = "text"
    FIGURE = "figure"
    TABLE = "table"
    FORMULA = "formula"
    HEADER = "header"
    FOOTER = "footer"
    CAPTION = "caption"
    UNKNOWN = "unknown"


# Standard class index mapping for DocLayout-YOLO models
DEFAULT_DOCLAYOUT_YOLO_CLASSES: dict[int, LayoutCategory] = {
    0: LayoutCategory.TITLE,
    1: LayoutCategory.TEXT,
    2: LayoutCategory.UNKNOWN,       # abandon / noise
    3: LayoutCategory.FIGURE,
    4: LayoutCategory.CAPTION,      # figure caption
    5: LayoutCategory.TABLE,
    6: LayoutCategory.CAPTION,      # table caption
    7: LayoutCategory.FOOTER,       # table footnote / page footer
    8: LayoutCategory.FORMULA,      # isolate display formula
    9: LayoutCategory.CAPTION,      # formula caption
}


@dataclass(slots=True, frozen=True)
class LayoutRegion:
    """A detected semantic region on a document page.
    
    Coordinates are in original page pixel/point space: (x0, y0, x1, y1).
    """

    bbox: tuple[float, float, float, float]
    category: LayoutCategory
    score: float

    @property
    def x0(self) -> float:
        return self.bbox[0]

    @property
    def y0(self) -> float:
        return self.bbox[1]

    @property
    def x1(self) -> float:
        return self.bbox[2]

    @property
    def y1(self) -> float:
        return self.bbox[3]

    @property
    def width(self) -> float:
        return max(0.0, self.x1 - self.x0)

    @property
    def height(self) -> float:
        return max(0.0, self.y1 - self.y0)

    @property
    def area(self) -> float:
        return self.width * self.height


class OnnxLayoutDetector:
    """Pluggable ONNX layout detector compatible with DocLayout-YOLO and YOLOv8/10.
    
    Designed to be lightweight and CPU-efficient with onnxruntime and cv2.
    If no model path is provided or the file is missing, `is_available()` returns False
    and gracefully falls back to empty detections without error.
    """

    def __init__(
        self,
        model_path: str | Path | None = None,
        conf_threshold: float = 0.35,
        iou_threshold: float = 0.45,
        class_mapping: dict[int, LayoutCategory] | None = None,
    ) -> None:
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold
        self.class_mapping = class_mapping or DEFAULT_DOCLAYOUT_YOLO_CLASSES
        self._session: Any = None
        self._input_name: str = ""
        self._input_shape: tuple[int, ...] = (1, 3, 1024, 1024)

        if model_path is not None:
            self.load_model(model_path)

    def is_available(self) -> bool:
        """Check whether an active ONNX inference session is loaded."""
        return self._session is not None

    def load_model(self, model_path: str | Path) -> bool:
        """Load an ONNX model from disk."""
        path = Path(model_path)
        if not path.is_file():
            logger.warning("ONNX model file not found at %s", path)
            self._session = None
            return False

        if ort is None:
            logger.warning("onnxruntime is not installed; cannot load ONNX model.")
            return False

        try:
            # Opt for CPUExecutionProvider by default for cross-platform stability
            providers = ["CPUExecutionProvider"]
            self._session = ort.InferenceSession(str(path), providers=providers)
            inputs = self._session.get_inputs()
            if inputs:
                self._input_name = inputs[0].name
                shape = inputs[0].shape
                # If static shape e.g. [1, 3, 1024, 1024]
                if len(shape) == 4 and isinstance(shape[2], int) and isinstance(shape[3], int):
                    self._input_shape = tuple(shape)
            logger.info("Successfully loaded ONNX layout model from %s", path)
            return True
        except Exception as exc:
            logger.error("Failed to load ONNX model from %s: %s", path, exc)
            self._session = None
            return False

    def letterbox(
        self,
        image: np.ndarray,
        target_size: tuple[int, int] = (1024, 1024),
    ) -> tuple[np.ndarray, float, tuple[float, float]]:
        """Resize and pad image while preserving aspect ratio.
        
        Returns:
            (padded_image, scale_ratio, (pad_left, pad_top))
        """
        shape = image.shape[:2]  # (h, w)
        target_h, target_w = target_size

        ratio = min(target_h / shape[0], target_w / shape[1])
        new_unpad_w = int(round(shape[1] * ratio))
        new_unpad_h = int(round(shape[0] * ratio))

        dw = (target_w - new_unpad_w) / 2.0
        dh = (target_h - new_unpad_h) / 2.0

        if shape[1] != new_unpad_w or shape[0] != new_unpad_h:
            resized = cv2.resize(image, (new_unpad_w, new_unpad_h), interpolation=cv2.INTER_LINEAR)
        else:
            resized = image

        top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
        left, right = int(round(dw - 0.1)), int(round(dw + 0.1))

        padded = cv2.copyMakeBorder(
            resized, top, bottom, left, right, cv2.BORDER_CONSTANT, value=(114, 114, 114)
        )
        return padded, ratio, (left, top)

    def preprocess(
        self,
        image: np.ndarray,
    ) -> tuple[np.ndarray, float, tuple[float, float]]:
        """Prepare image for model inference: letterbox, BGR->RGB, HWC->CHW, normalize."""
        target_h = self._input_shape[2] if len(self._input_shape) >= 4 else 1024
        target_w = self._input_shape[3] if len(self._input_shape) >= 4 else 1024

        padded, ratio, (pad_x, pad_y) = self.letterbox(image, (target_h, target_w))
        
        # Convert BGR to RGB
        if len(padded.shape) == 3 and padded.shape[2] == 3:
            rgb = cv2.cvtColor(padded, cv2.COLOR_BGR2RGB)
        else:
            rgb = padded

        # Normalize to [0.0, 1.0] and transpose to (1, 3, H, W)
        blob = rgb.astype(np.float32) / 255.0
        if len(blob.shape) == 3:
            blob = np.transpose(blob, (2, 0, 1))
        blob = np.expand_dims(blob, axis=0)
        return np.ascontiguousarray(blob), ratio, (pad_x, pad_y)

    def postprocess(
        self,
        raw_outputs: list[np.ndarray],
        orig_shape: tuple[int, int],
        ratio: float,
        pad: tuple[float, float],
    ) -> list[LayoutRegion]:
        """Convert model output tensors to LayoutRegion objects with original coordinates."""
        if not raw_outputs:
            return []

        out = raw_outputs[0]
        orig_h, orig_w = orig_shape
        pad_x, pad_y = pad

        boxes_list: list[list[int]] = []
        confidences_list: list[float] = []
        class_ids_list: list[int] = []

        # Case 1: YOLO format with shape (1, 6, N) or (1, num_anchors, 4 + num_classes)
        # or (1, num_preds, 6) e.g. [x1, y1, x2, y2, score, cls_id]
        if out.ndim == 3:
            # If shape is (1, C, N), transpose to (1, N, C)
            if out.shape[1] < out.shape[2] and out.shape[1] in (6, 14, 84):
                out = np.transpose(out, (0, 2, 1))

            preds = out[0]  # shape (N, C)
            num_cols = preds.shape[1]

            if num_cols == 6:
                # Direct format: x1, y1, x2, y2, score, class_id
                for row in preds:
                    score = float(row[4])
                    if score < self.conf_threshold:
                        continue
                    cls_id = int(row[5])
                    x1, y1, x2, y2 = row[:4]
                    w = x2 - x1
                    h = y2 - y1
                    boxes_list.append([int(x1), int(y1), int(w), int(h)])
                    confidences_list.append(score)
                    class_ids_list.append(cls_id)
            elif num_cols > 4:
                # Center format: cx, cy, w, h, class_scores...
                boxes_xywh = preds[:, :4]
                scores_all = preds[:, 4:]
                cls_ids = np.argmax(scores_all, axis=1)
                max_scores = np.max(scores_all, axis=1)

                valid_mask = max_scores >= self.conf_threshold
                valid_boxes = boxes_xywh[valid_mask]
                valid_scores = max_scores[valid_mask]
                valid_classes = cls_ids[valid_mask]

                for box, score, cls_id in zip(valid_boxes, valid_scores, valid_classes):
                    cx, cy, w, h = box
                    x1 = cx - w / 2.0
                    y1 = cy - h / 2.0
                    boxes_list.append([int(x1), int(y1), int(w), int(h)])
                    confidences_list.append(float(score))
                    class_ids_list.append(int(cls_id))

        if not boxes_list:
            return []

        # Run Non-Maximum Suppression (NMS)
        indices = cv2.dnn.NMSBoxes(
            boxes_list,
            confidences_list,
            self.conf_threshold,
            self.iou_threshold,
        )

        regions: list[LayoutRegion] = []
        if len(indices) == 0:
            return regions

        indices_flat = indices.flatten() if hasattr(indices, "flatten") else [i[0] for i in indices]

        for idx in indices_flat:
            bx, by, bw, bh = boxes_list[idx]
            score = confidences_list[idx]
            cls_id = class_ids_list[idx]

            # Scale back to original image coordinates
            x0 = (bx - pad_x) / ratio
            y0 = (by - pad_y) / ratio
            x1 = (bx + bw - pad_x) / ratio
            y1 = (by + bh - pad_y) / ratio

            # Clip to page bounds
            x0 = max(0.0, min(float(orig_w), x0))
            y0 = max(0.0, min(float(orig_h), y0))
            x1 = max(0.0, min(float(orig_w), x1))
            y1 = max(0.0, min(float(orig_h), y1))

            if x1 <= x0 or y1 <= y0:
                continue

            category = self.class_mapping.get(cls_id, LayoutCategory.UNKNOWN)
            regions.append(
                LayoutRegion(
                    bbox=(x0, y0, x1, y1),
                    category=category,
                    score=round(score, 4),
                )
            )

        # Sort regions in top-to-bottom reading order
        regions.sort(key=lambda r: (r.y0, r.x0))
        return regions

    def detect(self, image: np.ndarray | bytes) -> list[LayoutRegion]:
        """Detect document layout regions on the given image.
        
        Args:
            image: A BGR/RGB numpy array or raw encoded image bytes (PNG/JPEG).
        
        Returns:
            List of detected LayoutRegion objects sorted top-to-bottom.
        """
        if not self.is_available():
            return []

        if isinstance(image, (bytes, bytearray)):
            img_arr = cv2.imdecode(np.frombuffer(image, np.uint8), cv2.IMREAD_COLOR)
            if img_arr is None:
                return []
        else:
            img_arr = image

        orig_shape = img_arr.shape[:2]  # (h, w)
        blob, ratio, pad = self.preprocess(img_arr)

        try:
            raw_outputs = self._session.run(None, {self._input_name: blob})
            return self.postprocess(raw_outputs, orig_shape, ratio, pad)
        except Exception as exc:
            logger.error("Inference failed in OnnxLayoutDetector: %s", exc)
            return []

    def classify_spans(
        self,
        spans: Sequence[GlyphSpan],
        regions: Sequence[LayoutRegion],
        overlap_threshold: float = 0.4,
    ) -> dict[LayoutCategory, list[GlyphSpan]]:
        """Assign GlyphSpans to detected layout regions based on spatial overlap.
        
        Returns:
            Dictionary mapping each LayoutCategory to list of spans contained in it.
        """
        result: dict[LayoutCategory, list[GlyphSpan]] = {
            cat: [] for cat in LayoutCategory
        }

        for span in spans:
            sx0, sy0, sx1, sy1 = span.bbox
            span_area = max(1e-5, (sx1 - sx0) * (sy1 - sy0))
            assigned = False

            for reg in regions:
                # Compute intersection
                ix0 = max(sx0, reg.x0)
                iy0 = max(sy0, reg.y0)
                ix1 = min(sx1, reg.x1)
                iy1 = min(sy1, reg.y1)

                if ix1 > ix0 and iy1 > iy0:
                    inter_area = (ix1 - ix0) * (iy1 - iy0)
                    overlap_ratio = inter_area / span_area
                    if overlap_ratio >= overlap_threshold:
                        result[reg.category].append(span)
                        assigned = True
                        break

            if not assigned:
                result[LayoutCategory.TEXT].append(span)

        return result

    @staticmethod
    def to_ir_regions(
        regions: Sequence[LayoutRegion],
        page_num: int,
    ) -> list[Any]:
        """Convert detected LayoutRegions into LayoutLingua core IR LayoutRegion objects."""
        from layoutlingua.core.ir import LayoutRegion as CoreLayoutRegion

        ir_regions: list[CoreLayoutRegion] = []
        for idx, reg in enumerate(regions):
            ir_regions.append(
                CoreLayoutRegion(
                    region_id=f"p{page_num}_onnx_{idx}",
                    bbox=reg.bbox,
                    category=reg.category.value,
                    confidence=min(1.0, max(0.0, reg.score)),
                    source="doclayout_yolo",
                    metadata={"category": reg.category.value},
                )
            )
        return ir_regions
