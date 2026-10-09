# Research: pool toàn-document + parity Android + wall-clock không tăng request

Ngày: 2026-10-09. Nguồn primary: source upstream (Byaidu/PDFMathTranslate, funstory-ai/BabelDOC main) + code repo này. Không sửa code.

## 1. Pool toàn-document upstream (claim + nguồn)

- **F1 — Ultrafast: 1 pool cả document, default 16 workers.** `Byaidu/PDFMathTranslate:pdf2zh/high_level.py::translate_patch`: `if ultrafast and not thread: thread = 16`; pool mở bằng `with ThreadPoolExecutor(max_workers=thread) if ultrafast else nullcontext()` bao quanh vòng lặp trang; `-t` override; normal mode default 4 (`docs/ADVANCED.md#ultrafast`, `#threads`).
- **F2 — Vòng đời pool ultrafast: tạo ở `translate_patch`, đóng khi thoát `with` sau drain + replay.** Gán `device.translation_pool=pool; device.translation_futures=deque()`; `receive_layout` chỉ submit (`translation_futures.extend(pool.submit(worker,s) for s in sstk)`) rồi `return ""`; sau vòng trang: drain bằng `as_completed` + `future.result()`, `translation_pool=None`, rồi replay `for page in pending_pages: interpreter.process_page(page)` (lượt 2 lấy kết quả).
- **F3 — Thứ tự ultrafast = thứ tự submit trong deque (≈ index), `as_completed` chỉ để đợi.** Lượt replay `popleft().result()` theo đúng thứ tự `sstk` từng trang; normal mode dùng `executor.map` (giữ order theo spec stdlib).
- **F4 — Ultrafast KHÔNG gom batch: fan-out trực tiếp từng paragraph.** `ADVANCED.md#ultrafast`: "submits individual paragraph requests"; không có `TranslationBatcher` tương đương. QPS/limiter không đặt ở tầng pool mà phó mặc số worker (16) + retry trong worker.
- **F5 — BabelDOC: `PriorityThreadPoolExecutor` bao toàn doc, ưu tiên đoạn dài.** `babeldoc/.../midend/il_translator.py::ILTranslator.translate`: `with PriorityThreadPoolExecutor(max_workers=self.translation_config.pool_max_workers)`; `process_page` submit từng paragraph với `priority=1048576-paragraph_token_count` (token dài = số nhỏ = chạy trước); thứ tự giữ bằng mutate paragraph in-place (không cần reorder); thoát `with` = `shutdown(wait=True)` chờ `queue.join`. Executor fork tại `babeldoc/utils/priority_thread_pool_executor.py` (PriorityQueue + `submit(..., priority=...)`).
- **F6 — BabelDOC: limiter ở tầng engine, pool size default = QPS.** `pool_max_workers = pool_max_workers if ... else qps` (`translation_config.py`); `_translate_rate_limiter = RateLimiter(5)`, `.wait()` trong `translate()/llm_translate()` mỗi request (`babeldoc/translator/translator.py`). `close_process_pool()` gọi sau `LayoutParser` trong `_do_translate_single` (`babeldoc/format/pdf/high_level.py`) — nhưng `const.py` cho thấy nó no-op trừ khi `enable_process_pool()` (dev/test only), port phải biết để khỏi copy sai.

## 2. Parity Android: fix Python chưa có đối tác (file + hàm lệch)

- **A1 — Floor th/hi/ar:** Python `pdf2zh/rules.py:120-144` (`LANGUAGE_MIN_LINE_HEIGHT`: vi 1.10/th 1.12/hi 1.32/ar 1.91) + `line_height_for_language` (`:91-116`); Android `PdfLayoutPreserver.kt::drawParagraph:1049` floor duy nhất `max(base*0.75,5.5)`, `drawTextWithWrapping:972` floor `base*0.6` — chữ xếp chồng/vi/th/hi/ar dễ đè dòng.
- **A2 — Kinboku/CJK wrap:** Python `can_break_cjk_line` + `_CJK_CLOSERS/_OPENERS` (`rules.py:29-62`); Android `wrapText:1127-1153` split space-only → CJK không dấu cách thành 1 "word" không ngắt được, không luật đầu/cuối dòng.
- **A3 — Glossary:** Python `apply_glossary` exact-match qua `LAYOUTLINGUA_GLOSSARY` (`converter.py:477-488`); Android grep `glossar` = không có.
- **A4 — Batch + breaker/limiter:** Python `TranslationBatcher` 1500 chars/15 segs + fallback lẻ (`batch.py:20-108`), `RateLimiter(5.0)` + breaker 5×429/60s + retry-4 chỉ-429/5xx (`translator.py:31-93`, `converter.py:1144-1154`); Android `translatePdf:107-150` dịch tuần tự từng paragraph, `GoogleTranslateEngine.kt:45-70` gọi thẳng OkHttp không throttle/retry/429-handling, lỗi chỉ đếm `untranslatedCount`.
- **A5 — Preferred rotated headers:** Python `preferred_translation` (`converter.py:440-457`, Designation/Abbreviation/Unit→vi giữ `<sN>`); Android dịch header xoay như đoạn thường.
- **A6 — Placeholder reorder + cache:** Android `FormulaPlaceholder.kt:107-116` so list theo thứ tự (nghiêm hơn Python `Counter` cho reorder, `translator.py:274-291`); cache Android là `ConcurrentHashMap` in-memory, engine mới mỗi run (`PdfLayoutPreserver.kt:80`) nên mất hết sau mỗi file, Python sqlite persistent cap 50k (`cache.py:14-16,101-126`).

