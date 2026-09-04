#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
VENV="$ROOT/.venv-linux"
PYTHON_BIN="$VENV/bin/python3"
SKIP_ASSETS=0

if [[ "${1:-}" == "--skip-assets" ]]; then
  SKIP_ASSETS=1
elif [[ $# -gt 0 ]]; then
  echo "Usage: ./build-linux.sh [--skip-assets]" >&2
  exit 2
fi

if [[ "$(uname -s)" != "Linux" ]]; then
  echo "This script must run on Linux (e.g. Ubuntu 22.04+). For Windows or macOS, use their respective build scripts." >&2
  exit 1
fi

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "==> Creating the Linux virtual environment"
  python3 -m venv "$VENV"
fi

echo "==> Installing app and packaging dependencies"
"$PYTHON_BIN" -m pip install --upgrade pip
"$PYTHON_BIN" -m pip install -r "$ROOT/requirements-app.txt"

if [[ $SKIP_ASSETS -eq 0 ]]; then
  echo "==> Fetching the layout model and font"
  "$PYTHON_BIN" "$ROOT/scripts/fetch_assets.py"
fi

echo "==> Running PyInstaller for Linux ($(uname -m))"
"$PYTHON_BIN" -m PyInstaller --noconfirm --clean "$ROOT/app-linux.spec"

DIST_DIR="$ROOT/dist/LayoutLingua"
EXECUTABLE="$DIST_DIR/LayoutLingua"
if [[ ! -x "$EXECUTABLE" ]]; then
  echo "PyInstaller did not produce an executable at $EXECUTABLE" >&2
  exit 1
fi

echo "==> Creating desktop entry and icon for Linux desktop integration"
cat > "$DIST_DIR/LayoutLingua.desktop" <<EOF
[Desktop Entry]
Name=LayoutLingua
Comment=Preserve-layout and math formula PDF translator
Exec=LayoutLingua
Icon=icon
Terminal=false
Type=Application
Categories=Office;Publishing;Utility;
EOF
cp "$ROOT/app/assets/icon.png" "$DIST_DIR/icon.png"

echo "==> Packaging tar.gz archive"
ARCH="$(uname -m)"
TARBALL="$ROOT/dist/LayoutLingua-linux-$ARCH.tar.gz"
tar -czf "$TARBALL" -C "$ROOT/dist" LayoutLingua

echo "==> Linux build complete: $TARBALL"
