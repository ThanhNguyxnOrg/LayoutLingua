<p align="center">
  <img src=".github/assets/logo.png" alt="LayoutLingua Logo" width="160">
</p>

<h1 align="center">LayoutLingua</h1>

<p align="center">
  <strong>High-precision document translation engine that preserves 100% of formatting,<br>mathematical formulas, tables, and typography geometry.</strong>
</p>

<p align="center">
  <sub>Maintained and developed by <a href="https://github.com/ThanhNguyxnOrg">ThanhNguyxnOrg</a></sub>
</p>

<p align="center">
  <a href="https://github.com/ThanhNguyxnOrg/LayoutLingua/releases/latest/download/LayoutLingua-windows.zip">
    <img src="https://img.shields.io/badge/DOWNLOAD-Windows_x64-1f6feb?style=for-the-badge&logo=windows11&logoColor=white" alt="Download LayoutLingua for Windows">
  </a>
  <a href="https://github.com/ThanhNguyxnOrg/LayoutLingua/releases/latest/download/LayoutLingua-macos-apple-silicon.dmg">
    <img src="https://img.shields.io/badge/DOWNLOAD-macOS_Apple_Silicon-111111?style=for-the-badge&logo=apple&logoColor=white" alt="Download LayoutLingua for macOS Apple Silicon">
  </a>
  <a href="https://github.com/ThanhNguyxnOrg/LayoutLingua/releases/latest/download/LayoutLingua-macos-intel.dmg">
    <img src="https://img.shields.io/badge/DOWNLOAD-macOS_Intel-555555?style=for-the-badge&logo=apple&logoColor=white" alt="Download LayoutLingua for macOS Intel">
  </a>
  <a href="https://github.com/ThanhNguyxnOrg/LayoutLingua/releases/latest/download/LayoutLingua-linux-x86_64.tar.gz">
    <img src="https://img.shields.io/badge/DOWNLOAD-Linux_x64-FCC624?style=for-the-badge&logo=linux&logoColor=black" alt="Download LayoutLingua for Linux">
  </a>
  <a href="https://github.com/ThanhNguyxnOrg/LayoutLingua/releases/latest">
    <img src="https://img.shields.io/badge/DOWNLOAD-Android_APK-3DDC84?style=for-the-badge&logo=android&logoColor=white" alt="Download LayoutLingua for Android">
  </a>
</p>

<p align="center">
  <a href="https://github.com/ThanhNguyxnOrg/LayoutLingua/releases/latest"><img src="https://img.shields.io/github/v/release/ThanhNguyxnOrg/LayoutLingua?style=flat-square&label=release" alt="Latest Release"></a>
  <a href="https://github.com/ThanhNguyxnOrg/LayoutLingua/releases"><img src="https://img.shields.io/github/downloads/ThanhNguyxnOrg/LayoutLingua/total?style=flat-square&label=downloads" alt="Total Downloads"></a>
  <a href="CHANGELOG.md"><img src="https://img.shields.io/badge/Changelog-v1.0.0-blue?style=flat-square" alt="Changelog"></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/ThanhNguyxnOrg/LayoutLingua?style=flat-square" alt="AGPL-3.0 License"></a>
  <img src="https://img.shields.io/badge/Python-standalone_bundle-2ea44f?style=flat-square" alt="Standalone Bundle">
</p>

<p align="center">
  <a href="#key-features">Features</a> ·
  <a href="#quick-start">Quick Start</a> ·
  <a href="#usage-guide">Usage</a> ·
  <a href="#agent-skill">Agent Skill</a> ·
  <a href="docs/development.md">Developer Guide</a> ·
  <a href="CHANGELOG.md">Changelog</a> ·
  <a href="#license">License</a>
</p>

---

**LayoutLingua** is an open-source document translation platform available for Windows, macOS, Linux, Android, and command-line environments. It parses page geometry, isolates formulas and technical code blocks, translates prose through high-accuracy neural engines, and writes the translated content back to exact spatial coordinates without converting documents into plain text.

## Key Features

- **Strict Layout Preservation:** Keeps paragraph bounding boxes, formulas, tables, figures, tables of contents, and references intact.
- **Universal Multi-lingual Recognition:** Deep isolation of technical formulas in documents written in Vietnamese (with full tone marks), CJK (Chinese, Japanese, Korean), Cyrillic (Russian, etc.), Arabic, Hebrew, and European Latin alphabets.
- **4 Native Platforms:** Ready-to-use binaries for Windows, macOS (Apple Silicon & Intel), Linux (x86_64), and Android.
- **Ready Out of the Box:** Download, extract, and run. Packaged desktop releases do not require Python or manual model downloads.
- **Batch Processing:** Drag and drop multiple files or entire folder trees into the processing queue.
- **Resilient Batch Execution:** A damaged or unsupported file logs an error and continues without stopping the rest of the queue.
- **Background Auto-Updater (Windows):** Checks for new releases in the background, downloads updates, and stages safe seamless swaps.
- **Native Android Companion:** Lightweight Android application powered by PDFBox-Android and Google Translate for on-the-go reading.
- **AI Agent Skill Mode:** Built-in Handoff mode adhering to the Agent Skills standard, allowing local LLMs (Codex, Claude Code, Copilot, Gemini) to translate domain-specific technical papers with full context awareness.

