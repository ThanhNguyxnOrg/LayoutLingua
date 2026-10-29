"""Legacy Vietnamese font encoding normalizer (VNI Windows & TCVN3/ABC).

Word 2003 / MathType math textbooks frequently store Vietnamese prose in
VNI-Times or .VnTime fonts without Unicode CMaps.
Unverified or unrecognized encodings are preserved as original text with
warnings, adhering strictly to the Fail-Closed preservation principle.
"""

from __future__ import annotations

import re
from typing import Any

from layoutlingua.processing.normalizers.base import BaseTextNormalizer, NormalizationResult

# VNI Windows Replacement Table ported from TS Engine (`pdfTranslator.ts`):
# Ordered carefully so:
# 1. Composite VNI horn pairs (ôù -> ớ, ôø -> ờ, ôû -> ở, ôõ -> ỡ, ôï -> ợ) run first
# 2. Bare VNI horn ('ô' -> 'ơ', 'Ô' -> 'Ơ') runs BEFORE 'oâ' -> 'ô' so 'oâ' does not get clobbered into 'ơ'
_VNI_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    # Spaced VNI composite pairs
    ("o ù", "ó"), ("o ø", "ò"), ("o û", "ỏ"), ("o õ", "õ"), ("o ï", "ọ"),
    ("o á", "ố"), ("o à", "ồ"), ("o å", "ổ"), ("o ã", "ỗ"), ("o ä", "ộ"),
    ("ô ù", "ớ"), ("ô ø", "ờ"), ("ô û", "ở"), ("ô õ", "ỡ"), ("ô ï", "ợ"),
    ("a ù", "á"), ("a ø", "à"), ("a û", "ả"), ("a õ", "ã"), ("a ï", "ạ"),
    ("a á", "ấ"), ("a à", "ầ"), ("a å", "ẩ"), ("a ã", "ẫ"), ("a ä", "ậ"), ("a â", "â"),
    ("a é", "ắ"), ("a è", "ằ"), ("a ú", "ẳ"), ("a ü", "ẵ"), ("a ë", "ặ"), ("a ê", "ă"),
    ("e ù", "é"), ("e ø", "è"), ("e û", "ẻ"), ("e õ", "ẽ"), ("e ï", "ẹ"),
    ("e á", "ế"), ("e à", "ề"), ("e å", "ể"), ("e ã", "ễ"), ("e ä", "ệ"), ("e â", "ê"),
    ("i ù", "í"), ("i ø", "ì"), ("i û", "ỉ"), ("i õ", "ĩ"), ("i ï", "ị"),
    ("u ù", "ú"), ("u ø", "ù"), ("u û", "ủ"), ("u õ", "ũ"), ("u ï", "ụ"),
    ("ö ù", "ứ"), ("ö ø", "ừ"), ("ö û", "ử"), ("ö õ", "ữ"), ("ö ï", "ự"),
    ("y ù", "ý"), ("y ø", "ỳ"), ("y û", "ỷ"), ("y õ", "ỹ"), ("y ï", "ỵ"),
    # Standard VNI horn composite pairs (must precede bare 'ô' -> 'ơ')
    ("ôù", "ớ"), ("ôø", "ờ"), ("ôû", "ở"), ("ôõ", "ỡ"), ("ôï", "ợ"),
    ("ÔÙ", "Ớ"), ("ÔØ", "Ờ"), ("ÔÛ", "Ở"), ("ÔÕ", "Ỡ"), ("ÔÏ", "Ợ"),
    # Bare VNI horn ('ô' -> 'ơ') BEFORE 'oâ' -> 'ô' so 'oâ' is not clobbered into 'ơ'
    ("ô", "ơ"), ("Ô", "Ơ"),
    # Words with VNI prefix stems
    ("vo ânghieäm", "vô nghiệm"),
    ("vo â nghieäm", "vô nghiệm"),
    ("voâ nghieäm", "vô nghiệm"),
    ("voânghieäm", "vô nghiệm"),
    ("vo â", "vô "),
    ("voâ", "vô"),
    ("Vo â", "Vô "),
    ("Voâ", "Vô"),
    ("VO Â", "VÔ "),
    ("VOÂ", "VÔ"),
    ("o â", "ô"), ("O Â", "Ô"),
    # Standard VNI composite pairs (including full i/y/u/o/a/e coverage from TS engine)
    ("oá", "ố"), ("oà", "ồ"), ("oå", "ổ"), ("oã", "ỗ"), ("oä", "ộ"), ("oâ", "ô"),
    ("où", "ó"), ("oø", "ò"), ("oû", "ỏ"), ("oõ", "õ"), ("oï", "ọ"),
    ("aá", "ấ"), ("aà", "ầ"), ("aå", "ẩ"), ("aã", "ẫ"), ("aä", "ậ"), ("aâ", "â"),
    ("aé", "ắ"), ("aè", "ằ"), ("aú", "ẳ"), ("aü", "ẵ"), ("aë", "ặ"), ("aê", "ă"),
    ("aù", "á"), ("aø", "à"), ("aû", "ả"), ("aõ", "ã"), ("aï", "ạ"),
    ("eá", "ế"), ("eà", "ề"), ("eå", "ể"), ("eã", "ễ"), ("eä", "ệ"), ("eâ", "ê"),
    ("eù", "é"), ("eø", "è"), ("eû", "ẻ"), ("eõ", "ẽ"), ("eï", "ẹ"),
    ("iù", "í"), ("iø", "ì"), ("iû", "ỉ"), ("iõ", "ĩ"), ("iï", "ị"),
    ("öù", "ứ"), ("öø", "ừ"), ("öû", "ử"), ("öõ", "ữ"), ("öï", "ự"), ("ö", "ư"),
    ("uù", "ú"), ("uø", "ù"), ("uû", "ủ"), ("uõ", "ũ"), ("uï", "ụ"),
    ("yù", "ý"), ("yø", "ỳ"), ("yû", "ỷ"), ("yõ", "ỹ"), ("yï", "ỵ"),
    # Uppercase VNI composite pairs
    ("OÙ", "Ó"), ("OØ", "Ò"), ("OÛ", "Ỏ"), ("OÕ", "Õ"), ("OÏ", "Ọ"),
    ("OÂ", "Ô"), ("OÁ", "Ố"), ("OÀ", "Ồ"), ("OÅ", "Ổ"), ("OÃ", "Ỗ"), ("OÄ", "Ộ"),
    ("AÙ", "Á"), ("AØ", "À"), ("AÛ", "Ả"), ("AÕ", "Ã"), ("AÏ", "Ạ"),
    ("AÂ", "Â"), ("AÁ", "Ấ"), ("AÀ", "Ầ"), ("AÅ", "Ẩ"), ("AÃ", "Ẫ"), ("AÄ", "Ậ"),
    ("AÊ", "Ă"), ("AÉ", "Ắ"), ("AÈ", "Ằ"), ("AÚ", "Ẳ"), ("AÜ", "Ẵ"), ("AË", "Ặ"),
    ("EÙ", "É"), ("EØ", "È"), ("EÛ", "Ẻ"), ("EÕ", "Ẽ"), ("EÏ", "Ẹ"),
    ("EÂ", "Ê"), ("EÁ", "Ế"), ("EÀ", "Ề"), ("EÅ", "Ể"), ("EÃ", "Ẫ"), ("EÄ", "Ệ"),
    ("IÙ", "Í"), ("IØ", "Ì"), ("IÛ", "Ỉ"), ("IÕ", "Ĩ"), ("IÏ", "Ị"),
    ("ÖÙ", "Ứ"), ("ÖØ", "Ừ"), ("ÖÛ", "Ử"), ("ÖÕ", "Ữ"), ("ÖÏ", "Ự"), ("Ö", "Ư"),
    ("UÙ", "Ú"), ("UØ", "Ù"), ("UÛ", "Ủ"), ("UÕ", "Ũ"), ("UÏ", "Ụ"),
    ("YÙ", "Ý"), ("YØ", "Ỳ"), ("YÛ", "Ỷ"), ("YÕ", "Ỹ"), ("YÏ", "Ỵ"),
    ("ñ", "đ"), ("Ñ", "Đ"),
)