## 3. Giảm wall-clock KHÔNG tăng request, KHÔNG service ngoài

- **W1 — Bỏ predict trang preserved/scan (chưa làm, hiệu quả nhất).** `high_level.py:270-274` `get_pixmap`+`model.predict` chạy TRƯỚC phân loại text TOC/INDEX/nomenclature/references (`:399-513`) và chỉ ghi nhận `scanned_pages` mà vẫn predict — đảo thứ tự để trang preserve/blank bỏ inference (0 request, thuần tiết kiệm ONNX/CPU).
- **W2 — Cap `imgsz`.** `:274` `imgsz=full height/32*32`; DocLayNet chuẩn 1024 (prior `research-followup-optimizations.md` F8/R6, arxiv 2410.12628) → cap 1024 giảm pixel inference bậc 2.
- **W3 — Cache layout theo hash trang (đề xuất cũ R6b, chưa làm):** cùng PDF dịch lại bỏ toàn bộ predict.
- **W4 — Path native-text kiểu ultrafast** (bỏ ONNX/OCR cho PDF có text, trang không text → preserve không OCR chui; `ADVANCED.md#ultrafast`, prior R6a).

## 4. Khuyến nghị port (effort tăng dần; file chạm + constraint)

- **R1 (~0.5d) Android preferred headers:** chạm `PdfLayoutPreserver.kt` vòng dịch (`:107-150`); constraint: exact-match + giữ `<sN>` như `converter.py:440-457`.
- **R2 (~0.5d) Android restore cho reorder:** chạm `FormulaPlaceholder.kt:107-126`; constraint: vẫn throw khi mất/cross-nested, giữ test cũ xanh.
- **R3 (~0.5-1d) Android floor per-script:** chạm `drawParagraph:1049` + `drawTextWithWrapping:972-1008`, map theo `TargetLanguage.code`; constraint: chỉ nới floor (th/hi/ar/vi), không đổi layout en hiện tại.
- **R4 (~1d) Android limiter + retry:** chạm `GoogleTranslateEngine.kt:45-70`; constraint: min-interval shared (hiện sequential nên đơn giản), retry chỉ 429/5xx như Python, không retry 400.
- **R5 (~1-2d) Android batch prose:** gom đoạn ngắn marker-free trước khi gọi engine (copy semantics `batch.py`: delimiter + fallback lẻ khi mismatch); constraint: giữ thứ tự đoạn, batch payload vẫn qua limiter R4.
- **R6 (~1-2d) Android kinboku/CJK wrap:** chạm `wrapText:1127-1153`; constraint: chỉ bật khi target CJK, latin giữ nguyên + 1 regression test dấu câu đầu/cuối dòng.
- **R7 (~2-4d) Python pool toàn-document:** chạm `high_level.py::translate_patch` (tạo 1 `ThreadPoolExecutor` cả doc, truyền vào `TranslateConverter` thay `converter.py:1231-1237` tạo/hủy mỗi trang) — pattern F1-F3; batch gom trước theo trang rồi submit payload batch lên pool chung; constraint: không vượt 5 QPS toàn cục (limiter đã shared), batch chỉ prose marker-free ≤1500 chars, giữ thứ tự bằng index/deque.
- **R8 (~1-3d) Wall-clock:** W1+W2 trước, W3 sau; constraint: trang scan/không-text vẫn preserve (không OCR chui), render QA trước/sau.
