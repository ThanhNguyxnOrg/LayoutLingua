"""Multi-page document accumulator with atomic commit gates and document-level preservation."""

from __future__ import annotations

import pymupdf

from layoutlingua.typesetting.models import FittingReport, PageTransactionResult

PREDEFINED_NAMED_ACTIONS: frozenset[str] = frozenset({"NextPage", "PrevPage", "FirstPage", "LastPage"})


class DocumentAccumulator:
    """Accumulates staged pages into a coherent multi-page PDF document.

    Guarantees:
    - Strictly preserves page order 0..N-1 with zero duplicated or omitted pages.
    - Atomic commit gate: if output_doc.insert_pdf fails, rolls back trailing page
      and commits the pristine source page.
    - Preserves document-level properties: metadata, TOC, page labels, embedded files,
      and XML metadata.
    - Post-assembly link restoration: re-inserts LINK_GOTO, LINK_URI, and dual
      LINK_NAMED (predefined actions + named destination resolution) after all pages
      are committed with links=False.
    """

    def __init__(self, source_doc: pymupdf.Document) -> None:
        self.source_doc = source_doc
        self.output_doc = pymupdf.open()

    def commit_page(self, tx_result: PageTransactionResult) -> bool:
        """Atomically commit a staged page transaction result into output_doc.

        Returns:
            True if tx_result.staging_doc was committed cleanly;
            False if commit failed, triggering an emergency rollback and pristine source fallback.
        """
        source_page_index = tx_result.source_page_index
        pre_commit_count = len(self.output_doc)
        committed_cleanly = False

        try:
            self.output_doc.insert_pdf(
                tx_result.staging_doc,
                from_page=0,
                to_page=0,
                links=False,
                annots=True,
                widgets=True,
                join_duplicates=True,
            )
            committed_cleanly = True
        except Exception:
            # Atomic rollback of any partial/corrupted page added
            if len(self.output_doc) > pre_commit_count:
                try:
                    self.output_doc.delete_page(-1)
                except Exception:
                    pass

            # Emergency fallback: commit pristine source page
            try:
                self.output_doc.insert_pdf(
                    self.source_doc,
                    from_page=source_page_index,
                    to_page=source_page_index,
                    links=False,
                    annots=True,
                    widgets=True,
                    join_duplicates=True,
                )
            except Exception:
                pass
            committed_cleanly = False
        finally:
            try:
                if not tx_result.staging_doc.is_closed:
                    tx_result.staging_doc.close()
            except Exception:
                pass

        return committed_cleanly

    def commit_pristine_source_page(self, source_page_index: int) -> None:
        """Commit an untouched pristine source page directly into output_doc."""
        self.output_doc.insert_pdf(
            self.source_doc,
            from_page=source_page_index,
            to_page=source_page_index,
            links=False,
            annots=True,
            widgets=True,
            join_duplicates=True,
        )

    def restore_links(self, report: FittingReport) -> None:
        """Post-assembly link restoration from source_doc into output_doc.

        Handles three link categories:
        1. LINK_GOTO / LINK_URI: re-inserted verbatim into corresponding output page.
        2. LINK_NAMED predefined actions (NextPage, PrevPage, FirstPage, LastPage):
           re-inserted verbatim as LINK_NAMED.
        3. LINK_NAMED with nameddest=<name>: resolved via source_doc name table,
           converted to LINK_GOTO with coordinate transformation via destination
           page's transformation_matrix. Unresolvable names emit a warning.
        """
        # Build resolved name table from source document
        resolved_names: dict[str, dict] = {}
        try:
            resolved_names = self.source_doc.resolve_names() or {}
        except Exception:
            pass

        # Track which named destinations from the catalog are referenced by links
        referenced_dest_names: set[str] = set()

        num_pages = min(len(self.source_doc), len(self.output_doc))
        for page_idx in range(num_pages):
            source_page = self.source_doc[page_idx]
            output_page = self.output_doc[page_idx]

            try:
                source_links = source_page.get_links()
            except Exception:
                continue

            for link in source_links:
                kind = link.get("kind")

                if kind == pymupdf.LINK_GOTO:
                    # Internal cross-page link: re-insert verbatim
                    try:
                        output_page.insert_link(link)
                    except Exception:
                        pass

                elif kind == pymupdf.LINK_URI:
                    # External URI link: re-insert verbatim
                    try:
                        output_page.insert_link(link)
                    except Exception:
                        pass

                elif kind == pymupdf.LINK_NAMED:
                    name = link.get("name") or link.get("nameddest") or ""

                    # Check predefined viewer actions first
                    if name in PREDEFINED_NAMED_ACTIONS:
                        try:
                            action_link = {
                                "kind": pymupdf.LINK_NAMED,
                                "from": link.get("from", pymupdf.Rect(0, 0, 0, 0)),
                                "name": name,
                            }
                            output_page.insert_link(action_link)
                        except Exception:
                            pass
                        continue

                    # Extract destination name from "nameddest=<name>" format
                    dest_name = ""
                    if name.startswith("nameddest="):
                        dest_name = name[len("nameddest="):]
                    else:
                        dest_name = name

                    if not dest_name:
                        continue

                    referenced_dest_names.add(dest_name)

                    # Resolve named destination from source document name table
                    dest_info = resolved_names.get(dest_name)
                    if dest_info is None:
                        # Unresolvable: skip link insertion, emit warning
                        report.warnings.append(
                            f"Unresolvable named destination '{dest_name}' on page {page_idx + 1}; "
                            f"link skipped to prevent dead link."
                        )
                        continue

                    # Convert resolved destination to LINK_GOTO
                    dest_page = dest_info.get("page", -1)
                    dest_to = dest_info.get("to")

                    if dest_page < 0 or dest_page >= len(self.output_doc):
                        report.warnings.append(
                            f"Named destination '{dest_name}' resolves to invalid page {dest_page}; "
                            f"link skipped."
                        )
                        continue

                    # Apply coordinate transformation via destination page's transformation_matrix
                    goto_point = pymupdf.Point(0, 0)
                    if dest_to is not None:
                        try:
                            dest_output_page = self.output_doc[dest_page]
                            raw_point = pymupdf.Point(dest_to)
                            goto_point = raw_point * dest_output_page.transformation_matrix
                        except Exception:
                            goto_point = pymupdf.Point(dest_to) if dest_to else pymupdf.Point(0, 0)

                    goto_link = {
                        "kind": pymupdf.LINK_GOTO,
                        "from": link.get("from", pymupdf.Rect(0, 0, 0, 0)),
                        "page": dest_page,
                        "to": goto_point,
                    }
                    try:
                        output_page.insert_link(goto_link)
                    except Exception:
                        report.warnings.append(
                            f"Failed to insert resolved LINK_GOTO for destination '{dest_name}' "
                            f"on page {page_idx + 1}."
                        )

                else:
                    # Unknown link kind: attempt verbatim restoration
                    try:
                        output_page.insert_link(link)
                    except Exception:
                        pass

        # Emit diagnostic warnings for standalone catalog named destinations
        # that exist in the name table but were not referenced by any link
        if resolved_names:
            standalone_dests = set(resolved_names.keys()) - referenced_dest_names
            for dest_name in sorted(standalone_dests):
                report.warnings.append(
                    f"Standalone catalog named destination '{dest_name}' preserved in document "
                    f"structure but not referenced by any link."
                )

    def preserve_document_properties(self, translated_toc: list[list] | None = None) -> None:
        """Transfer document-level attributes verbatim from source_doc to output_doc."""
        # 1. Document metadata (title, author, subject, keywords, creator, producer, dates)
        try:
            if self.source_doc.metadata:
                self.output_doc.set_metadata(self.source_doc.metadata)
        except Exception:
            pass

        # 2. Table of Contents (bookmarks / outlines)
        try:
            if translated_toc:
                self.output_doc.set_toc(translated_toc)
            else:
                toc = self.source_doc.get_toc()
                if toc:
                    self.output_doc.set_toc(toc)
        except Exception:
            pass

        # 3. Page labels
        try:
            page_labels = self.source_doc.get_page_labels()
            if page_labels:
                self.output_doc.set_page_labels(page_labels)
        except Exception:
            pass

        # 4. Embedded files
        try:
            if hasattr(self.source_doc, "embfile_names"):
                for name in self.source_doc.embfile_names():
                    try:
                        info = self.source_doc.embfile_info(name)
                        content = self.source_doc.embfile_get(name)
                        self.output_doc.embfile_add(
                            name,
                            content,
                            filename=info.get("filename") if isinstance(info, dict) else name,
                            desc=info.get("desc") if isinstance(info, dict) else "",
                        )
                    except Exception:
                        pass
        except Exception:
            pass

        # 5. XML metadata
        try:
            xml_meta = self.source_doc.get_xml_metadata()
            if xml_meta:
                self.output_doc.set_xml_metadata(xml_meta)
        except Exception:
            pass

    def finish(
        self,
        report: FittingReport | None = None,
        layout_mode: str = "mono",
        translated_toc: list[list] | None = None,
    ) -> bytes:
        """Finalize and return the accumulated PDF bytes, closing the output document.

        Args:
            report: If provided, post-assembly link restoration is performed and
                    warnings are appended to report.warnings.
            layout_mode: "mono" for translated pages only; "bilingual" for alternating
                         source and translated pages (pdf2zh dual layout pattern).
            translated_toc: Optional translated Table of Contents (bookmarks) outline.
        """
        if (layout_mode or "").lower() == "bilingual":
            return self.build_bilingual_document(report=report, translated_toc=translated_toc)

        self.preserve_document_properties(translated_toc=translated_toc)
        if report is not None:
            self.restore_links(report)
        pdf_bytes = self.output_doc.tobytes(deflate=True, garbage=3)
        self.output_doc.close()
        return pdf_bytes

    def build_bilingual_document(
        self,
        report: FittingReport | None = None,
        translated_toc: list[list] | None = None,
    ) -> bytes:
        """Create and return a bilingual alternating PDF document.

        Interleaves source and translated pages:
        [Source 0, Translated 0, Source 1, Translated 1, ...]
        """
        self.preserve_document_properties(translated_toc=translated_toc)
        if report is not None:
            self.restore_links(report)

        bilingual_doc = pymupdf.open()
        num_pages = max(len(self.source_doc), len(self.output_doc))

        for idx in range(num_pages):
            if idx < len(self.source_doc):
                bilingual_doc.insert_pdf(
                    self.source_doc,
                    from_page=idx,
                    to_page=idx,
                    links=False,
                    annots=True,
                    widgets=True,
                    join_duplicates=True,
                )
            if idx < len(self.output_doc):
                bilingual_doc.insert_pdf(
                    self.output_doc,
                    from_page=idx,
                    to_page=idx,
                    links=False,
                    annots=True,
                    widgets=True,
                    join_duplicates=True,
                )

        try:
            if self.source_doc.metadata:
                bilingual_doc.set_metadata(self.source_doc.metadata)
        except Exception:
            pass

        try:
            if translated_toc:
                bilingual_doc.set_toc(translated_toc)
            elif self.source_doc.get_toc():
                bilingual_doc.set_toc(self.source_doc.get_toc())
        except Exception:
            pass

        pdf_bytes = bilingual_doc.tobytes(deflate=True, garbage=3)
        bilingual_doc.close()
        self.output_doc.close()
        return pdf_bytes

    def close(self) -> None:
        """Close output document if not already closed."""
        try:
            if not self.output_doc.is_closed:
                self.output_doc.close()
        except Exception:
            pass
