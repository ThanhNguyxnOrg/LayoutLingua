# Holistic Architectural & Safety Review: Slice 4C.2 (Table Cell Isolation & Grid Protection)

**Scope of Review:** Toàn bộ 9 Tasks của Slice 4C.2 (`dc342f0..95f8907`)
**Review Diff:** `git diff dc342f0..95f8907`
**Date:** 2026-10-15
**Verdict:** **ALL 9 TASKS PASS — FULL SLICE INTEGRITY VERIFIED**

---

## 1. Mục tiêu và Bối cảnh Đánh giá Tổng thể
Sau khi hoàn thành tuần tự 9 task theo quy trình Superpowers SDD, báo cáo này thực hiện một lượt rà soát xuyên suốt (cross-task holistic review) nhằm phát hiện các mâu thuẫn giao diện tiềm ẩn, rò rỉ ranh giới (boundary leakage), hoặc các giả định không tương thích giữa các module độc lập.

---

## 2. Kiểm chứng các Invariants Xuyên suốt (Cross-Task Invariants)

### Invariant 1: Phân tách Kiến trúc Sạch (Clean Architectural Decoupling)
- **Quy tắc:** Module Core (`layoutlingua.core.table_models`, `tables.py`) tuyệt đối không phụ thuộc hoặc import bất kỳ thành phần nào từ Typesetting (`layoutlingua.typesetting.*`).
- **Thực tế:**
  - `table_models.py` thuần túy định nghĩa các cấu trúc hình học (`BorderLine`, `CellGeometry`, `TableGrid`) bằng thư viện chuẩn Python (dataclasses, typing).
  - `tables.py` chỉ phụ thuộc vào `pymupdf`, `ir.py`, và `table_models.py`.
  - Typesetting (`engine.py`, `protection.py`, `accumulator.py`) tiêu thụ domain model từ Core một chiều.
  - **Kết luận:** **PASS — Không có vòng phụ thuộc (zero circular imports).**

### Invariant 2: Hợp đồng Chỉ số Trang (Page Indexing Contract — Ruling 1)
- **Quy tắc:** `page_number` là 1-indexed (dùng cho telemetry, PageIR, báo cáo người dùng), `source_page_index` là 0-indexed (dùng cho PyMuPDF `doc[p]`, `insert_pdf`). Bất biến: `page_number == source_page_index + 1`.
- **Thực tế:**
  - `PageTransactionResult(page_number, source_page_index, ...)` tuân thủ nghiêm ngặt quy tắc này.
  - Vòng lặp `DocumentAccumulator.commit_page()` và `restore_links()` luôn ánh xạ chính xác `p` (0-indexed) sang `p + 1` khi ghi log warning và telemetry.
  - **Kết luận:** **PASS — Không có lỗi lệch chỉ số off-by-one.**

### Invariant 3: Cổng Cam kết Telemetry & Zero False Success (Ruling 2)
- **Quy tắc:** Báo cáo `FittingReport` chỉ được ghi nhận các block/cell trạng thái `SUCCESS` SAU KHI trang đã được commit thành công vào `output_doc`. Nếu commit lỗi hoặc trang rollback, toàn bộ block phải chuyển thành `TRANSACTION_FALLBACK` hoặc fallback tương ứng.
- **Thực tế:**
  - `TypesetEngine.typeset()` chỉ gọi `_commit_page_telemetry()` khi `committed_cleanly is True`.
  - Khối commit failure gọi `_commit_emergency_fallback_telemetry()`, ghi nhận `replaced_blocks = 0`, bảo đảm không bao giờ báo cáo thành công giả cho trang đã bị hủy bỏ.
  - **Kết luận:** **PASS — Tuyệt đối không có false success.**

### Invariant 4: Bảo toàn Glyph Multiset ($C_{\text{out}} == C_{\text{in}}$)
- **Quy tắc:** Quá trình phân chia text qua đường viền cell (`TableCellPartitioner`) không được làm rơi, trùng lặp hoặc xáo trộn bất kỳ ký tự nào; token công thức toán học `⟦LL_FORMULA_XXXX⟧` không bao giờ bị cắt đôi.
- **Thực tế:**
  - Sử dụng định danh bất biến `f"p{p}_b{b}_s{s}_c{c}"` cho từng ký tự.
  - Mọi vi phạm (kể cả tổng số ký tự bằng nhau nhưng ID bị lệch) đều kích hoạt fail-closed, chuyển bảng thành `table_rejected` và giữ nguyên văn bản gốc.
  - **Kết luận:** **PASS — An toàn dữ liệu tuyệt đối.**

