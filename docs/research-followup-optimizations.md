# Research follow-up: những gì còn lại đáng học/tối ưu
Đã xong (không lặp lại): box mask int32, retry 4 chỉ-429/5xx, RateLimiter 5 QPS,
circuit-breaker 5×429/60s, TranslationBatcher, cache cleanup 50k, glossary ngoài,
floor ink th/hi/ar/he/bn/te/ta/ru/el/CJK.
## Findings (claim + nguồn primary)
- **F1 — Kinboku BabelDOC = 3 predicate + 1 regex** (`BabelDOC/.../midend/typesetting.py`):
  `calc_can_break_line`: `LINE_BREAK_REGEX.match(ch)`→False (không ngắt sau Latin/số/Cyrillic/
  Greek/Thai/Tamil/Telugu/`-`/`·`), còn lại True; `is_cjk_char`: punct `（）【】《》〔〕〈〉〖〗「」『』、。：？！，`
  + range `3000-303f,3040-30ff,ac00-d7af,4e00-9fff,2e80-2eff...` + fallback `unicodedata.name`
  chứa `CJK UNIFIED IDEOGRAPH`/`FULLWIDTH`; `is_hung_punctuation` (burasagari) và
  `is_cannot_appear_in_line_end` (gyomatsu `“‘「『([{（〔〈《〖〘〚`).
- **F2 — Điểm ngắt từ = `_get_width_before_next_break_point`** (cùng file): unit đầu
  `can_break_line`→width 0, ngược lại cộng dồn `unit.width` tới unit ngắt được đầu tiên ×`scale`.
  Đây là "word-wrap cho CJK" tối thiểu để port.
- **F3 — Gate CJK = substring `lang_out.upper()`** (`Typesetting.__init__`):
  `is_cjk = ZH|JA|JP|KR|CN|HK|TW`; `line_skip=1.50` nếu CJK else `1.3`; scale 1.0→0.1
  (bước 0.05 khi >0.6, 0.1 khi ≤0.6), mở rộng box rồi mới giảm scale.
- **F4 — `wait_exponential` KHÔNG có jitter** (`jd/tenacity/.../wait.py` docstring:
  "intervals are fixed... NOT suitable for contention... Use `wait_random_exponential`";
  `wait_random_exponential`=Full Jitter (AWS blog); `wait_exponential_jitter`=Google Cloud
  (`min(initial*2^n+uniform(0,jitter),max)`); cho phép `wait_fixed+wait_random`):
  `Retry-After` phải tự viết `wait` đọc header (mẫu `alexwlchan/handling-http-429-with-tenacity`).
- **F5 — Upstream retry mạnh tay hơn ta** (`BabelDOC/.../translator/translator.py`,
  `PDFMathTranslate/pdf2zh/translator.py`): OpenAI `stop_after_attempt(100)`,
  `wait_exponential(1,1,15)` chỉ cho `RateLimitError`; `temperature=0  # 随机采样可能会打断公式标记`.
- **F6 — Concurrency upstream: pool toàn-document 16 vs 4** (`ADVANCED.md#ultrafast`):
  "shared whole-document paragraph worker pool with 16 workers... `-t` overrides...
  normal mode default 4"; ultrafast bỏ ONNX+OCR+subsetting (output lớn hơn), chỉ CLI
  fast-mode; GUI batch đa-file+zip ở `PDFMathTranslate-next PR #292` (cẩn thận trùng tên file).
- **F7 — Prompt LLM upstream dùng được nguyên văn** (2 file translator.py + `ADVANCED.md#prompt`):
  system `"You are a professional, authentic machine translation engine."`, user `";; Treat next
  line as plain text... into {lang_out}, output ONLY... return original if unnecessary"`;
  fast-mode thêm `Keep {v*} unchanged` + `${lang_in/lang_out/text}`; `max_tokens=2048`,
  `httpx timeout=600`, lọc `<think>`, QPS mặc định 4 (`--qps`/`RateLimiter(5)`).
- **F8 — Layout rẻ nhất = bỏ inference, không phải tuning** (`arxiv 2410.12628`: 85.5 FPS/A100,
  mAP 70.3/79.7/78.8; `imgsz` 1024, 1120 DocLayNet, 1600 D4LA; stride 32):
  ultrafast chứng minh bỏ ONNX/OpenCV cho PDF có native-text; Surya "cần GPU pro, extremely
  slow" (`BabelDOC#89`).
