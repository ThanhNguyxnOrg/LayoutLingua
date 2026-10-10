# LayoutLingua Scripts (`scripts`)

This directory contains command-line interfaces, packaging utilities, verification benchmarks, and developer tools for LayoutLingua.

## Primary CLI Tools

### 1. `translate_pdf.py` — Main Translation CLI

Translates text-based PDFs while preserving layout, tables, and formulas.

```bash
# Basic translation (defaults to Vietnamese)
python scripts/translate_pdf.py input.pdf --output-dir ./output

# Translate with specific engine and target language
python scripts/translate_pdf.py input.pdf --output-dir ./output --target-language fr --engine google

# Generate dual-language alternating PDF alongside mono translation
python scripts/translate_pdf.py input.pdf --output-dir ./output --dual

# Enforce custom terminology glossary (JSON, CSV, or JSONL)
python scripts/translate_pdf.py input.pdf --output-dir ./output --glossary my_glossary.json

# Offline Handoff Mode (export untranslated segments for external translation)
python scripts/translate_pdf.py input.pdf --engine handoff --emit-segments untranslated.jsonl

# Ingest translated segments back into the document
python scripts/translate_pdf.py input.pdf --output-dir ./output --engine handoff --segments translated.jsonl
```

#### CLI Options Reference

| Flag | Type | Description |
|---|---|---|
| `input_pdf` | `Path` | Path to the input PDF file. |
| `--output-dir` | `Path` | Directory where output files are written. |
| `--target-language` | `str` | Target language code (default: `vi`). Supports 48 languages. |
| `--source-language` | `str` | Source language code (default: `auto`). |
| `--pages` | `str` | Page selection range (e.g. `1,3-5`). |
| `--threads` | `int` | Number of worker threads (default: `4`, max: `8`). |
| `--engine` | `str` | MT service (`google`, `deeplx`, `handoff`). |
| `--dual` | `flag` | Generate dual-language PDF with alternating pages. |
| `--glossary` | `Path` | Path to JSON/CSV/JSONL terminology glossary. |
| `--overwrite` | `flag` | Overwrite destination file if it already exists. |
| `--ignore-cache` | `flag` | Bypass SQLite translation cache. |
| `--segments` | `Path` | Handoff mode: input JSONL segments file. |
| `--emit-segments` | `Path` | Handoff mode: output JSONL segments file. |

---

### 2. `verify_preservation.py` — Visual & Geometric Verification

Compares source and translated PDFs to verify layout fidelity:
- Page dimension and orientation preservation.
- Text bounding box overlap and margin drift.
- Visual difference heatmaps via OpenCV.

```bash
python scripts/verify_preservation.py source.pdf translated.pdf --diff-dir ./diff_images
```

---

### 3. `benchmark_speed.py` — Performance Benchmarking

Measures end-to-end processing throughput across thread counts, batch sizes, and translation backends.

```bash
python scripts/benchmark_speed.py --sample sample.pdf --runs 3
```

---

### 4. Build & Maintenance Scripts

- **`package.py`**: Builds standalone frozen binaries using PyInstaller (`app.spec` on Windows, `app-macos.spec` on macOS, `app-linux.spec` on Linux).
- **`set_version.py`**: Synchronizes version strings across `app/update.py`, `android/build.gradle.kts`, `CITATION.cff`, and documentation.
- **`generate_sample_pdf.py`**: Generates synthetic multi-column, table, and formula PDFs for automated regression testing.
