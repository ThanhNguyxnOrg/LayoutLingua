"""Font asset management, checksum verification, and Vietnamese glyph validation."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any

import pymupdf

logger = logging.getLogger(__name__)

EXPECTED_DEJAVU_SHA256 = "3fdf69cabf06049ea70a00b5919340e2ce1e6d02b0cc3c4b44fb6801bd1e0d22"

VIETNAMESE_TEST_CHARACTERS = (
    "aAăĂâÂđĐeEêÊiIoOôÔơƠuUưƯyYáàảãạấầẩẫậắằẳẵặéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ"
)


class FontValidationError(Exception):
    """Raised when bundled font asset is missing, corrupted, or lacks required glyphs."""


class FontManager:
    """Manages version-pinned Unicode fonts for deterministic cross-platform rendering."""

    def __init__(self, font_path: str | Path | None = None) -> None:
        if font_path is not None:
            self._font_path = Path(font_path).resolve()
        else:
            self._font_path = (
                Path(__file__).parent / "assets" / "fonts" / "DejaVuSans.ttf"
            ).resolve()

        if not self._font_path.is_file():
            raise FontValidationError(
                f"Bundled Unicode font asset not found at: {self._font_path}"
            )

        self._font_buffer: bytes | None = None
        self._font_obj: pymupdf.Font | None = None

    @property
    def font_path(self) -> Path:
        return self._font_path

    def get_font_buffer(self) -> bytes:
        """Return raw font bytes, cached in memory."""
        if self._font_buffer is None:
            self._font_buffer = self._font_path.read_bytes()
        return self._font_buffer

    def get_font(self) -> pymupdf.Font:
        """Return cached PyMuPDF Font instance."""
        if self._font_obj is None:
            self._font_obj = pymupdf.Font(fontbuffer=self.get_font_buffer())
        return self._font_obj

    def get_font_metrics(self) -> tuple[float, float]:
        """Return (ascender, descender) normalized in em units."""
        font = self.get_font()
        return float(font.ascender), float(font.descender)

    def calculate_effective_lineheight(
        self,
        configured_ratio: float = 1.20,
        safety_padding_em: float = 0.03,
    ) -> float:
        """Calculate dynamic line-height floor from actual font ascender/descender metrics.
        
        Formula:
            L_effective = max(L_configured, ascender - descender + p)
        where descender is negative, so ascender - descender represents total glyph height in em units.
        """
        try:
            asc, desc = self.get_font_metrics()
            if asc > 0 and desc < 0:
                metric_height = asc - desc  # e.g., 0.928 - (-0.236) = 1.164 em
                return max(configured_ratio, metric_height + safety_padding_em)
        except Exception as exc:
            logger.warning("Failed to extract font metrics; using configured lineheight: %s", exc)

        return configured_ratio

    def measure_text_length(self, text: str, fontsize: float) -> float:
        """Measure horizontal advance width of a string in points."""
        return float(self.get_font().text_length(text, fontsize=fontsize))

    def verify_checksum(self, expected_sha256: str = EXPECTED_DEJAVU_SHA256) -> bool:
        """Verify font file integrity against expected SHA-256 hash."""
        buf = self.get_font_buffer()
        actual = hashlib.sha256(buf).hexdigest()
        if actual != expected_sha256:
            raise FontValidationError(
                f"Font checksum mismatch for {self._font_path.name}: "
                f"expected {expected_sha256}, got {actual}"
            )
        return True

    def validate_vietnamese_glyphs(self) -> list[str]:
        """Verify that all composite Vietnamese characters have valid glyphs in the font.
        
        Returns a list of missing characters (empty if 100% coverage is verified).
        """
        font = self.get_font()
        missing: list[str] = []
        for char in VIETNAMESE_TEST_CHARACTERS:
            codepoint = ord(char)
            if not font.has_glyph(codepoint):
                missing.append(char)
        if missing:
            raise FontValidationError(
                f"Font {self._font_path.name} lacks glyphs for Vietnamese characters: {missing}"
            )
        return missing

    def register_on_page(self, page: Any, font_name: str = "DejaVuSans") -> str:
        """Register the font asset into the given PyMuPDF page resource dictionary."""
        if font_name in ("china-s", "china-t", "japan", "korea"):
            return font_name
        buf = self.get_font_buffer()
        page.insert_font(fontname=font_name, fontbuffer=buf)
        return font_name
