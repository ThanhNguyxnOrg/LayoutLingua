"""Early Contract Test Suite for LayoutLingua Slice 1.

Verifies:
1. Intermediate Representation (IR) validation and JSON round-trip serialization.
2. PyMuPDF parser across valid, text-less, empty, and corrupted PDFs.
3. Deterministic offline Mock Translation Provider preserving formula tokens (<bN></bN>).
4. JSON-RPC 2.0 NDJSON protocol compliance, method dispatch, error codes, and stdout isolation.
5. CLI parsing and mock translation execution.
"""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path

import pymupdf

from layoutlingua.cli import __version__, main as cli_main
from layoutlingua.core.ir import (
    CharInfo,
    DocumentIR,
    GlyphSpan,
    LayoutRegion,
    PageGeometry,
    PageIR,
    TextBlock,
)
from layoutlingua.core.parser import PDFParseError, parse_pdf
from layoutlingua.ipc import (
    INTERNAL_ERROR,
    INVALID_PARAMS,
    INVALID_REQUEST,
    METHOD_NOT_FOUND,
    PARSE_ERROR,
    JsonRpcServer,
)
from layoutlingua.translation.mock import MockTranslationProvider


class TestIRDataStructures(unittest.TestCase):
    """Test decoupled Intermediate Representation schemas, validation, and JSON conversion."""

    def test_geometry_validation(self) -> None:
        geom = PageGeometry(width=595.0, height=842.0, rotation=0)
        self.assertEqual(geom.width, 595.0)
        self.assertEqual(geom.unit, "pt")

        # Inverted / invalid dimensions
        with self.assertRaises(ValueError):
            PageGeometry(width=-10.0, height=100.0)

        # Invalid rotation angle
        with self.assertRaises(ValueError):
            PageGeometry(width=100.0, height=100.0, rotation=45)

    def test_bbox_validation(self) -> None:
        # Invalid coordinate order (x0 > x1)
        with self.assertRaises(ValueError):
            GlyphSpan(
                span_id="s1",
                text="hello",
                bbox=(100.0, 10.0, 50.0, 20.0),  # x0 > x1
                font_name="Helvetica",
                font_size=12.0,
                color="#000000",
            )

    def test_layout_region_extensibility(self) -> None:
        # Test that LayoutRegion supports alternative sources like doclayout_yolo with metadata
        region = LayoutRegion(
            region_id="r_yolo_1",
            bbox=(50.0, 100.0, 250.0, 400.0),
            category="formula",
            confidence=0.98,
            source="doclayout_yolo",
            metadata={"model_stride": 32, "raw_class_id": 4},
        )
        self.assertEqual(region.source, "doclayout_yolo")
        self.assertEqual(region.category, "formula")
        self.assertEqual(region.metadata["raw_class_id"], 4)

    def test_document_ir_json_round_trip(self) -> None:
        geom = PageGeometry(width=612.0, height=792.0, rotation=0)
        span = GlyphSpan(
            span_id="p1_s0",
            text="Universal Document Translation: Việt Nam & 世界",
            bbox=(72.0, 72.0, 300.0, 84.0),
            font_name="NotoSans",
            font_size=10.0,
            color="#1a2b3c",
            flags=2,  # bold
            origin=(72.0, 80.0),
            chars=[
                CharInfo(char="U", bbox=(72.0, 72.0, 78.0, 84.0), origin=(72.0, 80.0)),
            ],
            is_math_or_symbol=False,
        )
        block = TextBlock(block_id="p1_b0", bbox=(72.0, 72.0, 300.0, 84.0), spans=[span])
        region = LayoutRegion(
            region_id="p1_r0",
            bbox=(72.0, 72.0, 300.0, 84.0),
            category="title",
            confidence=0.99,
            source="pymupdf",
        )
        page = PageIR(page_number=1, geometry=geom, blocks=[block], regions=[region])
        doc = DocumentIR(
            doc_id="test_doc_001",
            filename="sample.pdf",
            page_count=1,
            pages=[page],
            metadata={"producer": "LayoutLingua Unit Test"},
        )

        # Serialize to JSON and parse back
        json_str = doc.to_json(indent=2)
        restored = DocumentIR.from_json(json_str)

        self.assertEqual(restored.doc_id, "test_doc_001")
        self.assertEqual(restored.page_count, 1)
        self.assertEqual(len(restored.pages), 1)
        self.assertEqual(restored.pages[0].blocks[0].spans[0].text, "Universal Document Translation: Việt Nam & 世界")
        self.assertEqual(restored.pages[0].blocks[0].spans[0].color, "#1a2b3c")
        self.assertEqual(restored.pages[0].regions[0].category, "title")


