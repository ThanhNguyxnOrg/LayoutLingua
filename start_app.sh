#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

echo "========================================================"
echo "          LayoutLingua AI Translation Studio"
echo "========================================================"

if ! command -v node >/dev/null 2>&1; then
  echo "[!] Node.js is required but not found. Please install Node.js 18+ to proceed."
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1 && ! command -v python >/dev/null 2>&1; then
  echo "[!] Python 3 is required but not found. Please install Python 3.10+ to proceed."
  exit 1
fi

if [ ! -d "node_modules" ]; then
  echo "[*] Installing Node dependencies..."
  npm install --legacy-peer-deps
fi

echo "[*] Launching LayoutLingua AI Studio at http://localhost:3000..."
if command -v open >/dev/null 2>&1; then
  (sleep 2 && open http://localhost:3000) &
elif command -v xdg-open >/dev/null 2>&1; then
  (sleep 2 && xdg-open http://localhost:3000) &
fi

npm run dev
