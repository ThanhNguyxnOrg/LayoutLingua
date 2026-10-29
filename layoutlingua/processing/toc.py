"""PDF Table of Contents (outlines/bookmarks) translation and bilingual page adjustment."""

from __future__ import annotations

import pymupdf
from layoutlingua.translation.glossary import GlossaryManager


def translate_toc(
    source_doc: pymupdf.Document,
    target_lang: str = "vi",
    source_lang: str = "en",
    custom_glossary: str | dict | None = None,
    bilingual_mode: bool = False,
) -> list[list]:
    """Translate PDF Table of Contents titles and adjust destination pages for bilingual mode.

    PyMuPDF TOC item structure: [lvl (int), title (str), page (int, 1-indexed), ...]
    """
    try:
        toc = source_doc.get_toc(simple=True)
    except Exception:
        return []

    if not toc:
        return []

    translated_toc: list[list] = []

    for item in toc:
        if not item or len(item) < 3:
            continue

        lvl, title, page = item[0], item[1], item[2]

        # Translate outline title through GlossaryManager
        trans_title = GlossaryManager.apply_glossary(
            text=title,
            source_lang=source_lang,
            target_lang=target_lang,
            custom_glossary=custom_glossary,
        )

        # In bilingual alternating mode (P1_src, P1_tgt, P2_src, P2_tgt),
        # translated page target is at 2 * page
        target_page = (page * 2) if bilingual_mode else page

        new_item = list(item)
        new_item[1] = trans_title
        new_item[2] = target_page
        translated_toc.append(new_item)

    return translated_toc