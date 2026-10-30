#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

echo "========================================================"
echo "          LayoutLingua Desktop Application"
echo "========================================================"

# 1. If standalone binary exists in release/LayoutLingua and not building, launch it
if [[ "${1:-}" != "--build-exe" && "${1:-}" != "--build-bin" ]]; then
  if [[ -x "release/LayoutLingua/LayoutLingua" ]]; then
    echo "[*] Launching precompiled LayoutLingua standalone app..."
    exec "release/LayoutLingua/LayoutLingua" "$@"
  fi
fi

# Detect Python 3
PYTHON_BIN=""
for cmd in python3 python; do
  if command -v "$cmd" >/dev/null 2>&1; then
    PYTHON_BIN="$cmd"
    break
  fi
done

if [[ -z "$PYTHON_BIN" ]]; then
  echo "[!] Python 3.10+ is required to run LayoutLingua." >&2
  echo "Please install Python from https://www.python.org/ or your package manager." >&2
  exit 1
fi

# 2. Build frontend production bundle once if dist/index.html does not exist
if [[ ! -f "dist/index.html" ]]; then
  if ! command -v node >/dev/null 2>&1; then
    echo "[!] Node.js 18+ is required for first-time UI compilation." >&2
    exit 1
  fi
  if [[ ! -d "node_modules" ]]; then
    echo "[*] Installing UI dependencies..."
    npm install --legacy-peer-deps
  fi
  echo "[*] Compiling LayoutLingua Desktop UI..."
  npm run build
fi

# 3. Ensure Python engine and desktop dependencies are installed
if ! "$PYTHON_BIN" -c "import pymupdf" >/dev/null 2>&1; then
  echo "[*] Installing LayoutLingua Python engine dependencies..."
  "$PYTHON_BIN" -m pip install -r requirements.txt
fi

if ! "$PYTHON_BIN" -c "import webview" >/dev/null 2>&1; then
  echo "[*] Installing pywebview native desktop host..."
  "$PYTHON_BIN" -m pip install pywebview || true
fi

# 4. If user requested --build-exe / --build-bin
if [[ "${1:-}" == "--build-exe" || "${1:-}" == "--build-bin" ]]; then
  echo "[*] Building standalone desktop application executable..."
  "$PYTHON_BIN" -m layoutlingua.desktop --build-exe
  exit $?
fi

# 5. Launch native desktop application window
echo "[*] Launching LayoutLingua native desktop application..."
exec "$PYTHON_BIN" -m layoutlingua.desktop "$@"

