#!/usr/bin/env python3
"""Synchronize project version across all platforms and build configurations."""

from __future__ import annotations

import re
import sys
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parents[1]


def set_version_in_root(version: str, root: Path | None = None) -> str:
    target_root = root or DEFAULT_ROOT
    clean = version.strip().lstrip("vV")
    if not re.fullmatch(r"\d+\.\d+\.\d+", clean):
        raise ValueError(f"Invalid semantic version: {version!r}. Expected format: X.Y.Z (e.g. 1.0.1)")

    # 1. app/update.py
    update_py = target_root / "app" / "update.py"
    if update_py.is_file():
        content = update_py.read_text(encoding="utf-8")
        new_content, count = re.subn(r'APP_VERSION = "[^"]+"', f'APP_VERSION = "{clean}"', content)
        if count > 0:
            update_py.write_text(new_content, encoding="utf-8")
            print(f"[OK] app/update.py -> APP_VERSION = \"{clean}\"")

    # 2. android/app/build.gradle.kts
    gradle_kts = target_root / "android" / "app" / "build.gradle.kts"
    if gradle_kts.is_file():
        content = gradle_kts.read_text(encoding="utf-8")
        new_content, count = re.subn(r'val appVersionName = "[^"]+"', f'val appVersionName = "{clean}"', content)
        if count > 0:
            gradle_kts.write_text(new_content, encoding="utf-8")
            print(f"[OK] android/app/build.gradle.kts -> appVersionName = \"{clean}\"")

    return clean


def set_version(version: str) -> str:
    return set_version_in_root(version, root=DEFAULT_ROOT)


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python scripts/set_version.py <version>", file=sys.stderr)
        print("Example: python scripts/set_version.py 1.0.1", file=sys.stderr)
        return 1

    try:
        ver = set_version(sys.argv[1])
        print(f"Successfully updated all platforms to version {ver}")
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
