"""Unit tests for the Semantic Document IR module."""

import unittest
from pdf2zh.ir import (
    CellIR,
    DocumentIR,
    FormulaIR,
    PageIR,
    ParagraphIR,
    RunIR,
    SemanticRole,
    TableIR,
)


class TestDocumentIR(unittest.TestCase):
    def test_ir_roundtrip_serialization(self):
        doc = DocumentIR(
            global_glossary={"attention mechanism": "cơ chế chú ý"},
            metadata={"title": "Test Scientific Document"},
        )
        page = PageIR(page_number=1, width=595.0, height=842.0)
        para = ParagraphIR(
            id="p_1_0",
            bbox=(50.0, 700.0, 300.0, 750.0),
            semantic_role=SemanticRole.HEADING,
            source_text="Introduction to LayoutLingua",
            font_name="Helvetica-Bold",
            font_size=14.0,
        )
        run = RunIR(
            text="Introduction to LayoutLingua",
            font_name="Helvetica-Bold",
            font_size=14.0,
            style=1,
            bbox=(50.0, 700.0, 300.0, 750.0),
        )
        para.runs.append(run)
        page.paragraphs.append(para)
        doc.pages.append(page)

        # Serialize to JSON
        json_str = doc.to_json()
        self.assertIn("Introduction to LayoutLingua", json_str)
        self.assertIn("cơ chế chú ý", json_str)
        self.assertIn('"semantic_role": "heading"', json_str)

        # Deserialize from dict
        reconstructed = DocumentIR.from_dict(doc.to_dict())
        self.assertEqual(len(reconstructed.pages), 1)
        self.assertEqual(reconstructed.pages[0].page_number, 1)
        self.assertEqual(reconstructed.pages[0].paragraphs[0].id, "p_1_0")
        self.assertEqual(
            reconstructed.pages[0].paragraphs[0].semantic_role,
            SemanticRole.HEADING,
        )
        self.assertEqual(
            reconstructed.global_glossary["attention mechanism"],
            "cơ chế chú ý",
        )

    def test_semantic_roles(self):
        roles = [
            SemanticRole.TITLE,
            SemanticRole.PROSE,
            SemanticRole.TABLE,
            SemanticRole.CELL,
            SemanticRole.FORMULA,
            SemanticRole.CAPTION,
            SemanticRole.FOOTNOTE,
            SemanticRole.HEADER,
            SemanticRole.FOOTER,
        ]
        for role in roles:
            self.assertIsInstance(role.value, str)


if __name__ == "__main__":
    unittest.main()
