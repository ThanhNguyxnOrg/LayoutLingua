"""Unit tests for the Checkpoint and Defect Manifest Manager."""

import tempfile
import unittest
from pathlib import Path
from pdf2zh.checkpoint import (
    CheckpointManager,
    DefectRecord,
    is_reference_section_heading,
)


class TestCheckpointManager(unittest.TestCase):
    def test_checkpoint_lifecycle(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / "source.pdf"
            dst = Path(tmpdir) / "out.pdf"
            src.touch()
            dst.touch()

            # Session 1: Process pages 1 and 2
            mgr1 = CheckpointManager(source_path=src, output_path=dst, total_pages=10)
            self.assertFalse(mgr1.is_page_completed(1))

            mgr1.mark_page_completed(1)
            mgr1.record_defect(page_num=2, segment="f(x) = y", reason="FormulaPlaceholderDamaged")
            mgr1.mark_page_completed(2)

            self.assertTrue(mgr1.is_page_completed(1))
            self.assertTrue(mgr1.is_page_completed(2))
            self.assertFalse(mgr1.is_page_completed(3))

            # Session 2: Reload from disk
            mgr2 = CheckpointManager(source_path=src, output_path=dst, total_pages=10)
            self.assertTrue(mgr2.is_page_completed(1))
            self.assertTrue(mgr2.is_page_completed(2))
            self.assertFalse(mgr2.is_page_completed(3))

            manifest = mgr2.generate_manifest_report()
            self.assertEqual(manifest["total_fallback_segments"], 1)
            self.assertEqual(manifest["reasons_breakdown"].get("FormulaPlaceholderDamaged"), 1)

            # Cleanup
            mgr2.cleanup()
            self.assertFalse(mgr2.checkpoint_file.exists())

    def test_reference_heading_detection(self):
        self.assertTrue(is_reference_section_heading("References"))
        self.assertTrue(is_reference_section_heading("REFERENCES"))
        self.assertTrue(is_reference_section_heading("Bibliography"))
        self.assertTrue(is_reference_section_heading("Tài liệu tham khảo"))
        self.assertFalse(is_reference_section_heading("Introduction"))
        self.assertFalse(is_reference_section_heading("Related Work"))


if __name__ == "__main__":
    unittest.main()
