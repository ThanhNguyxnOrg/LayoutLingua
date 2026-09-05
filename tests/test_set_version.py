from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.set_version import set_version


class SetVersionTests(unittest.TestCase):
    def test_valid_version_cleaning(self):
        try:
            self.assertEqual(set_version("v1.2.3"), "1.2.3")
            self.assertEqual(set_version("V2.0.0"), "2.0.0")
        finally:
            set_version("1.0.0")

    def test_invalid_version_raises(self):
        with self.assertRaises(ValueError):
            set_version("invalid")
        with self.assertRaises(ValueError):
            set_version("v1.2")
        with self.assertRaises(ValueError):
            set_version("1.2.3.4")


if __name__ == "__main__":
    unittest.main()
