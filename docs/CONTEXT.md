# LayoutLingua Domain Context & Ubiquitous Language

<p align="center">
  <a href="../README.md">🏠 README</a> ·
  <a href="ARCHITECTURE.md">🏛 Architecture</a> ·
  <a href="ALGORITHM.md">🧮 Algorithms</a> ·
  <a href="API_REFERENCE.md">🔌 API</a> ·
  <a href="CHANGELOG.md">📜 Changelog</a> ·
  <a href="CONTEXT.md">🧭 Context</a> ·
  <a href="CONTRIBUTING.md">🤝 Contributing</a> ·
  <a href="CODE_OF_CONDUCT.md">🌈 Conduct</a> ·
  <a href="SECURITY.md">🔐 Security</a>
</p>

---

This document serves as the single source of truth for ubiquitous domain terminology, core rules, and system concepts for **LayoutLingua**.

---

## 1. Core Architecture Concepts

**Decoupled Intermediate Representation (IR)**:
A two-layer data structure separating visual layout geometry (bounding boxes, font metrics, color spaces) from semantic text contents (reading order, sentence stitching), allowing layout preservation without direct PDF stream mutation during translation.

**Independent Python Engine**:
The standalone core processing engine written in Python (using PyMuPDF, DocLayout-YOLO, ONNX Runtime). It functions as a first-class CLI tool and an IPC server, running headless on any CI/CD virtual machine.

**Desktop Client**:
The cross-platform graphical user interface built with Tauri v2 (Rust backend), React 19, TypeScript, and Tailwind CSS. It communicates with the independent Python core engine via headless JSON-RPC stdio. All user-facing UI, dialogs, status indicators, and logs are strictly 100% English.

**Early Contract Skeleton**:
The initial end-to-end operational pipeline combining the IR, a Mock Translation Provider, minimal CLI, and JSON-RPC stdio IPC to verify process execution before layering heavy layout and typesetting engines.

---

## 2. Translation Architecture & Resiliency

**Track A (Stable Zero-Key Offline)**:
Local offline neural machine translation powered by open-source engines like **Argos Translate** (OpenNMT models cached locally). Zero API keys, zero rate limits, zero privacy leakage.

**Track B (Experimental Web Translation)**:
Free Google Translate RPC utilizing Intelligent Batch Packing, disk caching, and rate throttling. If a CAPTCHA or hard block is encountered, the provider aborts immediately and reports to the user without attempting deceptive background provider hijacking.

**AI Provider Tier (Configurable, Non-Hardcoded)**:
Cloud AI translation utilizing active, user-selectable models:
- *Google AI Studio*: Production models (e.g., `gemini-3.1-flash-lite`) with mandatory **Privacy Disclosure** alerting users that free tier inputs may be reviewed or used for model training.
- *OpenAI-Compatible Standard*: Supports Groq (active models e.g., `openai/gpt-oss-120b`), DeepSeek, OpenAI, and local Ollama (`localhost:11434`).

**Persistent Segment Cache**:
An on-disk SQLite store (`layoutlingua_translations.db`) indexed by SHA-256 fingerprint (`source_lang + target_lang + provider_model + masked_text`). Guarantees that every translated segment is persisted across application restarts, session terminations, or rate limit halts, eliminating duplicate API costs and redundant network requests.

**Cached Translation Provider (Deep Seam)**:
A transparent decorator implementing `BaseTranslationProvider` that wraps any underlying translation engine. It partitions incoming batches into cache hits and cache misses, dispatches only unseen segments over the wire, and atomically commits newly translated segments to the persistent store.

**Graceful Failover Matrix**:
The systematic escalation policy when a provider encounters rate limits (HTTP 429) or transport failures:
1. If the user has configured API keys for secondary providers (Gemini / Groq / OpenAI), the system permits 1-click or automatic failover to continue translation.
2. If no secondary keys are configured, the engine safely halts with fail-closed semantics, preserving 100% of processed pages in the Persistent Segment Cache and rendering actionable configuration shortcuts in the desktop UI.

---

## 3. Geometry & Layout Terminology

**Layout Region**:
A segmented area on a document page classified by the layout model into semantic categories: `text`, `title`, `figure`, `table`, `formula`, `header`, `footer`, or `abandon`.

**Spatial DAG (Spatial Directed Acyclic Graph)**:
A 2D spatial graph where nodes represent layout boxes and directed edges define human reading precedence across columns and spanning elements.

