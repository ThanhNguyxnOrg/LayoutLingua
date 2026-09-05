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

    # 3. CHANGELOG.md badge
    changelog = target_root / "CHANGELOG.md"
    if changelog.is_file():
        content = changelog.read_text(encoding="utf-8")
        new_content, count1 = re.subn(r'img\.shields\.io/badge/Version-v[0-9.]+-blue', f'img.shields.io/badge/Version-v{clean}-blue', content)
        new_content, count2 = re.subn(r'alt="Version [0-9.]+"', f'alt="Version {clean}"', new_content)
        if count1 > 0 or count2 > 0:
            changelog.write_text(new_content, encoding="utf-8")
            print(f"[OK] CHANGELOG.md -> Version badge = \"v{clean}\"")

    # 4. CITATION.cff version & date
    citation_cff = target_root / "CITATION.cff"
    if citation_cff.is_file():
        content = citation_cff.read_text(encoding="utf-8")
        new_content, count = re.subn(r'(?m)^version:\s*[0-9.]+', f'version: {clean}', content)
        if count > 0:
            citation_cff.write_text(new_content, encoding="utf-8")
            print(f"[OK] CITATION.cff -> version = \"{clean}\"")

    # 5. README.md badges
    readme = target_root / "README.md"
    if readme.is_file():
        content = readme.read_text(encoding="utf-8")
        new_content, count1 = re.subn(r'badge/Changelog-v[0-9.]+-blue', f'badge/Changelog-v{clean}-blue', content)
        new_content, count2 = re.subn(r'badge/Version-v[0-9.]+-blue', f'badge/Version-v{clean}-blue', new_content)
        new_content, count3 = re.subn(r'badge/Roadmap-v[0-9.]+-blueviolet', f'badge/Roadmap-v{clean}-blueviolet', new_content)
        if count1 > 0 or count2 > 0 or count3 > 0:
            readme.write_text(new_content, encoding="utf-8")
            print(f"[OK] README.md -> Version badges = \"v{clean}\"")

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
