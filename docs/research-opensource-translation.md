# Nghiên cứu repo dịch PDF mã nguồn mở (primary sources)

> Phạm vi: BabelDOC / pdf2zh upstream / olmOCR / DocLayout-YOLO+ONNX / font / tốc độ. Mỗi claim có nguồn sở hữu nó.

## Tóm tắt (5 gạch)

- Giữ nguyên hợp đồng placeholder `{vN}`/`<bN>`/`<s1..3>` của `pdf2zh/`; BabelDOC dùng `{vN}` + `<style>` nên mọi ý tưởng ghép vào đều phải qua lớp adapter/validate, không đổi tag.
- Khác biệt upstream lớn nhất: cache SQLite WAL giống nhau nhưng BabelDOC có dọn 50k dòng; upstream cắt ngắn segment, bản bundled từ chối segment dài — giữ hành vi bundled.
- VLM (olmOCR) chỉ dành cho trang scan/image-only; không có bbox grounding chính thức, chi phí ~$190/1M trang + GPU, nên coi là fallback ngoại tuyến, không thay parser vector.
- Giảm cost layout: giữ `imgsz` bội số stride 32 + `scale_boxes` ngược về tọa độ gốc, giữ cache `.optimized`, CPU mặc định; chỉ thêm knob `intra_op_num_threads`.
- Font: CJK→SourceHanSerif, Cyrillic/Arabic/Hebrew/Vietnamese→Noto, giữ `no-subset` + kiểm `has_glyph` để tránh tofu/U+0000 trên Identity-H.

## 1. BabelDOC (funstory-ai/BabelDOC)

- IR tách layout/text: pipeline `Parse PDF → Intermediate Representation → Translate → Typeset → Fonts → Generate` trong `babeldoc/format/pdf/high_level.py` (`TRANSLATE_STAGES`, `XMLConverter` ghi `*.debug.json`). Nguồn: https://github.com/funstory-ai/BabelDOC + `raw/.../babeldoc/format/pdf/high_level.py`.
- Placeholder KHÁC bản bundled: `translator.py` `get_formular_placeholder→{vN}` + regex, rich-text `→<style id>/</style>`; prompt `il_translator.py` (`PROMPT_TEMPLATE`) cấm thêm/bớt/sắp xếp lại tag, cấm dịch trong `<code>`, giữ `{v1}/{name}/%s/%d/[[...]]`. Nguồn: `raw/.../babeldoc/translator/translator.py`, `raw/.../format/pdf/document_il/midend/il_translator.py`.
- Stitching xuyên trang CHƯA xong: README Roadmap ghi `Add cross-page/cross-column paragraph support`; hiện có `DocumentTranslateTracker.cross_page/cross_column` + `paragraph_finder.py:merge_alternating_line_number_paragraphs` (chỉ merge khi trùng `layout_id`+`xobj_id`, chữ số ASCII). Nguồn: https://github.com/funstory-ai/BabelDOC (README Roadmap) + `raw/.../midend/paragraph_finder.py`.
- CJK typography: `typesetting.py` `is_cjk_char` (U+3000–303F, Hiragana, Katakana, Hangul, CJK U+4E00–9FFF...), `is_hung_punctuation`/`is_cannot_appear_in_line_end` (kinboku), `can_break_line` (`LINE_BREAK_REGEX`), `line_skip=1.50` nếu `is_cjk` else `1.3`. Nguồn: `raw/.../document_il/midend/typesetting.py`.
- Glossary: CLI `--glossary-files` CSV `source,target,tgt_lng` (khớp `lang-out` mới dùng) + `AutomaticTermExtractor` (LLM JSON `[{"src","tgt"}`, gom ≤600 token/12 đoạn, `PriorityThreadPoolExecutor`, đối chiếu glossary người dùng). Nguồn: README (Glossary Options) + `raw/.../midend/automatic_term_extractor.py`.

## 2. pdf2zh upstream (PDFMathTranslate/PDFMathTranslate)

