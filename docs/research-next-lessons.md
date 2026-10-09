# Research: PDFMathTranslate-next & bài học chưa áp dụng (09/10/2026)

## A. Findings (claim + nguồn primary)

1. Next tách frontend/backend: Gradio WebUI (`pdf2zh_next/gui.py` ~4222 dòng) + HTTP API
   (`http_api.py`) + CLI (`main.py`) chung `SettingsModel` và `high_level.do_translate_*`;
   nhà này CustomTkinter gọi trực tiếp `translate_pdf()` trong thread (`app/gui.py:_run`).
2. Queue next không dừng khi 1 file lỗi: `do_translate_file_async` lặp `input_files`,
   `ignore_error=True` chỉ tăng `error_count` (`high_level.py`). Nhà này đã có tương đương
   (`app/gui.py:1037-1068` try/except từng file, `E-OUT-05`→skipped).
3. Progress next là async event stream `{"type": finish/error,...}` từ subprocess qua
   `multiprocessing.Pipe` + `AsyncCallback` (`high_level.py:_translate_in_subprocess`).
   Nhà này chỉ có page-callback `on_progress` + `queue.Queue` — đủ ở粒度 page, thiếu event chuẩn.
4. Mỗi file next chạy subprocess riêng (timeout 30', cancel pipe, terminate→kill fallback),
   lỗi có cấu trúc picklable (`TranslationError/BabeldocError/SubprocessError/IPCError/
   SubprocessCrashError`). Nhà này **không có Cancel** (`gui.py` chỉ `progress.stop()` khi xong;
   `_clear_queue`/`remove_file` bị chặn khi worker sống).
5. Next health-check engine lúc khởi tạo: `translator.translate("Hello", ignore_cache=True)`
   (`translator/utils.py:_create_translator_instance`); nhà này fail muộn từng file.
6. "Marker #885" thực chất là **watermark**: template PNAS bị dịch watermark như text thường
   (`Byaidu/PDFMathTranslate#885`, 30/04/2025; maintainer đóng, chuyển sang BabelDOC).
   Bài học = `WatermarkOutputMode` (no_watermark/both/watermarked) next giao cho BabelDOC
   (`high_level.py`: `watermark_output_mode_maps`). `grep pdf2zh/` nhà này: không có lọc
   watermark/diagonal/large-font nào → **chưa áp dụng**.
7. `Immersive Translate #3874` = dịch PDF lỗi câm + nuốt trọn quota 1000 pages (05/2026).
   Bài học: error explicit + defect manifest + resume để lỗi không tốn quota/re-run.
   Nhà này: `CheckpointManager` (`pdf2zh/checkpoint.py`) **không được import/wire ở đâu**
   (chỉ CHANGELOG nhắc); `--manifest` build dict inline (`translate_pdf.py:518-529`),
   không qua `generate_manifest_report`, không resume theo page.
8. Trùng tên output: **GUI an toàn** — đích = `path.parent/"translated"` (`gui.py:1040`) +
   `{stem}-{lang}.pdf` (`translate_pdf.py:406`); 2 file cùng stem khác thư mục → 2 thư mục
   khác nhau; `collect_pdfs` dedup theo `resolve()` (`gui.py:179`). Lỗ hổng còn lại: **CLI
   `--output-dir` dùng chung + cùng stem** → file sau ghi đè (với `--overwrite`) hoặc báo
   `E-OUT-05`. (Đính chính ref cũ: `Byaidu#292` là hỏi offline-deploy Windows; repo next
   không có PR #292 — số hiệu ghi nhầm, nhưng bài học đặt tên duy nhất vẫn đúng.)
9. Engine mới ngoài DeepLX/Bing: next có 16 impl (`api/.../translator_impl`):
   ollama, xinference, clitranslator, tencentmechinetranslation, qwenmt, siliconflow(+free),
   openai/azure/azureopenai, deepl, anythingllm, dify, claudecode + google/bing; bản v1 có
   thêm `ArgosTranslator` mà next đã bỏ. **Offline hoàn toàn**: Argos (gói local, chỉ cần
   mạng 1 lần tải model), Ollama (`localhost:11434`, `ollama.py`), Xinference (localhost),
   CLITranslator (bọc CLI local bất kỳ). Tencent/Qwen/SiliconFlow/DeepL/OpenAI... đều
   online + cần key. Hợp IP bị chặn: Argos > Ollama/Xinference > handoff (đã có).

## B. Khuyến nghị (effort tăng dần; file chạm + constraint + verify)

- R1 (nhỏ, verify **offline**): đặt tên duy nhất cho CLI output-dir chung
  (`{stem}-{parent-hash}-{lang}.pdf` hoặc từ chối khi trùng). Chạm: `scripts/translate_pdf.py:
  translate_pdf`. Verify: unit test 2 stem trùng, không mạng.
- R2 (nhỏ, verify **offline**): health-check 1 segment "Hello" trước batch (pattern
  `translator/utils.py`). Chạm: `app/gui.py:_start`. Verify: `engine=handoff`, không mạng.
- R3 (vừa, verify **offline**): nút Cancel batch bằng `threading.Event` giữa các file
  (bản đơn giản cùng-process của cancel pipe next). Chạm: `app/gui.py` (`_run/_start`).
  Verify: batch handoff 2 file, cancel giữa chừng, không mạng.
- R4 (vừa, verify **offline**): wire `CheckpointManager` vào flow: save/resume theo page +
  manifest cuối qua `generate_manifest_report` (bài học #3874). Chạm: `pdf2zh/checkpoint.py`
  + `scripts/translate_pdf.py`. Constraint: cần test multi-page. Verify: handoff offline.
- R5 (lớn, **cần mạng 1 lần**): lọc watermark kiểu #885 (bỏ text nền font quá lớn/xoay/
  overlap lớn với body) + tuỳ chọn `watermark_output_mode`. Chạm: `pdf2zh/converter.py`
  (+ `rules.py`). Verify: tải PDF mẫu PNAS công khai 1 lần, sau đó test offline.
- R6 (lớn, **cần mạng/cài đặt**): engine offline mới — port `ArgosTranslator` từ v1 hoặc
  client Ollama/Xinference trỏ localhost. Chạm: `pdf2zh/translator.py` + `ENGINES`.
  Constraint: model nặng, dung lượng bundle. Verify: cần mạng lần đầu (tải model), sau đó
  offline hoàn toàn — phù hợp nhất khi IP bị chặn.
