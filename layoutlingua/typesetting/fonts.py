"""Font asset management, checksum verification, and multi-family DejaVu font selection."""

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


CJK_FONT_ALIASES: dict[str, str] = {
    "cjk-sim": "china-s",
    "cjk-trad": "china-t",
    "cjk-jp": "japan",
    "cjk-kr": "korea",
    "china-s": "china-s",
    "china-t": "china-t",
    "japan": "japan",
    "korea": "korea",
}

CJK_EMBED_FONTS = frozenset(CJK_FONT_ALIASES.keys())

BUILTIN_OR_CJK_FONTS = frozenset({
    *CJK_FONT_ALIASES.keys(),
    "tiro", "tibo", "tiit", "tibi",
    "helv", "hebo", "heit", "hebi",
    "couri", "cobo", "coit", "cobi",
    "times-roman", "times-bold", "times-italic", "times-bolditalic",
    "helvetica", "courier",
})

_FONT_VARIANT_FILES: dict[str, str] = {
    "freeserif": "FreeSerif.ttf",
    "freeserif-bold": "FreeSerifBold.ttf",
    "freeserif-italic": "FreeSerifItalic.ttf",
    "freeserif-bolditalic": "FreeSerifBoldItalic.ttf",
    "freesans": "FreeSans.ttf",
    "freesans-bold": "FreeSansBold.ttf",
    "freesans-italic": "FreeSansOblique.ttf",
    "freesans-oblique": "FreeSansOblique.ttf",
    "freesans-bolditalic": "FreeSansBoldOblique.ttf",
    "freesans-boldoblique": "FreeSansBoldOblique.ttf",
    "dejavusans": "DejaVuSans.ttf",
    "dejavusans-bold": "DejaVuSans-Bold.ttf",
    "dejavusans-italic": "DejaVuSans-Oblique.ttf",
    "dejavusans-oblique": "DejaVuSans-Oblique.ttf",
    "dejavusans-bolditalic": "DejaVuSans-BoldOblique.ttf",
    "dejavusans-boldoblique": "DejaVuSans-BoldOblique.ttf",
    "dejavuserif": "DejaVuSerif.ttf",
    "dejavuserif-bold": "DejaVuSerif-Bold.ttf",
    "dejavuserif-italic": "DejaVuSerif-Italic.ttf",
    "dejavuserif-bolditalic": "DejaVuSerif-BoldItalic.ttf",
    "dejavuserifcondensed": "DejaVuSerifCondensed.ttf",
    "dejavuserifcondensed-bold": "DejaVuSerifCondensed-Bold.ttf",
    "dejavuserifcondensed-italic": "DejaVuSerifCondensed-Italic.ttf",
    "dejavuserifcondensed-bolditalic": "DejaVuSerifCondensed-BoldItalic.ttf",
    "dejavusansmono": "DejaVuSansMono.ttf",
    "dejavusansmono-bold": "DejaVuSansMono-Bold.ttf",
}


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

        self._assets_dir = self._font_path.parent
        self._bold_font_path = (self._assets_dir / "DejaVuSans-Bold.ttf").resolve()

        self._font_buffers: dict[Path, bytes] = {}
        self._font_objs: dict[Path, pymupdf.Font] = {}

    @property
    def font_path(self) -> Path:
        return self._font_path

    def select_font_variant(
        self,
        *,
        serif: bool = False,
        bold: bool = False,
        italic: bool = False,
        mono: bool = False,
        condensed: bool = False,
    ) -> str:
        """Select the best matching bundled metric-compatible font family & style name."""
        if mono:
            cand = "DejaVuSansMono-Bold" if bold else "DejaVuSansMono"
        elif serif:
            if condensed:
                base = "DejaVuSerifCondensed"
            else:
                base = "FreeSerif" if (self._assets_dir / "FreeSerif.ttf").is_file() else "DejaVuSerif"
            if bold and italic:
                cand = f"{base}-BoldItalic"
            elif bold:
                cand = f"{base}-Bold"
            elif italic:
                cand = f"{base}-Italic"
            else:
                cand = base
        else:
            has_freesans = (self._assets_dir / "FreeSans.ttf").is_file()
            base_sans = "FreeSans" if has_freesans else "DejaVuSans"
            if bold and italic:
                cand = f"{base_sans}-BoldOblique"
            elif bold:
                cand = f"{base_sans}-Bold"
            elif italic:
                cand = f"{base_sans}-Oblique"
            else:
                cand = base_sans

        if self.get_font_path(cand).is_file():
            return cand
        return "DejaVuSans-Bold" if bold else "DejaVuSans"

    def get_font_path(self, font_name: str | None = None) -> Path:
        """Return the filesystem path for the requested font variant."""
        if font_name:
            key = font_name.strip().lower()
            mapped = _FONT_VARIANT_FILES.get(key)
            if mapped:
                cand_path = (self._assets_dir / mapped).resolve()
                if cand_path.is_file():
                    return cand_path
            if "bold" in key or "hebo" in key:
                if self._bold_font_path.is_file():
                    return self._bold_font_path
        return self._font_path

    def get_font_buffer(self, font_name: str | None = None) -> bytes:
        """Return raw font bytes for the requested variant, cached in memory."""
        if font_name and font_name.lower() in CJK_EMBED_FONTS:
            f_obj = self.get_font(font_name)
            return bytes(f_obj.buffer)
        path = self.get_font_path(font_name)
        buf = self._font_buffers.get(path)
        if buf is None:
            buf = path.read_bytes()
            self._font_buffers[path] = buf
        return buf

    def get_font(self, font_name: str | None = None) -> pymupdf.Font:
        """Return cached PyMuPDF Font instance for the requested variant."""
        if font_name and font_name.lower() in BUILTIN_OR_CJK_FONTS:
            fn_low = font_name.lower()
            mupdf_name = CJK_FONT_ALIASES.get(fn_low, font_name)
            key_path = Path(f"__builtin__/{mupdf_name.lower()}")
            cached = self._font_objs.get(key_path)
            if cached is not None:
                return cached
            try:
                f_obj = pymupdf.Font(fontname=mupdf_name)
                self._font_objs[key_path] = f_obj
                return f_obj
            except Exception:
                pass
        path = self.get_font_path(font_name)
        font_obj = self._font_objs.get(path)
        if font_obj is None:
            font_obj = pymupdf.Font(fontbuffer=self.get_font_buffer(font_name))
            self._font_objs[path] = font_obj
        return font_obj

    def get_font_metrics(self) -> tuple[float, float]:
        """Return (ascender, descender) normalized in em units."""
        font = self.get_font()
        return float(font.ascender), float(font.descender)

    def calculate_effective_lineheight(
        self,
        configured_ratio: float = 1.20,
        safety_padding_em: float = 0.03,
    ) -> float:
        """Calculate dynamic line-height floor from actual font ascender/descender metrics."""
        try:
            asc, desc = self.get_font_metrics()
            if asc > 0 and desc < 0:
                metric_height = asc - desc
                return max(configured_ratio, metric_height + safety_padding_em)
        except Exception as exc:
            logger.warning("Failed to extract font metrics; using configured lineheight: %s", exc)

        return configured_ratio

    def measure_text_length(self, text: str, fontsize: float, font_name: str | None = None) -> float:
        """Measure horizontal advance width of a string in points."""
        return float(self.get_font(font_name).text_length(text, fontsize=fontsize))

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
        """Verify that all composite Vietnamese characters have valid glyphs in the font."""
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
        fn_low = font_name.lower()
        if fn_low in CJK_EMBED_FONTS:
            buf = self.get_font_buffer(font_name)
            page.insert_font(fontname=font_name, fontbuffer=buf)
            return font_name
        if fn_low in BUILTIN_OR_CJK_FONTS:
            return font_name
        buf = self.get_font_buffer(font_name)
        page.insert_font(fontname=font_name, fontbuffer=buf)
        return font_name