_VNI_KERNING_SPLIT_RE = re.compile(
    r"([a-zA-ZôöÔÖ])\s+([ùúûõïäëâêáàåãéèüÙÚÛÕÏÄËÂÊÁÀÅÃÉÈÜ])(?![a-zA-Z])"
)

_VNI_SIGNATURE_RE = re.compile(
    r"(?:aù|aø|aû|aõ|aï|aâ|aá|aà|aå|aã|aä|aê|aé|aè|aú|aü|aë|"
    r"eù|eø|eû|eõ|eï|eâ|eá|eà|eå|eã|eä|iù|iø|iû|iõ|iï|"
    r"où|oø|oû|oõ|oï|oâ|oå|oä|ôù|ôø|ôû|ôõ|ôï|"
    r"uù|uø|uû|uõ|uï|öù|öø|öû|öõ|öï|yù|yø|yû|yõ|yï|"
    r"Vôùi|vôùi|nghieäm|phöông|ñuùng|vaø|laø|coù|soá|caùc|ñöôïc|töï|haøm)",
    re.IGNORECASE,
)

# Precomposed Unicode Vietnamese codepoints outside 8-bit Latin-1 (U+0100..U+1EF9).
# Genuine VNI Windows text only uses 8-bit Windows-1252 characters; if a span in a non-VNI font
# already contains these Unicode Vietnamese codepoints, it is already Unicode and must not be VNI-decoded.
_UNICODE_VIET_RE = re.compile(
    r"[\u0102\u0103\u0110\u0111\u0128\u0129\u0168\u0169\u01A0\u01A1\u01AF\u01B0\u1EA0-\u1EF9]"
)

