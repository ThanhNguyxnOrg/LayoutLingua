# Task 9 Implementation Report: Visual Integrity, Multi-Tier Telemetry & Final Regression

**Base Commit:** `a4e7955`
**Commit:** `95f8907`
**Review Diff:** `.superpowers/sdd/review-a4e7955..95f8907.diff`
**Test Suite Status:** **159/159 PASS** (11.30s runtime)

---

## 1. Tóm tắt Triển khai

Task 9 hoàn thành chặng cuối cùng của Slice 4C.2, khóa toàn bộ các hợp đồng kiểm định tính toàn vẹn hình ảnh, đối soát phân tầng telemetry, cách ly bộ nhớ đệm dịch thuật, và kiểm thử tích hợp toàn trình:

1. **Kiểm tra tính toàn vẹn hình ảnh & cấu trúc PDF (Visual & Structural Integrity):**
   - Xác minh việc thay thế nội dung ô bảng bảo toàn 100% các phần tử vector art và đường viền bảng gốc (`get_drawings()` không bị mất nét vẽ).
   - Kích thước trang và hệ trục tọa độ (`rect.width`, `rect.height`) giữ nguyên vẹn.
   - Nội dung dịch thuật nằm đúng vùng quy định, không tràn đè đường viền cell.

2. **Kiểm chứng Telemetry nhiều tầng (Multi-tier Telemetry Stratification):**
   - **Cấp Block:** `total_blocks` và `replaced_blocks` đếm toàn bộ các khối văn bản (bao gồm cả khối cell).
   - **Cấp Cell:** `total_cells` và `replaced_cells` tách riêng biệt, chỉ đếm các khối có `block_type == "table_cell"`.
   - **Cấp Table:** `rejected_tables` ghi nhận các bảng bị từ chối với `unit_kind="TABLE"`, tách biệt hoàn toàn không làm thổi phồng (inflate) `skipped_blocks` hay `total_cells`.
   - Tuân thủ nguyên tắc **Zero False Success**: Không bao giờ ghi nhận `SUCCESS` khi một trang hoặc một ô rơi vào rollback hoặc fallback.

3. **Cách ly Cache dịch thuật (Cache Isolation):**
   - `compute_cache_key` sử dụng băm SHA-256 trên văn bản chuẩn hóa `segment.masked_text`.
   - Các partitioned cell segments ("Col A", "Col B") có khóa băm độc lập hoàn toàn với khối gộp chưa phân vùng ("Col A Col B"), loại bỏ nguy cơ hit nhầm bản dịch cũ của paragraph gộp.
   - Các cell giống hệt nhau ("Col A" trùng lặp) chia sẻ khóa cache nhất quán, tối ưu hóa chi phí gọi LLM.

4. **Kiểm thử tích hợp Toàn trình (End-to-End Pipeline Integration):**
   - Kiểm thử `test_end_to_end_full_pipeline_multi_page_pdf_integration` thực hiện toàn bộ quy trình: Tài liệu PDF 2 trang chứa text thường, bảng kẻ viền vector 2 ô, và liên kết chéo trang `LINK_GOTO` từ trang 1 trỏ sang trang 2.
   - Kết quả xuất bản:
     - Toàn bộ vector art được bảo toàn nguyên vẹn.
     - Cả 2 ô bảng và văn bản trang 2 được thay thế bằng bản dịch chính xác.
     - Liên kết chéo trang được tái tạo chuẩn xác với `page=1`.
     - Telemetry thống kê chính xác tuyệt đối: 3/3 blocks, 2/2 cells, 0 rejected tables, 0 warnings.

---

## 2. Kết quả Acceptance Tests & Regression

- ** Acceptance Tests mới (4 tests):**
  1. `test_table_level_telemetry_isolation_no_block_inflation`: Bảng bị từ chối ghi nhận `unit_kind='TABLE'`, tăng `rejected_tables` mà không làm sai lệch metric cell.
  2. `test_table_cell_translation_cache_isolation_from_merged_blocks`: Xác minh phân tách cache key giữa ô bảng riêng lẻ và paragraph gộp, chia sẻ cache đúng cho ô trùng lặp.
  3. `test_rebuilt_pdf_table_visual_and_structural_integrity`: Xác minh PDF đầu ra giữ nguyên vector drawings, kích thước trang và vị trí text.
  4. `test_end_to_end_full_pipeline_multi_page_pdf_integration`: Kiểm thử toàn trình PDF 2 trang với bảng biểu, đường viền vector, và liên kết chéo trang.

- **Toàn bộ Test Suite:** **159/159 PASS** (0 failures, 0 errors, 11.30s runtime).
