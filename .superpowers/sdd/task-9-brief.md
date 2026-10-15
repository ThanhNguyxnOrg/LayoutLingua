# Task 9 Brief: Visual Integrity, Multi-Tier Telemetry & Final Regression

**Base Commit:** `a4e7955`
**Target Commit:** `feat(tables): complete telemetry stratification, cache isolation, and end-to-end PDF integrity for Slice 4C.2`

## 1. Mục tiêu và Phạm vi
Task 9 là chặng kết thúc của Slice 4C.2 (Table Cell Isolation & Grid Protection), chịu trách nhiệm hoàn tất phân tầng telemetry, cách ly bộ nhớ đệm dịch thuật, kiểm tra tính toàn vẹn hình ảnh & cấu trúc của PDF đầu ra, và chạy kiểm thử tích hợp toàn trình (E2E pipeline integration):

1. **Kiểm tra tính toàn vẹn hình ảnh và cấu trúc PDF (Visual & Structural Integrity):**
   - Xác minh redaction chỉ loại bỏ text (`PDF_REDACT_TEXT_REMOVE`) mà không làm tổn hại đến vector drawings, border strokes hay line art (`graphics=PDF_REDACT_LINE_ART_NONE`).
   - Chữ dịch nằm trọn trong ô (`CellGeometry`), tuân thủ stroke-aware insets, không tràn đè lên đường viền bảng.
   - Các bảng bị từ chối (`table_rejected`) bảo toàn 100% vector art và văn bản nguồn trên cả tài liệu nhiều trang và các trang giao dịch fallback.

2. **Kiểm chứng telemetry nhiều tầng (Multi-tier Telemetry Stratification):**
   - Phân tầng minh bạch giữa cấp Block (`total_blocks`, `replaced_blocks`, `overflow_blocks`), Cell (`total_cells`, `replaced_cells`, `overflow_cells`), và Table (`rejected_tables`).
   - Bảng bị từ chối ghi nhận `unit_kind="TABLE"`, chỉ tăng `report.rejected_tables` mà không làm sai lệch hay thổi phồng (inflate) `skipped_blocks` hay `total_cells`.
   - Đối soát toàn diện các trạng thái: `SUCCESS`, `OVERFLOW_FALLBACK`, `TRANSACTION_FALLBACK`, `SKIPPED_UNCHANGED`, `SKIPPED_UNSUPPORTED`.
   - Bảo đảm nguyên tắc **Zero False Success**: Không đếm trùng, không bỏ sót, và chỉ ghi nhận `SUCCESS` khi trang thực sự được commit sạch vào `output_doc`.

3. **Cách ly cache dịch thuật ô bảng (Translation Cache Isolation):**
   - Khóa cache theo địa chỉ nội dung (`compute_cache_key`) dựa trên `segment.masked_text`, bảo đảm các partitioned cell segments không bao giờ va chạm với cache cũ của các merged blocks trước phân vùng, đồng thời các cell giống hệt nhau tái sử dụng cache hiệu quả.

4. **Final Regression & End-to-End Pipeline Integration:**
   - Kiểm thử toàn diện chu trình: `PDF đầu vào` -> `Layout Parser & TableGridValidator` -> `TableCellPartitioner` -> `TranslationService (MockProvider)` -> `TypesetEngine (Page Transactions)` -> `DocumentAccumulator` -> `Post-Assembly Link Restoration` -> `PDF đầu ra`.
   - Kiểm tra các đặc tính thực tế của file PDF sau xuất bản: Vector line art, text placement, internal & external links, metadata.

## 2. Ranh giới (Scope Boundaries)
- **Không bao gồm:** Thiết kế giao diện đồ họa (GUI / Desktop UI).
- **Không bao gồm:** Git push hoặc merge vào remote main.
- **Không bao gồm:** Thay đổi CLI options công khai ngoài phạm vi Slice 4C.2.

## 3. Acceptance Tests (TDD)
1. `test_table_level_telemetry_isolation_no_block_inflation`: Kiểm tra `unit_kind="TABLE"`, `report.rejected_tables` tách biệt hoàn toàn với metric cell.
2. `test_table_cell_translation_cache_isolation_from_merged_blocks`: Kiểm tra phân tách cache key giữa cell riêng lẻ và merged blocks.
3. `test_rebuilt_pdf_table_visual_and_structural_integrity`: Kiểm tra đầu ra PDF thực tế bảo toàn vector drawings, kích thước trang, text placement.
4. `test_end_to_end_full_pipeline_multi_page_pdf_integration`: Kiểm tra tích hợp toàn trình đa trang từ PDF byte đầu vào đến PDF byte đầu ra với bảng và link hoàn chỉnh.
