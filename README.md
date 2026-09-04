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
</p>

<p align="center">
  <a href="https://github.com/ThanhNguyxnOrg/LayoutLingua/releases/latest"><img src="https://img.shields.io/github/v/release/ThanhNguyxnOrg/LayoutLingua?style=flat-square&label=release" alt="Latest Release"></a>
  <a href="https://github.com/ThanhNguyxnOrg/LayoutLingua/releases"><img src="https://img.shields.io/github/downloads/ThanhNguyxnOrg/LayoutLingua/total?style=flat-square&label=downloads" alt="Total Downloads"></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/ThanhNguyxnOrg/LayoutLingua?style=flat-square" alt="AGPL-3.0 License"></a>
  <img src="https://img.shields.io/badge/Python-standalone_bundle-2ea44f?style=flat-square" alt="Standalone Bundle">
</p>

<p align="center">
  <a href="#key-features">Features</a> ·
  <a href="#quick-start">Quick Start</a> ·
  <a href="#usage-guide">Usage</a> ·
  <a href="#agent-skill">Agent Skill</a> ·
  <a href="#vision--image-roadmap">Vision & OCR Roadmap</a> ·
  <a href="#license">License</a>
</p>

---

**LayoutLingua** is an open-source document translation platform available for Windows, macOS, Android, and command-line environments. It parses page geometry, isolates formulas and technical code blocks, translates prose through high-accuracy neural engines, and writes the translated content back to exact spatial coordinates without converting documents into plain text.

## Key Features

- **Strict Layout Preservation:** Keeps paragraph bounding boxes, formulas, tables, figures, tables of contents, and references intact.
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

### Android

1. **[Download APK from the latest Android release](https://github.com/ThanhNguyxnOrg/LayoutLingua/releases?q=android-v)** (`LayoutLingua-android-*.apk`).
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

### Install Globally

```powershell
npx skills add ThanhNguyxnOrg/LayoutLingua -g --all
```

### Run from Prompts

In your agent terminal:

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

## Architecture & Future Roadmap

LayoutLingua builds upon the foundational advances of leading document processing systems—synthesizing the formula preservation of **PDFMathTranslate**, precision diacritical ink-metric typography, the intermediate representation (IR) and Chinese/CJK engine of **[BabelDOC](https://github.com/funstory-ai/BabelDOC)**, and the multimodal vision capabilities of **[AllenAI olmOCR](https://github.com/allenai/olmocr)**.

For complete technical specifications, see [docs/architecture-roadmap.md](docs/architecture-roadmap.md).

### 1. Multilingual Chinese & CJK Expansion (Inspired by BabelDOC)
- **Decoupled Intermediate Representation (IR):** Decouples page layout geometry from semantic text streams, enabling lossless re-typesetting.
- **Cross-Page Paragraph Stitching:** Merges sentences that wrap across page boundaries or columns before translation.
- **Chinese/CJK Typesetting Engine:** Dynamic punctuation compression (*kinshoku shori*), character-spacing optimization, and integrated Google Noto Sans CJK SC/TC/JP/KR font cascades.
- **Document-Level Glossary Constraints:** Automated domain terminology extraction enforcing lexical consistency across whole documents.

### 2. Vision & Scanned Document Pipeline (Powered by olmOCR)
- **[AllenAI olmOCR](https://github.com/allenai/olmocr) Pipeline:** Multi-modal Vision-Language Models (e.g., Molmo, Qwen2-VL) transcribe dense scanned pages, multi-column research papers, and complex LaTeX equations into grounded Markdown with bounding boxes.
- **Text Erasure & Inpainting:** Background text removal via LaMa inpainting to preserve underlying graphics, charts, diagrams, and figures.
- **Composite Re-typesetting:** Overlay target translations seamlessly into original image coordinate frames.

---

## Building from Source

### Prerequisites

```powershell
git clone https://github.com/ThanhNguyxnOrg/LayoutLingua.git
cd LayoutLingua
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### Build Desktop Binaries

```powershell
# Windows
.\build.ps1

# macOS
bash build-macos.sh
```

---

## License

LayoutLingua is open-source software released under the [AGPL-3.0 License](LICENSE).
Maintained by **[ThanhNguyxnOrg](https://github.com/ThanhNguyxnOrg)**.
