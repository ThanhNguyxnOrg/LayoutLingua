# 📋 Changelog & Release Notes

<p align="left">
  <img src="https://img.shields.io/badge/Version-v1.0.0-blue?style=flat-square" alt="Version 1.0.0">
  <img src="https://img.shields.io/badge/Release_Status-Production_Ready-brightgreen?style=flat-square" alt="Production Ready">
  <img src="https://img.shields.io/badge/SemVer-2.0.0-informational?style=flat-square" alt="SemVer">
</p>

All notable changes to **LayoutLingua** across Windows, macOS, Linux, and Android are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-09-05

### Added
- **4-Platform Native Releases**: First official stable release supporting Windows (`.zip`), macOS (`.dmg` for Apple Silicon & Intel), Linux (`.tar.gz`), and Android (`.apk`).
- **Universal Multi-lingual Prose Recognition**: Advanced regex engine for isolating prose blocks from math formulas across Vietnamese with diacritics/tone marks, CJK (Chinese, Japanese, Korean), Cyrillic (Russian, Ukrainian), Arabic, Hebrew, and European Latin languages.
- **Smart Automated Release CI/CD**: Keyword-triggered GitHub Actions pipeline (`release: X.Y.Z`) with automatic version synchronization across all platforms, automated tagging, and multi-platform release asset bundling.
- **Dark Obsidian UI**: Refined cross-platform desktop user interface featuring high-contrast sleek design tokens, crisp vector icons, and real-time per-page translation progress.
- **Native Android Companion**: Android app with Google Translate integration and PDFBox layout preservation engine.
- **Grammar-Aware Formula Placeholders**: Resilient tag balancing allowing target language grammatical permutations while strictly protecting inline vectors and formulas.
- **TOC & Link Preservation**: Full preservation of PDF Table of Contents (TOC) link annotations and visual formatting geometry.

## [0.2.5] - 2026-08-20

### Added
- Seamless background auto-updater for Windows desktop.
- Initial PDF Table of Contents (TOC) link preservation and anchor verification.
- Improved font fallback handling for specialized math characters.
