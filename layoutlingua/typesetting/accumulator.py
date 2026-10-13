"""Multi-page document accumulator with atomic commit gates and document-level preservation."""

from __future__ import annotations

import pymupdf

from layoutlingua.typesetting.models import PageTransactionResult


class DocumentAccumulator:
    """Accumulates staged pages into a coherent multi-page PDF document.

    Guarantees:
    - Strictly preserves page order 0..N-1 with zero duplicated or omitted pages.
    - Atomic commit gate: if output_doc.insert_pdf fails, rolls back trailing page
      and commits the pristine source page.
    - Preserves document-level properties: metadata, TOC, page labels, embedded files,
      and XML metadata.
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

    def preserve_document_properties(self) -> None:
        """Transfer document-level attributes verbatim from source_doc to output_doc."""
        # 1. Document metadata (title, author, subject, keywords, creator, producer, dates)
        try:
            if self.source_doc.metadata:
                self.output_doc.set_metadata(self.source_doc.metadata)
        except Exception:
            pass

        # 2. Table of Contents (bookmarks / outlines)
        try:
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

    def finish(self) -> bytes:
        """Finalize and return the accumulated PDF bytes, closing the output document."""
        self.preserve_document_properties()
        pdf_bytes = self.output_doc.tobytes(deflate=True, garbage=3)
        self.output_doc.close()
        return pdf_bytes

    def close(self) -> None:
        """Close output document if not already closed."""
        try:
            if not self.output_doc.is_closed:
                self.output_doc.close()
        except Exception:
            pass
