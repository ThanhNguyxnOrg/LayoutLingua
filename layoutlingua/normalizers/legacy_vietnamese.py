"""Legacy Vietnamese font encoding normalizer (VNI Windows & TCVN3).

Word 2003 / MathType math textbooks frequently store Vietnamese prose in
VNI-Times font without Unicode CMaps, emitting characters like 'Vôùi',
'nghieäm ñuùng', 'trong ñoù', and 'vo ânghieäm'. MT engines cannot recognize
these pseudo-words and leave them untranslated, while Unicode fonts render
the raw diacritics as broken characters.
"""

from __future__ import annotations

from layoutlingua.normalizers.base import BaseTextNormalizer

_VNI_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    # Words with VNI prefix stems (must run before character replacements)
    ("vo ânghieäm", "vô nghiệm"), ("vo â nghieäm", "vô nghiệm"),
    ("voâ nghieäm", "vô nghiệm"), ("voânghieäm", "vô nghiệm"),
    ("vo ânghiệm", "vô nghiệm"), ("voâ nghiệm", "vô nghiệm"),
    ("vo â", "vô "), ("voâ", "vô"),
    ("Vo â", "Vô "), ("Voâ", "Vô"),
    ("VO Â", "VÔ "), ("VOÂ", "VÔ"),
    ("Vôùi", "Với"), ("vôùi", "với"), ("VÔÙI", "VỚI"),
    ("cô soá", "cơ số"), ("cô", "cơ"), ("CÔ", "CƠ"),
    # Spaced VNI composite pairs
    ("o ù", "ó"), ("o ø", "ò"), ("o û", "ỏ"), ("o õ", "õ"), ("o ï", "ọ"),
    ("o â", "ô"), ("o á", "ố"), ("o à", "ồ"), ("o å", "ổ"), ("o ã", "ỗ"), ("o ä", "ộ"),
    ("ô ù", "ớ"), ("ô ø", "ờ"), ("ô û", "ở"), ("ô õ", "ỡ"), ("ô ï", "ợ"),
    ("a ù", "á"), ("a ø", "à"), ("a û", "ả"), ("a õ", "ã"), ("a ï", "ạ"),
    ("a â", "â"), ("a á", "ấ"), ("a à", "ầ"), ("a å", "ẩ"), ("a ã", "ẫ"), ("a ä", "ậ"),
    ("a ê", "ă"), ("a é", "ắ"), ("a è", "ằ"), ("a ú", "ẳ"), ("a ü", "ẵ"), ("a ë", "ặ"),
    ("e ù", "é"), ("e ø", "è"), ("e û", "ẻ"), ("e õ", "ẽ"), ("e ï", "ẹ"),
    ("e â", "ê"), ("e á", "ế"), ("e à", "ề"), ("e å", "ể"), ("e ã", "ễ"), ("e ä", "ệ"),
    ("u ù", "ú"), ("u ø", "ù"), ("u û", "ủ"), ("u õ", "ũ"), ("u ï", "ụ"),
    ("ö ù", "ứ"), ("ö ø", "ừ"), ("ö û", "ử"), ("ö õ", "ữ"), ("ö ï", "ự"),
    ("y ù", "ý"), ("y ø", "ỳ"), ("y û", "ỷ"), ("y õ", "ỹ"),
    # Standard VNI composite pairs
    ("ôù", "ớ"), ("ôø", "ờ"), ("ôû", "ở"), ("ôõ", "ỡ"), ("ôï", "ợ"),
    ("oá", "ố"), ("oà", "ồ"), ("oå", "ổ"), ("oã", "ỗ"), ("oä", "ộ"), ("oâ", "ô"),
    ("où", "ó"), ("oø", "ò"), ("oû", "ỏ"), ("oõ", "õ"), ("oï", "ọ"),
    ("aá", "ấ"), ("aà", "ầ"), ("aå", "ẩ"), ("aã", "ẫ"), ("aä", "ậ"), ("aâ", "â"),
    ("aé", "ắ"), ("aè", "ằ"), ("aú", "ẳ"), ("aü", "ẵ"), ("aë", "ặ"), ("aê", "ă"),
    ("aù", "á"), ("aø", "à"), ("aû", "ả"), ("aõ", "ã"), ("aï", "ạ"),
    ("eá", "ế"), ("eà", "ề"), ("eå", "ể"), ("eã", "ễ"), ("eä", "ệ"), ("eâ", "ê"),
    ("eù", "é"), ("eø", "è"), ("eû", "ẻ"), ("eõ", "ẽ"), ("eï", "ẹ"),
    ("öù", "ứ"), ("öø", "ừ"), ("öû", "ử"), ("öõ", "ữ"), ("öï", "ự"), ("ö", "ư"),
    ("uù", "ú"), ("uø", "ù"), ("uû", "ủ"), ("uõ", "ũ"), ("uï", "ụ"),
    ("yù", "ý"), ("yø", "ỳ"), ("yû", "ỷ"), ("yõ", "ỹ"),
    # Uppercase VNI composite pairs
    ("OÙ", "Ó"), ("OØ", "Ò"), ("OÛ", "Ỏ"), ("OÕ", "Õ"), ("OÏ", "Ọ"),
    ("OÂ", "Ô"), ("OÁ", "Ố"), ("OÀ", "Ồ"), ("OÅ", "Ổ"), ("OÃ", "Ỗ"), ("OÄ", "Ộ"),
    ("ÔÙ", "Ớ"), ("ÔØ", "Ờ"), ("ÔÛ", "Ở"), ("ÔÕ", "Ỡ"), ("ÔÏ", "Ợ"),
    ("AÙ", "Á"), ("AØ", "À"), ("AÛ", "Ả"), ("AÕ", "Ã"), ("AÏ", "Ạ"),
    ("AÂ", "Â"), ("AÁ", "Ấ"), ("AÀ", "Ầ"), ("AÅ", "Ẩ"), ("AÃ", "Ẫ"), ("AÄ", "Ậ"),
    ("AÊ", "Ă"), ("AÉ", "Ắ"), ("AÈ", "Ằ"), ("AÚ", "Ẳ"), ("AÜ", "Ẵ"), ("AË", "Ặ"),
    ("EÙ", "É"), ("EØ", "È"), ("EÛ", "Ẻ"), ("EÕ", "Ẽ"), ("EÏ", "Ẹ"),
    ("EÂ", "Ê"), ("EÁ", "Ế"), ("EÀ", "Ề"), ("EÅ", "Ể"), ("EÃ", "Ễ"), ("EÄ", "Ệ"),
    ("ÖÙ", "Ứ"), ("ÖØ", "Ừ"), ("ÖÛ", "Ử"), ("ÖÕ", "Ữ"), ("ÖÏ", "Ự"), ("Ö", "Ư"),
    ("UÙ", "Ú"), ("UØ", "Ù"), ("UÛ", "Ủ"), ("UÕ", "Ũ"), ("UÏ", "Ụ"),
    ("YÙ", "Ý"), ("YØ", "Ỳ"), ("YÛ", "Ỷ"), ("YÕ", "Ỹ"),
    # Single VNI characters
    ("ñ", "đ"), ("Ñ", "Đ"),
)


class VietnameseLegacyNormalizer(BaseTextNormalizer):
    """Detects and decodes VNI Windows and TCVN3 legacy font encodings."""

    def should_apply(self, text: str, font_name: str | None = None) -> bool:
        if font_name and ("vni" in font_name.lower() or ".vn" in font_name.lower()):
            return True
        if not text:
            return False
        return any(
            marker in text
            for marker in ("ñ", "Ñ", "ä", "ö", "ë", "ï", "ø", "ù", "Vôùi", "vôùi", "ño")
        )

    def normalize(self, text: str) -> str:
        if not text:
            return text
        result = text
        for legacy, standard in _VNI_REPLACEMENTS:
            if legacy in result:
                result = result.replace(legacy, standard)
        return result