# TCVN3 / ABC 1-byte character table
_TCVN3_TABLE: dict[int, str] = {
    0xB8: "à", 0xB9: "ả", 0xBA: "ã", 0xBB: "á", 0xBC: "ạ",
    0xBD: "ă", 0xBE: "ằ", 0xC6: "ẳ", 0xC7: "ẵ", 0xC8: "ắ", 0xC9: "ặ",
    0xCA: "â", 0xCB: "ầ", 0xCC: "ẩ", 0xCE: "ẫ", 0xCF: "ấ", 0xD0: "ậ",
    0xD1: "è", 0xD2: "ẻ", 0xD3: "ẽ", 0xD4: "é", 0xD5: "ẹ",
    0xD6: "ê", 0xD7: "ề", 0xD8: "ể", 0xDC: "ễ", 0xDD: "ế", 0xDE: "ệ",
    0xDF: "ì", 0xE1: "ỉ", 0xE2: "ĩ", 0xE3: "í", 0xE4: "ị",
    0xE5: "ò", 0xE6: "ỏ", 0xE7: "õ", 0xE8: "ó", 0xE9: "ọ",
    0xEA: "ô", 0xEB: "ồ", 0xEC: "ổ", 0xED: "ỗ", 0xEE: "ố", 0xEF: "ộ",
    0xF1: "ơ", 0xF2: "ờ", 0xF3: "ở", 0xF4: "ỡ", 0xF5: "ớ", 0xF6: "ợ",
    0xF7: "ù", 0xF8: "ủ", 0xF9: "ũ", 0xFA: "ú", 0xFB: "ụ",
    0xFC: "ư", 0xFD: "ừ", 0xFE: "ử", 0xFF: "ữ", 0xA1: "ứ", 0xA2: "ự",
    0xA3: "ỳ", 0xA4: "ỷ", 0xA5: "ỹ", 0xA6: "ý", 0xA7: "ỵ",
    0xA9: "đ", 0xA8: "Đ",
}