## Quick Start

### Windows

1. **[Download LayoutLingua for Windows](https://github.com/ThanhNguyxnOrg/LayoutLingua/releases/latest/download/LayoutLingua-windows.zip)** (`.zip`).
2. Extract the archive completely.
3. Run `LayoutLingua.exe`.

### macOS

1. Download the installer for your Mac architecture:
   - **[Apple Silicon (M1/M2/M3/M4)](https://github.com/ThanhNguyxnOrg/LayoutLingua/releases/latest/download/LayoutLingua-macos-apple-silicon.dmg)**
   - **[Intel](https://github.com/ThanhNguyxnOrg/LayoutLingua/releases/latest/download/LayoutLingua-macos-intel.dmg)**
2. Open the `.dmg` file and drag **LayoutLingua** to your **Applications** folder.
3. On first launch, right-click the app icon → **Open** → **Open**.

### Linux (x86_64)

1. **[Download LayoutLingua for Linux](https://github.com/ThanhNguyxnOrg/LayoutLingua/releases/latest/download/LayoutLingua-linux-x86_64.tar.gz)** (`.tar.gz`).
2. Extract and launch:
   ```bash
   tar -xzf LayoutLingua-linux-x86_64.tar.gz
   cd LayoutLingua && ./LayoutLingua
   ```

### Android

1. **[Download APK from the latest release](https://github.com/ThanhNguyxnOrg/LayoutLingua/releases/latest)** (`LayoutLingua-android-*.apk`).
2. Install the APK on your device (Android 8.0+ supported).

To build Android from source:

```bash
cd android
./gradlew assembleDebug
```

## Usage Guide

### 1. Add Documents
- Drag and drop PDF files or folders directly onto the application window.
- Or click **Select Files** / **Select Folder**.

### 2. Choose Target Language
- Select your target language from the dropdown menu (Default: English / Vietnamese, with 36 Latin-script languages supported).

### 3. Translate
- Click **Translate**. Each file displays live per-page progress.
- Results are saved into a `translated/` subfolder next to each input file:
  ```text
  Documents/
  ├── research-paper.pdf
  └── translated/
      └── research-paper-en.pdf
  ```

---

## Agent Skill

LayoutLingua follows the [Agent Skills](https://agentskills.io/) specification and integrates directly into AI coding tools (Claude Code, Codex, GitHub Copilot, Antigravity).

### Install

The `skills` CLI pulls directly from GitHub repositories or local directories (no npm publishing required):

```powershell
# Install directly from GitHub:
npx skills add ThanhNguyxnOrg/LayoutLingua -g --all

# Or install from a local clone (offline / dev):
npx skills add . -g --all
```

### Run from Prompts

In your agent session or terminal:

```text
/layout-lingua translate document.pdf into English
```

### Dual-Engine Modes

| Mode | Engine | Best Suited For |
| :--- | :--- | :--- |
| **Google (Default)** | `translate.google.com` | Rapid batch translation without API tokens |
| **Handoff** | Active AI Agent Session | Technical papers, specialized terminology, high accuracy |

In **Handoff** mode, translatable text is extracted to JSONL chunks, translated by the LLM in context, and rebuilt back into the PDF with exact formula markers preserved.

---

## Developer Resources

Looking to contribute, run tests, understand the translation pipeline, or build binaries from source?

- 📖 **[Developer Guide & CI/CD Pipeline](docs/development.md):** Architecture and translation pipeline, local environment setup, fast test runner, automated GitHub Actions testing CI, cross-platform build scripts, and cloud release automation.
- 📐 **[Architecture & Vision Roadmap](docs/architecture-roadmap.md):** Deep-dive into layout geometry, formula tokenization, BabelDOC CJK engine integration, and olmOCR multi-modal vision pipeline.
- 🧪 **Automated Cloud CI:** Every code commit automatically runs our test suite via [`.github/workflows/test.yml`](.github/workflows/test.yml). Skip-CI applies automatically to documentation edits.

## License

LayoutLingua is open-source software released under the [AGPL-3.0 License](LICENSE).
Maintained by **[ThanhNguyxnOrg](https://github.com/ThanhNguyxnOrg)**.