- **F9 — `--retain-gids` khả thi nhưng phình CJK** (`fonttools docs` + `fonttools#3516`):
  60k glyph trống ≈ +60KB endchar + mảng offset 3-byte; `hmtx/vmtx/loca/CFF` index theo GID
  nên chỉ trim đuôi được. Liên quan `should_subset_fonts()=False`: `raw_string()` ghi
  `has_glyph(ord(c))` làm CID nên renumber là sai.
- **F10 — Engine thứ 3 từ bảng upstream** (`ADVANCED.md#services`): `DeepLX` free
  (`DEEPLX_ENDPOINT`); `Bing` keyless (1000 chars, scrape `ig/iid/key/token`); `Tencent`
  keyed (tự split 5000 chars); `Argos` offline (tự download package theo cặp lang).
  BabelDOC hiện chỉ OpenAI-compatible (README TIP).
## Khuyến nghị (effort tăng dần; không sửa code ở đây)
- **R1 — Jitter + `Retry-After` (~0.5 ngày).** Chạm `pdf2zh/converter.py` (`request_translation`):
  `wait_exponential`→`wait_exponential_jitter` hoặc `wait_fixed+wait_random` + `wait` đọc
  `Retry-After` (giây/HTTP-date), fallback exponential; giữ retry-4 + chỉ-429/5xx + breaker.
  Preservation: fail-closed giữ source; không retry 400/placeholder.
- **R2 — Củng cố HandoffTranslator local (~0.5–1 ngày).** Chạm `pdf2zh/translator.py` + doc caller:
  `temperature=0`, system prompt F7, giữ tag `<bN></bN>`/`<sN>`, context ≥ đoạn dài nhất +
  delimiter, lọc `<think>`. Preservation: `restore_formula_placeholders` là gate cuối; miss không vào cache.
- **R3 — Port kinboku read-only sau restore, gate CJK (~1–2 ngày).** Chạm `pdf2zh/typesetting.py`
  (+`converter.py` chỗ wrap): `can_break_line` (copy regex), `is_cjk_char`, 2 set burasagari/
  gyomatsu, wrap theo cụm F2; chỉ bật `lang_out` CJK (F3), latin giữ nguyên + 1 regression
  test CJK dấu câu đầu/cuối dòng. Preservation: read-only sau restore, không đụng `{vN}`; source bất biến.
- **R4 — Engine thứ 3: DeepLX → Bing → (Tencent|Argos) (~1–3 ngày/engine).**
  Chạm `pdf2zh/translator.py` (`ENGINES`): DeepLX free trước, Bing keyless sau (1000 chars, sid dễ vỡ),
  Tencent/Argos cuối (key/package nặng); mỗi engine có `MAXIMUM_SEGMENT_CHARACTERS` riêng, qua
  RateLimiter/breaker chung. Preservation: mọi output qua `validate_formula_placeholders`/`validate_style_tags`.
- **R5 — Concurrency không tăng 429 (~2–4 ngày).** Chạm `pdf2zh/converter.py`, `pdf2zh/high_level.py`
  (+GUI queue): pool toàn-document, `-t` override, batch prose ngắn trước rồi fan-out đoạn lẻ;
  GUI đa-file xếp hàng qua 1 limiter + tên file duy nhất (bài học PR #292).
  Preservation: giữ thứ tự đoạn; không vượt QPS toàn cục.
- **R6 — Layout rẻ hơn, làm sau R1–R5 (~3–5 ngày).** Chạm `pdf2zh/doclayout.py`, `pdf2zh/high_level.py`:
  (a) path native-text kiểu ultrafast (bỏ ONNX/OCR, giữ safeguard font/formula);
  (b) giảm `imgsz` 1024→768/640 + cache layout theo hash trang; (c) Surya/layoutreader cuối cùng
  (tốn GPU, chậm — F8). Preservation: trang không native-text → preserve, không OCR chui; render QA trước/sau.
- **R7 — Font CJK: giữ no-subset; thí điểm `retain-gids` (~3–5 ngày, dễ phình).**
  Chạm `pdf2zh/high_level.py` (`should_subset_fonts`, `download_remote_fonts` SourceHan
  CN/TW/JP/KR + fallback msyh/msjh/meiryo/malgun đã có): mặc định `subset=False` (GID raw — F9);
  thí điểm chỉ CJK + đo size trước/sau cùng 1 PDF. Preservation: không renumber GID khi
  `raw_string()` còn ghi CID trực tiếp; font bundle không commit.
