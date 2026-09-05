#!/usr/bin/env python3
"""One-command automated release tool for LayoutLingua.

Usage:
    python scripts/release.py <version>    # e.g. python scripts/release.py 1.0.1
    python scripts/release.py patch        # e.g. 1.0.0 -> 1.0.1
    python scripts/release.py minor        # e.g. 1.0.0 -> 1.1.0
    python scripts/release.py major        # e.g. 1.0.0 -> 2.0.0

What this tool does:
1. Validates and determines the target semantic version.
2. Synchronizes version across all platforms (app/update.py, android gradle, UI).
3. Ensures CHANGELOG.md has a section for the new version.
4. Commits changes as 'chore(release): v<version>'.
5. Creates git tags 'v<version>' and 'android-v<version>'.
6. Pushes commit and tags to origin main to trigger GitHub Actions release build.
"""

from __future__ import annotations

import argparse
import datetime
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.set_version import set_version


def get_current_version() -> str:
    update_py = ROOT / "app" / "update.py"
    if not update_py.is_file():
        raise FileNotFoundError("app/update.py not found")
    content = update_py.read_text(encoding="utf-8")
    m = re.search(r'APP_VERSION = "([^"]+)"', content)
    if not m:
        raise ValueError("Could not find APP_VERSION in app/update.py")
    return m.group(1).strip()


def bump_version(current: str, part: str) -> str:
    pieces = [int(p) for p in current.split(".")]
    while len(pieces) < 3:
        pieces.append(0)
    major, minor, patch = pieces[:3]

    if part == "patch":
        patch += 1
    elif part == "minor":
        minor += 1
        patch = 0
    elif part == "major":
        major += 1
        minor = 0
        patch = 0
    else:
        raise ValueError(f"Unknown bump part: {part}")
    return f"{major}.{minor}.{patch}"


def ensure_changelog(version: str) -> None:
    changelog = ROOT / "CHANGELOG.md"
    if not changelog.is_file():
        return

    content = changelog.read_text(encoding="utf-8")
    header_pattern = rf'##\s*\[?v?{re.escape(version)}\]?'
    if re.search(header_pattern, content):
        return

    today = datetime.date.today().isoformat()
    new_entry = f"\n## [{version}] - {today}\n\n### Changed\n- Maintenance update and bug fixes.\n"

    # Insert after header
    marker = "and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).\n"
    if marker in content:
        parts = content.split(marker, 1)
        updated = parts[0] + marker + new_entry + parts[1]
    else:
        updated = new_entry + "\n" + content

    changelog.write_text(updated, encoding="utf-8")
    print(f"[OK] Added release section for [{version}] to CHANGELOG.md")


def run(cmd: list[str]) -> None:
    print(f"--> {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=ROOT)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def main() -> int:
    parser = argparse.ArgumentParser(description="One-command release manager for LayoutLingua")
    parser.add_argument(
        "version",
        help="Target version (e.g. 1.0.1, v1.0.1) or bump increment (patch, minor, major)",
    )
    parser.add_argument(
        "--no-push",
        action="store_true",
        help="Commit and tag locally, but do not push to origin",
    )
    args = parser.parse_args()

    current = get_current_version()
    arg_val = args.version.lower().strip()

    if arg_val in ("patch", "minor", "major"):
        target_version = bump_version(current, arg_val)
    else:
        target_version = arg_val.lstrip("vV")
        if not re.fullmatch(r"\d+\.\d+\.\d+", target_version):
            print(f"Error: Invalid version format {args.version!r}. Expected X.Y.Z, patch, minor, or major.", file=sys.stderr)
            return 1

    print(f"Current version: {current}")
    print(f"Target version:  {target_version}")

    # 1. Update version in source files
    set_version(target_version)

    # 2. Ensure CHANGELOG.md has entry
    ensure_changelog(target_version)

    # 3. Git commit
    run(["git", "add", "app/update.py", "android/app/build.gradle.kts", "CHANGELOG.md"])
    for p in ROOT.glob("Redesign/*/package.json"):
        run(["git", "add", str(p.relative_to(ROOT))])
    for p in ROOT.glob("Redesign/*/src/App.tsx"):
        run(["git", "add", str(p.relative_to(ROOT))])

    # Check if anything to commit
    diff_check = subprocess.run(["git", "diff", "--staged", "--quiet"], cwd=ROOT)
    if diff_check.returncode != 0:
        run(["git", "commit", "-m", f"chore(release): v{target_version}"])
    else:
        print("[INFO] No file changes to commit, proceeding to tag.")

    # 4. Git tags
    tag_name = f"v{target_version}"
    android_tag = f"android-v{target_version}"

    # Remove local tag if exists
    subprocess.run(["git", "tag", "-d", tag_name], cwd=ROOT, capture_output=True)
    subprocess.run(["git", "tag", "-d", android_tag], cwd=ROOT, capture_output=True)

    run(["git", "tag", tag_name])
    run(["git", "tag", android_tag])
    print(f"[OK] Created git tags: {tag_name} and {android_tag}")

    # 5. Git push
    if not args.no_push:
        print(f"\nPushing commit and tags to origin main...")
        run(["git", "push", "origin", "main"])
        run(["git", "push", "origin", tag_name, android_tag])
        print(f"\n=======================================================")
        print(f"  RELEASE TRIGGERED SUCCESSFULLY: {tag_name}")
        print(f"  GitHub Actions is now building 4-platform artifacts.")
        print(f"  Check progress at: https://github.com/ThanhNguyxnOrg/LayoutLingua/actions")
        print(f"=======================================================")
    else:
        print(f"\n[INFO] --no-push set. Committed and tagged locally.")
        print(f"To publish to GitHub, run:\n  git push origin main && git push origin {tag_name} {android_tag}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
