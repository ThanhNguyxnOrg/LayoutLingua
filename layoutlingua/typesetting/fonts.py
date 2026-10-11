"""Font asset management, checksum verification, and Vietnamese glyph validation."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pymupdf

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
        self._verified: bool = False

    @property
    def font_path(self) -> Path:
        return self._font_path

    def get_font_buffer(self) -> bytes:
        """Return raw font bytes, cached in memory."""
        if self._font_buffer is None:
            self._font_buffer = self._font_path.read_bytes()
        return self._font_buffer

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
        font = pymupdf.Font(fontbuffer=self.get_font_buffer())
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
        buf = self.get_font_buffer()
        page.insert_font(fontname=font_name, fontbuffer=buf)
        return font_name