### Invariant 5: Bảo vệ Đường nét Vector & Không gian Hình ảnh (Line Art & Vector Protection)
- **Quy tắc:** Redaction chỉ loại bỏ văn bản (`PDF_REDACT_TEXT_REMOVE`), giữ nguyên vector graphics và line art (`PDF_REDACT_LINE_ART_NONE`). Stroke-aware insets lùi văn bản khỏi mép viền bảng ít nhất $p_{\text{side}} = \max(1.0, w_{\text{border}} / 2 + 0.5)\text{ pt}$.
- **Thực tế:**
  - Cả unit test và end-to-end integration test (`test_rebuilt_pdf_table_visual_and_structural_integrity`) đều xác nhận `get_drawings()` giữ nguyên 100% vector shapes và nét viền bảng.
  - Văn bản dịch không bao giờ đè lên stroke viền bảng.
  - **Kết luận:** **PASS — Không tổn hại visual line art.**

### Invariant 6: Khôi phục Liên kết Toàn diện Sau Ghép Trang (Post-Assembly Restoration)
- **Quy tắc:** Không phụ thuộc `insert_pdf()` từng trang để giữ link chéo trang. Giải quyết `LINK_GOTO`, `LINK_URI`, và dual `LINK_NAMED` (phân biệt predefined actions vs catalog named destinations), chuyển đổi tọa độ qua `transformation_matrix` và `rotation_matrix`.
- **Thực tế:**
  - Hoạt động sau khi toàn bộ $N$ trang đã được commit với `links=False`.
  - Hỗ trợ chuẩn xác các trang thường, trang offset CropBox, và trang xoay 90°/270°.
  - Destination không tồn tại được bỏ qua an toàn, ghi warning, không tạo dead link.
  - **Kết luận:** **PASS — Đầy đủ và chuẩn xác.**

---

## 3. Tổng Hợp Số Liệu Kiểm Thử Toàn Bộ Slice 4C.2

```text
Ran 159 tests in 11.301s

OK
```

- **Tổng số acceptance tests bổ sung trong Slice 4C.2:** 50 tests (từ Task 1 đến Task 9).
- **Tổng số tests toàn hệ thống:** 159 tests PASS (0 failures, 0 errors, 0 skipped).
- **Thời gian chạy:** ~11.3 giây trên môi trường local.

---

## 4. Đánh Giá Trạng Thái Dự Án & Định Hướng Tiếp Theo

### Những gì ĐÃ đạt được:
1. Core PDF engine của LayoutLingua hiện đã có khả năng xử lý bảng biểu chuyên sâu ở cấp độ cell độc lập.
2. Hệ thống giao dịch trang đơn (single-page transactional staging & rollback) với ngân sách thử lại (`MAX_PAGE_ATTEMPTS = 3`) ngăn ngừa hoàn toàn các khoảng trắng (white voids) hoặc lỗi dở dang.
3. Bộ tích lũy tài liệu đa trang bảo lưu trọn vẹn metadata, TOC, page labels, embedded files, form widgets, và các liên kết tương tác.
4. Telemetry 3 tầng (Block, Cell, Table) hoạt động minh bạch, phục vụ chẩn đoán chính xác.

### Những gì CHƯA thực hiện (Cần lưu ý trước khi phát hành):
1. **Giao diện Người dùng (Desktop GUI / Web UI):** Chưa triển khai.
2. **Font Bundling & Routing thực tế:** Hiện đang dùng fallback hệ thống và Base14/DejaVu; cần kiểm tra tích hợp với các bộ font mở rộng (CJK, tiếng Việt dấu phức tạp, RTL).
3. **Thử nghiệm trên các tập tài liệu lớn ngoài đời thực (Real-world Stress Testing):** Cần chạy thử nghiệm trên các báo cáo tài chính phức tạp, tài liệu nghiên cứu khoa học nhiều trang có bảng lồng nhau.
4. **Đóng gói phát hành (Packaging / Distribution):** Chưa build installer hay APK/AppImage.

---

## 5. Kết Luận
Slice 4C.2 đã hoàn thành 100% mục tiêu kỹ thuật theo kế hoạch đã cam kết, đảm bảo an toàn tuyệt đối cho tầng Core PDF trước khi bước sang các giai đoạn tiếp theo của dự án.
