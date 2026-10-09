# Research: 429 / IP-block trên `translate.google.com/m`

Context: IP này 429 + redirect `/sorry/index` ngay từ request lạnh đầu tiên;
throttle 0.2s (~5 QPS) + retry 4 lần exp-max-60s vẫn fail 100% → IP đã bị
flag sẵn, không phải burst nhất thời. Không sửa code trong task này.

## Findings (claim + nguồn)

1. `GoogleTranslator` gốc (Byaidu) KHÔNG xử lý 429: `do_translate` chỉ
`text[:5000]`, `raise_for_status()`, không retry/backoff/jitter/Retry-After.
(`raw.../Byaidu/PDFMathTranslate/main/pdf2zh/translator.py`, class
`GoogleTranslator`; `BingTranslator` tương tự, giới hạn `text[:1000]`.)
2. `PDFMathTranslate-next` cũng không có logic 429 riêng: `google.py` retry
mọi `Exception` 5 lần `wait_exponential(min=1,max=15)`, không đọc
`Retry-After`, không giảm concurrency, không đổi endpoint.
(`pdf2zh_next/translator/translator_impl/google.py`; `bing.py` giống hệt,
chỉ khác endpoint `bing.com/translator` + `text[:1000]`.)
3. Rate-limit chuẩn của họ là leaky-bucket QPS + tenacity cho API **có key**:
BabelDOC `RateLimiter` mặc định 5 QPS (`babeldoc/translator/translator.py:72`);
`OpenAI*: RateLimitError → 100 lần, 1–15s; `SiliconFlowFree`: HTTPError 3 lần
30–60s + RateLimit 100 lần 4–120s, QPS động qua `/config → set_max_qps`
(`siliconflowfree.py:59-82,182-193`). Không parse `Retry-After` ở đâu cả.
4. `/m` là endpoint web không key (unofficial scraping), KHÔNG có quota công
khai; 429/`/sorry/index` là chống-bot theo IP, vi phạm ToS.
Cộng đồng: block sau ~40–50 request dồn (`ssut/py-googletrans#76`), hoặc
400–800 bulk (`#117`); Google chỉ ghi "expire shortly after those requests
stop"; báo cáo thực tế ~24h (`#117`: "disappeared in 24 hours").
Request lạnh đầu tiên đã 429 = IP/NAT/VPN dùng chung đã bị flag trước.
5. Quota chính thức (trả phí, có key): Cloud Translation 6M ký tự/phút,
tối đa 30k/request (khuyến nghị 5k), 500k ký tự/tháng miễn phí rồi ~$20/M
(`docs.cloud.google.com/translate/quotas`, trang pricing); DeepL API Free
500k ký tự/tháng, cần key (`support.deepl.com`, `developers.deepl.com`).
6. Batching: `/m` chỉ nhận 1 tham số `q`, giới hạn ~5000 ký tự
(upstream cắt `text[:5000]`, im lặng mất đuôi); endpoint batch
(`batchexecute`) nhận mảng, ít bị limit hơn nhưng kém chính xác
(`google-translate-api-x` README: `forceBatch`, max 5000 chars/call).
Delimiter phải tránh `<bN>`/`{vN}` (placeholder công thức của repo);
mẫu an toàn đã có upstream: tách theo newline giữ delimiter ≤5000
(`TencentTranslator.do_translate`).
7. Khi IP đã block: retry/backoff KHÔNG gỡ block; chỉ có dừng traffic + đợi,
đổi egress IP, giải CAPTCHA `google.com/sorry`, hoặc bỏ endpoint free.
Proxy thường vô dụng trên IP dùng chung đã nhiễm (`py-googletrans#76`,
`gTTS#259`, `support.google.com/translate/thread/97045092`).

## Khuyến nghị (effort tăng dần, preservation-safe)

1. Dừng bắn request, tận dụng cache sẵn có; probe 1 request sau cooldown —
xác nhận block còn hay hết, 0 rủi ro.
2. Giảm QPS ≤1 + 1 worker + jitter + tôn trọng `Retry-After` (thay đổi nhỏ,
không chạm placeholder/bố cục).
3. Gom nhiều segment/1 request ≤5000 ký tự, tách theo newline, delimiter
không bao giờ xuất hiện trong văn bản (tránh `<bN>`); giảm tổng request
~10–50x, vẫn giữ nguyên check placeholder.
4. Fail-soft: 429 cạn retry → giữ nguyên source + ghi miss để chạy lại
(`HandoffTranslator` + `segments_out` đã có sẵn) thay vì crash tài liệu.
5. Thoát endpoint free: Bing free (trần 1000 ký tự, thêm vòng `find_sid`),
hoặc API có key (Cloud/DeepL/Azure), hoặc LLM local/Handoff — tốn key/
setup nhất nhưng là đường duy nhất ổn định khi IP đã bị liệt.
