# Research còn sót — mảng mới chưa port (09/10/2026)

> Chỉ primary sources. Phần đã xong (fail-closed batch, limiter/breaker/jitter/Retry-After,
> cache, glossary, floor ink, kinboku, skip-predict, imgsz cap, DeepLX, R5/R7, checkpoint,
> unique output GUI) không nhắc lại, trừ khi nguồn mới đổi kết luận.

## 1. Findings (claim + nguồn)

- V1 upstream đóng băng ở `v1.9.11` (07/2025); dev thật sang org `PDFMathTranslate`
  (nguồn: `api.github.com/.../releases` — commit gần nhất chỉ là star-history noise).
- MỚI chưa port: auto-space CJK↔Latin (kể cả chữ có dấu) ở normal + ultrafast, note
  `[October 3, 2026]` (nguồn: `PDFMathTranslate/.../docs/ADVANCED.md` + `text_spacing.py`);
  `grep pdf2zh/ add_cjk` = 0 hit.
- Ultrafast (pdf-inspector, bỏ ONNX/OCR/subset, pool 16 worker) + MCP server `--mcp` +
  engine mới `argos/grok/groq/deepseek/minimax/openailiked/qwen-mt` (nguồn: `ADVANCED.md`
  `#ultrafast/#cache/#mcp/#services`); local `translator.py` chỉ Google/DeepLX/Handoff.
- Next có `CLITranslator` generic — bọc CLI local bất kỳ, retry timeout + ép utf-8 (PR #311,
  01/2026), khác `HandoffTranslator` nhà này; next cũng auto-rename trùng tên (`330bc38`,
  12/2025) trong khi CLI nhà này (`scripts/translate_pdf.py:413-420`) vẫn báo `E-OUT-05`
  (nguồn: raw `PDFMathTranslate-next/main/pdf2zh_next/high_level.py` + commit log).
- Cancel next ĐỦ chi tiết để port bản gọn: 2 `Pipe(duplex=False)` + `threading.Event` +
  `config.cancel_translation()`, join 2s → terminate → kill, lỗi picklable
  (`TranslationError/BabeldocError/SubprocessError/IPCError/SubprocessCrashError`).
  GUI nhà này worker `threading.Thread` (`gui.py:1032`) không nút Cancel; `pdf2zh/high_level.py`
  đã có sẵn param `cancellation_event` (3 chỗ).
- Watermark BabelDOC ở tầng TYPESET/output, không phải parse: re-typeset trang 1 ở mode
  Watermarked + merge (`generate_first_page_with_watermark`, `merge_watermark_doc`);
  `watermark_output_mode_maps` chỉ là dict str→enum (nguồn: raw `BabelDOC/.../high_level.py`).
- BabelDOC v0.6.x chưa port (nguồn: `api.github.com/repos/funstory-ai/BabelDOC/releases`):
  pixel-budget raster + hạ DPI (v0.6.4); min line-advance Latin/CJK (v0.6.4); chuẩn hoá Type3
  FontMatrix (v0.6.3); guard đệ quy parser + bỏ RapidOCR (v0.6.0/0.6.1);
  `--disable-same-text-fallback` (12/2025); glossary `utf-8-sig` (03/2026); CMap pickle
  allowlist CVE-2026-54071 + sanitize ImageWriter (v0.6.3).
- PyMuPDF pin `1.25.2` → mới `1.28.2` (nguồn: `requirements.txt:14` + `changes.html`):
  `find_tables(use_layout,union,refine)`; `get_textpage_ocr` giờ OCR cả vector graphics
  (1.27.2) — đổi giả định pipeline; save deterministic (#5056); fix segfault subset
  #5049 (củng cố no-subset); leak `get_texttrace` (#5042); `Document.repair()`, `TEXT_CLIP`.
- pikepdf `10.12.0`→`10.17.0` (nguồn: `requirements.txt:13` + `version10.html`): lộ trình
  explicit-mode (v11 warn→v13 bỏ implicit); `set_qpdf_limits()` chống PDF ác ý; bỏ py3.10
  (nhà này py3.12 — không ảnh hưởng).
- onnxruntime `1.20.1`→`1.31.0` (nguồn: `requirements.txt:28` + safety changelog): CPU
  prepacking song song, kernel AVX2 LayerNorm; FP16 MatMul CPU fallback FP32 thầm lặng
  (#32301); siết validation load model; telemetry default 1DS.
- Argos: README ~38 NN KHÔNG có tiếng Việt; cặp `en↔vi` từng bị gỡ vì lỗi Stanza SBD
  tiếng Việt (nguồn: raw `argos-translate/README.md` + `community.libretranslate.com/t/
  offline-vietnamese/846`); model OpenNMT nhỏ, pivot qua English, không giữ `{vN}`.

## 2. Khuyến nghị (effort tăng dần)

1. (XS) Nâng pin 3 lib trong venv test + chạy suite; watch fallback FP16 thầm lặng.
2. (S) Port `add_cjk_latin_spacing`, gate CJK, test offline thuần.
3. (S) CLI trùng stem: học next `330bc38` auto-rename thay vì chỉ `E-OUT-05`.
4. (M) Nút Cancel GUI = `threading.Event` giữa các file + nối `cancellation_event` có sẵn.
5. (M) Pixel-budget raster + min line-advance CJK + `--disable-same-text-fallback`.
6. (L) Watermark ở tầng typeset — chỉ khi có PDF mẫu PNAS; không detect lúc parse.
7. (L) BÁC Argos (gãy vi, mất `{vN}`); ưu tiên pattern `CLITranslator` rồi Ollama localhost.
8. (XL) Ultrafast / MCP `--mcp`: đổi kiến trúc, để riêng, không gộp pipeline precise.