- Formula regions: `converter.py:vflag` (font `CM[^R]|MS.M|...Mono|Code|Ital|Sym|Math`, unicode `Lm/Mn/Sk/Sm/Zl/Zp/Zs`, Hy Lạp U+0370–03FF) + vùng layout `cls==0` + `{vN}`; bundled mở rộng họ Consolas/Menlo/Fira Code + token xếp chồng + validate. Nguồn: `raw/.../PDFMathTranslate/main/pdf2zh/converter.py`.
- Table matching: upstream v1 chỉ mask box layout (`translate_patch`, `box[y0:y1,x0:x1]`); nhánh BabelDOC ghi `--translate-table-text (experimental, default False)`; cell-grid `find_tables` + ngưỡng 50% là phần mở rộng của bản bundled. Nguồn: `raw/.../main/pdf2zh/high_level.py` + README (`--translate-table-text`) + `docs/ADVANCED.md#ultrafast`.
- Cache SQLite: cả hai dùng peewee `cache.v1.db`, `UNIQUE(engine,params,original) ON CONFLICT REPLACE`, `journal_mode=wal,busy_timeout=1000`; BabelDOC thêm `MAX_CACHE_ROWS=50_000`, `CLEAN_PROBABILITY=0.001`, khóa cleanup, bỏ qua khi `database is locked`. Nguồn: `raw/.../BabelDOC/.../translator/cache.py` + `raw/.../PDFMathTranslate/main/pdf2zh/cache.py`.
- Batching: upstream `ThreadPoolExecutor(max_workers=thread)` + `worker(s)` cho từng `sstk`, `@retry(wait_fixed(1))`; ultrafast pool 16 worker toàn văn bản + `as_completed`, `[ultrafast perf]` log; BabelDOC `PriorityThreadPoolExecutor(pool_max_workers≈QPS)` + `RateLimiter` leaky-bucket (mặc định 5 QPS, `time.monotonic`). Nguồn: `converter.py`, `high_level.py:translate_patch`, `docs/ADVANCED.md`, `BabelDOC translator.py:RateLimiter`.

## 3. olmOCR (allenai/olmocr) — khi nào + cost bbox

- Chỉ cho scan/image-only (core bundled từ chối OCR, báo image-only): olmOCR là VLM 7B (v1 `Qwen2-VL-7B`, v2 `Qwen2.5-VL-7B`) finetune ~250k trang, ra Markdown+LaTeX đúng thứ tự đọc, chịu đa cột/chữ tay. Nguồn: https://github.com/allenai/olmocr (README) + https://allenai.org/blog/olmocr (`document anchoring` đưa text/metadata vào prompt).
- Cost: ~$190/1M trang (~1/32 GPT-4o batch), README ghi `<$200/1M`; cần GPU ≥12GB VRAM + ~30GB đĩa; remote qua `--server/--model/--workers/--max_concurrent_requests` (vLLM/OpenAI-compatible). Nguồn: blog olmOCR + README (Installation/Usage/Verified Providers).
- Không có bbox grounding chính thức: output là Markdown/Dolma; `issues/30` hẹn bbox ở v0.5; chi phí inpainting = render ảnh trang + VLM + LaMa xóa chữ + dàn lại chữ, không có đường bbox→PDF của hãng. Nguồn: https://github.com/allenai/olmocr/issues/30 + README + blog.

## 4. DocLayout-YOLO + onnxruntime (đúng tọa độ, rẻ)

- `imgsz` phải bội số stride: SDK `model.predict(img, imgsz=1024, conf=0.2)`; BabelDOC cố định `_FIXED_IMGSZ=1024` (CoreML static) `resize_and_pad_image` rồi `scale_boxes((new_h,new_w)→orig)+geometry.px_len_to_pt`; bundled dùng `imgsz=int(pix.height/32)*32` theo trang. Nguồn: https://github.com/opendatalab/DocLayout-YOLO (README Quick Start) + `BabelDOC .../docvision/doclayout.py:predict` + `pdf2zh/doclayout.py:53-67,204-221`.
- Providers: `onnxruntime.get_available_providers()`; BabelDOC chỉ giữ CPU (bỏ dml/cuda, Darwin dùng CoreML static); bundled `_BACKEND_PROVIDERS={cpu,cuda,dml}` + auto. Nguồn: `BabelDOC doclayout.py` + `pdf2zh/doclayout.py:93-117`.
- Threads + cache: mặc định `intra_op_num_threads=0` (=số core vật lý), `ORT_ENABLE_ALL`, `ORT_SEQUENTIAL` (docs Thread management); offline lưu graph qua `optimized_model_filepath` (docs Graph Optimizations); bundled ghi `model.onnx.optimized`, bỏ cache khi gặp CoreML/TensorRT. Nguồn: https://onnxruntime.ai/docs/performance/tune-performance/threading.html + .../model-optimizations/graph-optimizations.html + `pdf2zh/doclayout.py:93-127`.
- Muốn đúng box khi downscale: resize giữ tỉ lệ + pad (114,114,114) + `gain=min(...)`, trừ pad rồi chia gain — không đổi logic này khi giảm `imgsz`. Nguồn: `doclayout.py:scale_boxes:178-202`.

## 5. Font đa ngôn ngữ (tránh tofu/U+0000)