# Known modern Unicode font indicators (where legacy decoding must NOT run by default)
_MODERN_UNICODE_FONTS = (
    "noto", "arial", "timesnewroman", "times new roman", "calibri", "segoe",
    "helvetica", "dejavu", "liberation", "cambria", "roboto", "inter",
)


def has_vni_encoding(text: str, font_name: str | None = None) -> bool:
    """Return True if text or font_name indicates VNI Windows encoding."""
    if not text:
        return False
    fn = (font_name or "").lower()
    if "vni" in fn:
        return True
    if _UNICODE_VIET_RE.search(text):
        return False
    return bool(_VNI_SIGNATURE_RE.search(text))


def decode_vni_to_unicode(text: str, font_name: str | None = None) -> str:
    """Decode VNI Windows composite pairs and kerning-split accents into canonical Unicode."""
    if not text:
        return text
    if not has_vni_encoding(text, font_name):
        return text
    res = _VNI_KERNING_SPLIT_RE.sub(r"\1\2", text)
    for legacy, standard in _VNI_REPLACEMENTS:
        if legacy in res:
            res = res.replace(legacy, standard)
    return res


class VietnameseLegacyNormalizer(BaseTextNormalizer):
    """Detects and decodes VNI Windows and TCVN3 legacy font encodings."""

    @property
    def name(self) -> str:
        return "vietnamese_legacy"

    def should_apply(
        self,
        text: str,
        font_name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        if not text:
            return False

        fn = (font_name or "").lower()

        # Explicit font markers
        if any(marker in fn for marker in ("vni", ".vn", "tcvn", "vntime", "vnarial", "vn-")):
            return True

        # If text already contains precomposed Unicode Vietnamese characters (U+0102..U+1EF9)
        # in a non-legacy font, it is already Unicode Vietnamese and must not be altered.
        if _UNICODE_VIET_RE.search(text):
            return False

        # If font is recognized as a modern Unicode font, only apply if unambiguous VNI patterns exist
        if any(mf in fn for mf in _MODERN_UNICODE_FONTS):
            return bool(_VNI_SIGNATURE_RE.search(text))

        # In absence of known font, check for signature VNI patterns
        return bool(
            _VNI_SIGNATURE_RE.search(text)
            or any(
                marker in text
                for marker in ("ñ", "Ñ", "Vôùi", "vôùi", "vo ânghieäm", "cô soá", "nghieäm", "ño ù")
            )
        )

    def normalize(
        self,
        text: str,
        font_name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> NormalizationResult:
        if not text:
            return NormalizationResult(text=text, applied=False)

        if not self.should_apply(text, font_name=font_name, metadata=metadata):
            return NormalizationResult(text=text, applied=False)

        fn = (font_name or "").lower()

        # Check TCVN3 encoding (typically indicated by .vn or tcvn fonts)
        if any(marker in fn for marker in (".vn", "tcvn", "vntime", "vnarial")):
            converted_chars: list[str] = []
            has_tcvn = False
            for ch in text:
                code = ord(ch)
                if code in _TCVN3_TABLE:
                    converted_chars.append(_TCVN3_TABLE[code])
                    has_tcvn = True
                else:
                    converted_chars.append(ch)
            if has_tcvn:
                return NormalizationResult(
                    text="".join(converted_chars),
                    applied=True,
                    encoding_detected="tcvn3",
                )

        # Check VNI Windows encoding
        result = _VNI_KERNING_SPLIT_RE.sub(r"\1\2", text)
        applied_vni = result != text
        for legacy, standard in _VNI_REPLACEMENTS:
            if legacy in result:
                result = result.replace(legacy, standard)
                applied_vni = True

        if applied_vni:
            return NormalizationResult(
                text=result,
                applied=True,
                encoding_detected="vni_windows",
            )

        # If should_apply was True but neither VNI nor TCVN3 matched,
        # fail-closed: preserve original text and issue warning
        return NormalizationResult(
            text=text,
            applied=False,
            warnings=["Potential legacy text detected but signature could not be verified; original text preserved."],
        )