class TestPDFParser(unittest.TestCase):
    """Test PyMuPDF parser with synthesized PDF fixtures."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.dir_path = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _create_synthetic_pdf(self, path: Path) -> None:
        """Create a multi-page PDF with Unicode text, styling, and rotation."""
        doc = pymupdf.open()

        # Page 1: Standard upright text with formulas and accents
        page1 = doc.new_page(width=595, height=842)
        page1.insert_text(
            pymupdf.Point(50, 70),
            "LayoutLingua Core Engine: Arithmetic Progression & Formula x^2 + y^2 = z^2",
            fontsize=12,
            color=(0.1, 0.2, 0.8),  # Blue
        )
        page1.insert_text(
            pymupdf.Point(50, 110),
            "Accented Latin text: cafe, resume, uber, naive.",
            fontsize=10,
        )

        # Page 2: Rotated page (90 degrees)
        page2 = doc.new_page(width=842, height=595)
        page2.set_rotation(90)
        page2.insert_text(pymupdf.Point(100, 100), "Rotated Landscape Text", fontsize=14)

        doc.save(path)
        doc.close()

    def _create_textless_pdf(self, path: Path) -> None:
        """Create a PDF with zero text spans (empty / drawing only)."""
        doc = pymupdf.open()
        page = doc.new_page(width=400, height=400)
        # Draw a rectangle only
        page.draw_rect(pymupdf.Rect(50, 50, 200, 200), color=(1, 0, 0), fill=(0, 1, 0))
        doc.save(path)
        doc.close()

    def test_parse_valid_multipage_pdf(self) -> None:
        pdf_path = self.dir_path / "valid.pdf"
        self._create_synthetic_pdf(pdf_path)

        doc_ir = parse_pdf(pdf_path)
        self.assertEqual(doc_ir.page_count, 2)
        self.assertEqual(len(doc_ir.pages), 2)

        # Verify page 1
        p1 = doc_ir.pages[0]
        self.assertEqual(p1.page_number, 1)
        self.assertEqual(p1.geometry.width, 595.0)
        self.assertEqual(p1.geometry.height, 842.0)
        self.assertEqual(p1.geometry.rotation, 0)
        self.assertGreater(len(p1.blocks), 0)

        # Verify text extracted correctly
        combined_text = "".join(b.text for b in p1.blocks)
        self.assertIn("LayoutLingua Core Engine", combined_text)
        self.assertIn("Accented Latin text", combined_text)
        self.assertIn("x^2 + y^2 = z^2", combined_text)

        # Verify page 2 rotation
        p2 = doc_ir.pages[1]
        self.assertEqual(p2.page_number, 2)
        self.assertEqual(p2.geometry.rotation, 90)

    def test_parse_line_break_word_spacing(self) -> None:
        """Verify that multi-line paragraph text blocks preserve spaces across line breaks."""
        pdf_path = self.dir_path / "multiline_para.pdf"
        doc = pymupdf.open()
        page = doc.new_page(width=300, height=300)
        # Narrow textbox forces wrapping across multiple lines
        page.insert_textbox(
            pymupdf.Rect(50, 50, 200, 200),
            "Scientific literature is inherently multi-modal. Unlike continuous unstructured prose.",
            fontsize=12,
        )
        doc.save(pdf_path)
        doc.close()

        doc_ir = parse_pdf(pdf_path)
        self.assertEqual(len(doc_ir.pages), 1)
        full_text = " ".join(b.text for b in doc_ir.pages[0].blocks)
        # Ensure words across wrapped lines are separated by spaces, not mashed together
        self.assertIn("continuous unstructured", full_text)
        self.assertNotIn("continuousunstructured", full_text)

    def test_parse_textless_pdf(self) -> None:
        pdf_path = self.dir_path / "textless.pdf"
        self._create_textless_pdf(pdf_path)

        doc_ir = parse_pdf(pdf_path)
        self.assertEqual(doc_ir.page_count, 1)
        self.assertEqual(len(doc_ir.pages), 1)
        p = doc_ir.pages[0]
        self.assertEqual(len(p.blocks), 0)  # No text blocks
        self.assertEqual(p.geometry.width, 400.0)

    def test_parse_corrupt_pdf(self) -> None:
        corrupt_path = self.dir_path / "corrupt.pdf"
        corrupt_path.write_bytes(b"%PDF-1.4\nSome random garbage that is not a valid PDF content stream%%EOF")

        with self.assertRaises(PDFParseError):
            parse_pdf(corrupt_path)

    def test_parse_nonexistent_file(self) -> None:
        with self.assertRaises(PDFParseError):
            parse_pdf(self.dir_path / "does_not_exist.pdf")


class TestMockTranslationProvider(unittest.TestCase):
    """Test deterministic mock translation provider and formula tag preservation."""

    def setUp(self) -> None:
        self.provider = MockTranslationProvider()

    def test_determinism(self) -> None:
        text = "Deep learning and layout preservation in scientific documents."
        out1 = self.provider.translate_segment("s1", text, target_lang="vi")
        out2 = self.provider.translate_segment("s1", text, target_lang="vi")
        self.assertEqual(out1, out2)
        self.assertIn("[VI]", out1)

    def test_formula_token_preservation(self) -> None:
        text = "Let <b0></b0> be a vector and <b1></b1> be the scalar coefficient."
        result = self.provider.translate_segment("s_math", text, target_lang="vi")

        # Verify formula tokens are preserved verbatim
        self.assertIn("<b0></b0>", result)
        self.assertIn("<b1></b1>", result)
        # Verify text surrounding the tags is modified
        self.assertTrue(result.startswith("[VI] Let") or "[VI]" in result)

    def test_document_translation_audit(self) -> None:
        geom = PageGeometry(width=500.0, height=700.0)
        span = GlyphSpan(
            span_id="span_audit_1",
            text="Initial hypothesis <b0></b0> holds.",
            bbox=(50.0, 50.0, 200.0, 70.0),
            font_name="Times",
            font_size=12.0,
            color="#000000",
        )
        block = TextBlock(block_id="b1", bbox=(50.0, 50.0, 200.0, 70.0), spans=[span])
        page = PageIR(page_number=1, geometry=geom, blocks=[block])
        doc = DocumentIR(doc_id="doc_audit", filename="test.pdf", page_count=1, pages=[page])

        translated_doc = self.provider.translate_document(doc, target_lang="vi")

        # Ensure original doc was not mutated
        self.assertEqual(doc.pages[0].blocks[0].spans[0].text, "Initial hypothesis <b0></b0> holds.")
        # Ensure translated doc has updated text with intact geometry
        translated_text = translated_doc.pages[0].blocks[0].spans[0].text
        self.assertIn("<b0></b0>", translated_text)
        self.assertIn("[VI]", translated_text)
        self.assertEqual(translated_doc.pages[0].blocks[0].spans[0].bbox, (50.0, 50.0, 200.0, 70.0))

        # Check records log for ID mapping
        self.assertGreater(len(self.provider.records), 0)
        last_rec = self.provider.records[-1]
        self.assertEqual(last_rec.segment_id, "span_audit_1")
        self.assertEqual(last_rec.target_lang, "vi")


class TestJsonRpcServer(unittest.TestCase):
    """Test JSON-RPC 2.0 NDJSON protocol, error codes, and stdout isolation."""

    def setUp(self) -> None:
        self.server = JsonRpcServer()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.dir_path = Path(self.temp_dir.name)

        # Create a small sample PDF
        self.sample_pdf = self.dir_path / "sample.pdf"
        doc = pymupdf.open()
        page = doc.new_page(width=500, height=500)
        page.insert_text(pymupdf.Point(50, 50), "JSON-RPC IPC Test String", fontsize=11)
        doc.save(self.sample_pdf)
        doc.close()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_rpc_ping(self) -> None:
        request = json.dumps({"jsonrpc": "2.0", "id": 42, "method": "ping", "params": {}})
        err_stream = io.StringIO()
        response_line = self.server.process_message(request, err_stream=err_stream)

        self.assertIsNotNone(response_line)
        res = json.loads(response_line)
        self.assertEqual(res["jsonrpc"], "2.0")
        self.assertEqual(res["id"], 42)
        self.assertTrue(res["result"]["pong"])
        self.assertEqual(res["result"]["version"], "1.0.0")

    def test_rpc_get_schema_version(self) -> None:
        request = json.dumps({"jsonrpc": "2.0", "id": "req-1", "method": "get_schema_version"})
        response_line = self.server.process_message(request)
        self.assertIsNotNone(response_line)
        res = json.loads(response_line)
        self.assertEqual(res["id"], "req-1")
        self.assertEqual(res["result"]["ir_version"], "1.0")

    def test_rpc_parse_document(self) -> None:
        request = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 100,
                "method": "parse_document",
                "params": {"file_path": str(self.sample_pdf)},
            }
        )
        response_line = self.server.process_message(request)
        self.assertIsNotNone(response_line)
        res = json.loads(response_line)
        self.assertEqual(res["id"], 100)
        doc_data = res["result"]
        self.assertEqual(doc_data["page_count"], 1)
        self.assertIn("JSON-RPC IPC Test String", doc_data["pages"][0]["blocks"][0]["spans"][0]["text"])

    def test_rpc_translate_document_mock(self) -> None:
        request = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 101,
                "method": "translate_document_mock",
                "params": {"file_path": str(self.sample_pdf), "target_lang": "vi"},
            }
        )
        response_line = self.server.process_message(request)
        self.assertIsNotNone(response_line)
        res = json.loads(response_line)
        self.assertEqual(res["id"], 101)
        doc_data = res["result"]
        translated_span = doc_data["pages"][0]["blocks"][0]["spans"][0]["text"]
        self.assertIn("[VI]", translated_span)

    def test_rpc_invalid_json(self) -> None:
        err_stream = io.StringIO()
        response_line = self.server.process_message("{invalid_json_line", err_stream=err_stream)
        self.assertIsNotNone(response_line)
        res = json.loads(response_line)
        self.assertIsNone(res["id"])
        self.assertEqual(res["error"]["code"], PARSE_ERROR)
        self.assertIn("Parse error", res["error"]["message"])

    def test_rpc_invalid_request(self) -> None:
        # Missing jsonrpc: "2.0"
        response_line = self.server.process_message(json.dumps({"id": 1, "method": "ping"}))
        self.assertIsNotNone(response_line)
        res = json.loads(response_line)
        self.assertEqual(res["error"]["code"], INVALID_REQUEST)

    def test_rpc_method_not_found(self) -> None:
        request = json.dumps({"jsonrpc": "2.0", "id": 999, "method": "non_existent_method"})
        response_line = self.server.process_message(request)
        self.assertIsNotNone(response_line)
        res = json.loads(response_line)
        self.assertEqual(res["id"], 999)
        self.assertEqual(res["error"]["code"], METHOD_NOT_FOUND)

    def test_rpc_invalid_params(self) -> None:
        request = json.dumps({"jsonrpc": "2.0", "id": 55, "method": "parse_document", "params": {}})
        response_line = self.server.process_message(request)
        self.assertIsNotNone(response_line)
        res = json.loads(response_line)
        self.assertEqual(res["id"], 55)
        self.assertEqual(res["error"]["code"], INVALID_PARAMS)

    def test_stdout_isolation_and_log_containment(self) -> None:
        # Run stdio server simulation with separate StringIO streams
        in_stream = io.StringIO(
            json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping"}) + "\n"
            + json.dumps({"jsonrpc": "2.0", "id": 2, "method": "invalid_func"}) + "\n"
        )
        out_stream = io.StringIO()
        err_stream = io.StringIO()

        self.server.serve_stdio(in_stream=in_stream, out_stream=out_stream, err_stream=err_stream)

        # stdout MUST be valid NDJSON lines only
        out_content = out_stream.getvalue().strip()
        lines = out_content.splitlines()
        self.assertEqual(len(lines), 2)
        for line in lines:
            parsed = json.loads(line)  # Must be strictly parseable JSON
            self.assertIn("jsonrpc", parsed)

        # stderr receives diagnostic logs
        err_content = err_stream.getvalue()
        self.assertIn("[LayoutLingua IPC]", err_content)

    def test_rpc_persistent_multi_request_session(self) -> None:
        """Verify that multiple consecutive JSON-RPC requests on the same stream maintain process state."""
        requests = [
            {"jsonrpc": "2.0", "id": i, "method": "ping"} if i % 2 == 0
            else {"jsonrpc": "2.0", "id": i, "method": "get_schema_version"}
            for i in range(1, 11)
        ]
        in_stream = io.StringIO("\n".join(json.dumps(r) for r in requests) + "\n")
        out_stream = io.StringIO()
        err_stream = io.StringIO()

        self.server.serve_stdio(in_stream=in_stream, out_stream=out_stream, err_stream=err_stream)

        responses = [json.loads(line) for line in out_stream.getvalue().strip().splitlines()]
        self.assertEqual(len(responses), 10)
        for i, res in enumerate(responses, start=1):
            self.assertEqual(res["id"], i)
            if i % 2 == 0:
                self.assertTrue(res["result"]["pong"])
            else:
                self.assertEqual(res["result"]["ir_version"], "1.0")


class TestCLI(unittest.TestCase):
    """Test CLI execution, arguments, and exit codes."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.dir_path = Path(self.temp_dir.name)
        self.sample_pdf = self.dir_path / "cli_sample.pdf"

        doc = pymupdf.open()
        page = doc.new_page(width=400, height=400)
        page.insert_text(pymupdf.Point(50, 50), "CLI Test Header", fontsize=12)
        doc.save(self.sample_pdf)
        doc.close()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_cli_parse(self) -> None:
        out_json = self.dir_path / "parsed.json"
        exit_code = cli_main(["--parse", str(self.sample_pdf), "--output", str(out_json)])
        self.assertEqual(exit_code, 0)
        self.assertTrue(out_json.exists())

        data = json.loads(out_json.read_text(encoding="utf-8"))
        self.assertEqual(data["page_count"], 1)

    def test_cli_translate_mock(self) -> None:
        out_json = self.dir_path / "translated.json"
        exit_code = cli_main(["--translate-mock", str(self.sample_pdf), "--target-lang", "vi", "--output", str(out_json)])
        self.assertEqual(exit_code, 0)
        self.assertTrue(out_json.exists())

        data = json.loads(out_json.read_text(encoding="utf-8"))
        self.assertIn("[VI]", data["pages"][0]["blocks"][0]["spans"][0]["text"])

    def test_cli_parse_nonexistent_file(self) -> None:
        exit_code = cli_main(["--parse", str(self.dir_path / "none.pdf")])
        self.assertEqual(exit_code, 2)


if __name__ == "__main__":
    unittest.main()