- Noto phủ >1000 ngôn ngữ/150 hệ chữ (fonts.google.com/noto); Noto Sans CJK biến thể phủ CJK; `pymupdf-fonts` FiraGO phủ Latin+Cyrillic+Greek+Thai+Arabic+Hebrew+Devanagari nhưng KHÔNG CJK. Nguồn: https://fonts.google.com/noto + https://github.com/notofonts + https://pymupdf.readthedocs.io/en/latest/font.html.
- Source Han Serif là Pan-CJK (EN/JA/KO/ZH-CN/ZH-TW, 65,535 glyph), không gánh Việt/Arabic/Hebrew — phải fallback Noto. Nguồn: https://github.com/adobe-fonts/source-han-serif (README) + https://source.typekit.com/source-han-serif.
- Routing upstream `high_level.py:download_remote_fonts`: `noto_list=[am,ar,bn,bg,el,gu,iw,hi,kn,ml,mr,ru,sr,ta,te,th,ur,uk...]→GoNotoKurrent`, `zh/ja/ko→SourceHanSerifCN/TW/JP/KR`; bundled thêm floor `vi 1.10em` + Times New Roman trên Windows. Nguồn: `raw/.../main/pdf2zh/high_level.py` + `references/preservation-rules.md`.
- Subset vs raw ID: `Document.subset_fonts()` chỉ giữ glyph đã dùng (docs Document); content stream ghi glyph-ID thô trên Identity-H nên subset/renumber sẽ trỏ sai — bundled cấm subset mọi cỡ, tài liệu lớn (≥200p/50MB) dùng `garbage=1`, không object-stream. Nguồn: https://pymupdf.readthedocs.io/en/latest/document.html (`subset_fonts`) + `agent-knowledge/pdf-engine.md:51-53,83-89`.
- Tránh tofu: `Font.has_glyph(ord(c))` trả 0 = thiếu glyph (docs Font), `valid_codepoints()` liệt kê điểm mã có cmap; ký tự output-font không vẽ được thì giữ glyph gốc, không phát U+0000. Nguồn: https://pymupdf.readthedocs.io/en/latest/font.html (`has_glyph`, `valid_codepoints`).

## 6. Tốc độ dịch (pattern đã chứng minh)

- Batching: BabelDOC gom đoạn theo token (`1048576-token` priority), trích thuật ngữ theo batch; ultrafast 1 pool 16 worker + `-t` ghi đè. Nguồn: `il_translator.py:process_page`, `automatic_term_extractor.py`, `docs/ADVANCED.md#ultrafast`.
- Cache: SQLite WAL như mục 2; `ultrafast --ignore-cache` bỏ cả đọc+ghi, mode thường giữ hành vi cũ. Nguồn: `docs/ADVANCED.md#cache`, `#ultrafast`.
- Threadpool reuse: `pool_max_workers` mặc định theo QPS, riêng `term_pool_max_workers`; đóng process-pool sau layout (`close_process_pool`). Nguồn: README (Translation Service Options) + `BabelDOC high_level.py`.
- Retry/backoff: `tenacity wait_exponential(multiplier=1,min=1,max=15) stop_after_attempt(100)` cho `openai.RateLimitError` (cả BabelDOC lẫn upstream OpenAI); worker thường `@retry(wait_fixed(1))`. Nguồn: `BabelDOC translator.py:do_translate/do_llm_translate` + `upstream translator.py:OpenAITranslator`.
- Rate-limit Google: endpoint `translate.google.com/m`, upstream cắt `text[:5000]` (mất đuôi âm thầm), Bing cắt `text[:1000]`; bundled ném `SegmentTooLongError` để giữ nguồn + báo lý do. Dùng chung `requests.Session`, LLM `temperature=0` để khỏi xé tag công thức. Nguồn: `upstream translator.py:GoogleTranslator/BingTranslator`, `pdf2zh/translator.py:158-181`, `converter.py:options temperature`.

## Khuyến nghị ghép được (nhỏ nhất, preservation-safe)

1. Placeholder: giữ `{vN}`↔`<bN></bN>` + `<s1..3>` hiện tại; chỉ port thêm bước loại token placeholder ảo kiểu BabelDOC (`remove_placeholder` + đếm cặp cân bằng, cho reorder cả cặp), chạy SAU dịch như validator, không đổi tên tag.
2. Glossary: dùng `HandoffTranslator` + CSV `src,dst` đã validate placeholder (đã có `load_segment_table`); auto-extract để offline/tùy chọn, không nhét glossary vào path Google mặc định.
3. Stitching: chỉ nối câu gãy khi cùng `layout_id`+`xobj_id`, ngoài vùng figure/table/isolated-formula, và ghi lại số đoạn đã nối; không port stitching xuyên trang toàn văn bản.
4. CJK: port `is_cjk_char` + cấm dấu câu đầu/cuối dòng + `add_cjk_latin_spacing` (upstream `text_spacing.py`); giữ floor `vi 1.10em` và `line_skip` hiện tại cho tiếng Việt.
5. Inference: giữ snap `imgsz` theo stride 32 + cache `.optimized` + CPU mặc định; chỉ thêm biến môi trường `intra_op_num_threads`, kèm test round-trip `scale_boxes`.
6. Font/tốc độ: giữ `no-subset` + guard `has_glyph`; giữ cache WAL + pool hiện tại; thêm leaky-bucket QPS + `wait_exponential` cho lỗi 429/5xx của Google (retry GET, không truncate).
