from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.set_version import set_version_in_root


class SetVersionTests(unittest.TestCase):
    def test_version_cleaning_in_temp_dir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            app_dir = root / "app"
            app_dir.mkdir()
            update_py = app_dir / "update.py"
            update_py.write_text('APP_VERSION = "0.1.0"\n', encoding="utf-8")

            android_dir = root / "android" / "app"
            android_dir.mkdir(parents=True)
            gradle_kts = android_dir / "build.gradle.kts"
            gradle_kts.write_text('val appVersionName = "0.1.0"\n', encoding="utf-8")

            changelog = root / "CHANGELOG.md"
            changelog.write_text('<img src="https://img.shields.io/badge/Version-v0.1.0-blue?style=flat-square" alt="Version 0.1.0">\n', encoding="utf-8")

            citation = root / "CITATION.cff"
            citation.write_text('cff-version: 1.2.0\nversion: 0.1.0\n', encoding="utf-8")

            ver = set_version_in_root("v1.2.3", root=root)
            self.assertEqual(ver, "1.2.3")
            self.assertIn('APP_VERSION = "1.2.3"', update_py.read_text(encoding="utf-8"))
            self.assertIn('val appVersionName = "1.2.3"', gradle_kts.read_text(encoding="utf-8"))
            self.assertIn('Version-v1.2.3-blue', changelog.read_text(encoding="utf-8"))
            self.assertIn('version: 1.2.3', citation.read_text(encoding="utf-8"))

    def test_invalid_version_raises(self):
        with self.assertRaises(ValueError):
            set_version_in_root("invalid")
        with self.assertRaises(ValueError):
            set_version_in_root("v1.2")
        with self.assertRaises(ValueError):
            set_version_in_root("1.2.3.4")


if __name__ == "__main__":
    unittest.main()