**Gutter**:
The whitespace channel separating multi-column blocks or adjacent cells in borderless tables. Text reflow must never cross gutter boundaries.

**Tabular Row Isolation**:
The preservation rule where cells and rows in borderless tables are separated into isolated bounds rather than merged into wrapped prose.

---

## 4. Mathematical Formula & Typography Invariants

**Formula Placeholder**:
A transient token pair (`<bN></bN>`) wrapping untranslatable equations and math glyphs during translation, protected by whitespace boundaries to prevent translation engines from fusing tags.

**Fraction-Aware Line Clustering**:
A baseline grouping algorithm that tolerates vertical fraction offsets ($\Delta y_{\text{fraction}} \le 0.75 \times \text{font\_size}$) to bind numerators, fraction bars, and denominators into their parent baseline sequence.

**Ink Floor & Leading Floor**:
The vertical metric boundary ($1.10\,\text{em}$ for Vietnamese) below which line leading is strictly forbidden from compressing, preventing stacked diacritics (`ệ`, `ở`) from overlapping adjacent lines.

**Fail-Closed Preservation**:
The invariant design rule where un-fittable or corrupted segments automatically fall back to the original source text rather than outputting broken layouts.

---

## 5. Typesetting & Rendering Terminology (Slice 4A)

**TypesetEngine**:
A deep module interface that transforms translated Document IR and original PDF bytes into a layout-preserved rendered PDF along with a structured fitting telemetry report.

**Non-Destructive Text Clearance**:
Selective redaction executed via `page.add_redact_annot(rect, fill=False)` and `page.apply_redactions(images=PDF_REDACT_IMAGE_NONE, graphics=PDF_REDACT_LINE_ART_NONE, text=PDF_REDACT_TEXT_REMOVE)` to eliminate original text glyphs without painting solid white blocks or destroying background color fills and vector artwork.

**Adaptive Font Shrinkage**:
A bounded iterative reduction of font size down to $f_{\min} = \max(6.0\,\text{pt}, 0.70 \times f_{\text{original}})$ to accommodate expanded translated prose (such as Vietnamese) within the original span bounds.

**Fail-Closed Text Fallback**:
A typesetting safety invariant where, if translated text cannot fit safely within bounding box bounds even after maximum adaptive shrinkage, the engine retains the original source text instead of silently clipping or rendering an empty void.

**Fitting Report**:
Structured telemetry recording replaced block counts, overflow events, initial versus final font sizes, and fallback reasons for each processed layout region.

**Bundled Unicode Font Asset**:
A version-pinned, license-compliant TrueType font (`DejaVuSans.ttf`) embedded directly in the repository to guarantee identical, deterministic Vietnamese diacritic rendering across all operating systems and headless CI environments.

---

## 6. Precision Typography & Fitting Telemetry (Slice 4B)

**Binary Search Font Fitting**:
A monotonically convergent search over the continuous font size interval $[f_{\min}, f_{\text{original}}]$ with stopping tolerance $\epsilon = 0.2\,\text{pt}$ and a hard iteration cap ($\le 7$), replacing discrete step-downs to guarantee the largest legible font size that fits the bounding box.

**Dynamic Line-Height Floor**:
A font-metric-driven line-height calculation:
$$L_{\text{effective}} = \max(L_{\text{configured}},\, \text{ascender} - \text{descender} + p)$$
where $p$ is empirical safety padding ($0.03\,\text{em}$), ensuring stacked diacritics (`ệ`, `ở`, `ứ`) maintain vertical clearance across adjacent lines.

**Overflow Cause Taxonomy**:
Structured classification of layout failures when text cannot fit even at $f_{\min}$:
- `OVERFLOW_HEIGHT`: Total wrapped line height exceeds vertical bounding box dimension.
- `OVERFLOW_WIDTH_AT_MIN_SIZE`: A single unbreakable word or token exceeds the available bounding box width.
- `OVERFLOW_UNDETERMINED`: Ambiguous or compound constraint violations.

**Two-Tier Fitting Telemetry**:
A hierarchical diagnostic data model combining document-wide summaries (`avg_shrink_ratio`, `worst_shrink_ratio`, `severe_shrink_blocks_count`) with per-page summaries (`PageFittingSummary`) and block-level audit records (`BlockFittingDetail`).


