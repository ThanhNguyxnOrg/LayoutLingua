#!/usr/bin/env bash
cd "$(dirname "$0")"
chmod +x ./LayoutLingua.sh 2>/dev/null || true
./LayoutLingua.sh "$@"

