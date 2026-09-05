#!/usr/bin/env python3
"""Quick local test runner for LayoutLingua.

Usage:
    python scripts/test.py
    python scripts/test.py -v
"""

from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Auto-delegate to local .venv python if current python lacks project packages
venv_python_win = ROOT / ".venv" / "Scripts" / "python.exe"
venv_python_nix = ROOT / ".venv" / "bin" / "python"
venv_python = venv_python_win if venv_python_win.is_file() else (venv_python_nix if venv_python_nix.is_file() else None)

if venv_python and Path(sys.executable).resolve() != venv_python.resolve() and "LAYOUTLINGUA_IN_VENV" not in os.environ:
    os.environ["LAYOUTLINGUA_IN_VENV"] = "1"
    res = subprocess.run([str(venv_python)] + sys.argv, cwd=str(ROOT))
    sys.exit(res.returncode)


def main() -> int:
    verbosity = 2 if "-v" in sys.argv or "--verbose" in sys.argv else 1
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern="test_*.py")
    runner = unittest.TextTestRunner(verbosity=verbosity)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
