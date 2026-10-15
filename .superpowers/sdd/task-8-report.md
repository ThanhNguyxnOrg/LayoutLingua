# Task 8 Implementation Report: Post-Assembly Link Restoration & Dual `LINK_NAMED` Engine

**Base Commit:** `ae2f080`
**Commit:** `fe98241`
**Review Diff:** `.superpowers/sdd/review-ae2f080..fe98241.diff`
**Test Suite Status:** **155/155 PASS** (12.14s runtime)

---

## 1. Tóm tắt Triển khai

Task 8 đã hoàn thành tầng phục hồi liên kết sau ghép trang (Post-Assembly Link Restoration) và động cơ xử lý kép cho `LINK_NAMED` theo đúng hợp đồng spec Superpowers SDD:

1. **Khôi phục liên kết chéo trang & liên kết ngoài (`DocumentAccumulator.restore_links`):**
   - Vận hành sau khi toàn bộ $N$ trang đã được commit vào `output_doc` với cờ `links=False` (loại bỏ hoàn toàn rủi ro `insert_pdf()` làm đứt gãy hoặc mất liên kết chéo trang).
   - Duyệt tuần tự từng trang `source_doc[p]` và `output_doc[p]`:
     - `LINK_GOTO`: Khôi phục verbatim với đầy đủ `page`, tọa độ `to` và vùng clickable `from`.
     - `LINK_URI`: Khôi phục verbatim liên kết web ngoài với URI đích và vùng click.

2. **Dual `LINK_NAMED` Engine:**
   - **Predefined Viewer Actions:** Nhận diện các hành động định sẵn theo chuẩn PDF viewer (`NextPage`, `PrevPage`, `FirstPage`, `LastPage`). Các link này được tái tạo dưới dạng `LINK_NAMED` nguyên bản, không bị biến đổi sai thành link trang cố định.
   - **Named Destinations:** Đối với các liên kết `nameddest=<name>`:
     - Tra cứu bảng tên tài liệu nguồn thông qua `self.source_doc.resolve_names()`.
     - Chuyển đổi tọa độ điểm đến bằng ma trận biến đổi của trang đích: `goto_point = raw_point * dest_output_page.transformation_matrix` (xử lý chính xác cả trang chuẩn, trang có offset CropBox, và trang xoay 90°/270°).
     - Chuyển đổi thành công sang `LINK_GOTO` gắn vào trang đầu ra.
   - **Fail-Closed & Dead Link Protection:** Nếu named destination không tồn tại hoặc trỏ ra trang ngoài phạm vi, link bị hủy bỏ an toàn (không tạo dead link trong PDF đầu ra), đồng thời ghi nhận cảnh báo telemetry chẩn đoán vào `report.warnings`.

3. **Bảo toàn Form Widgets & Standalone Catalog Destinations:**
   - Bảo toàn các widget biểu mẫu đa trang bằng `join_duplicates=True`.
   - Quét và ghi nhận cảnh báo chẩn đoán cho các standalone catalog named destinations tồn tại trong cấu trúc tài liệu nhưng không có link nào tham chiếu.

4. **Kỷ luật Ranh giới (Scope Boundaries):**
   - Chưa tích hợp telemetry trực quan cấp tài liệu của Task 9.
   - Chưa can thiệp GUI hay thay đổi CLI bên ngoài.

---

## 2. Kết quả Acceptance Tests & Regression

- ** Acceptance Tests mới (7 tests):**
  1. `test_multipage_cross_page_internal_and_external_link_restoration`: Khôi phục `LINK_GOTO` chéo trang và `LINK_URI` chính xác.
  2. `test_multipage_named_actions_preservation`: Bảo toàn `LINK_NAMED` với các action định trước (`NextPage`, `PrevPage`).
  3. `test_multipage_named_destination_resolution_standard_page`: Giải quyết named destination thành `LINK_GOTO` trên trang chuẩn (300 x 400 pt).
  4. `test_multipage_named_destination_resolution_offset_cropbox`: Giải quyết named destination với offset CropBox qua transformation matrix.
  5. `test_multipage_named_destination_resolution_rotated_page`: Giải quyết named destination trên trang xoay 90°/270° kèm rotation matrix.
  6. `test_multipage_unresolvable_named_destination_emits_warning_no_dead_link`: Bỏ qua named destination không tồn tại, ghi warning vào `report.warnings`, không tạo dead link.
  7. `test_multipage_form_widgets_and_catalog_dests_warning`: Bảo toàn form widgets và ghi warning cho standalone catalog dests.

- **Toàn bộ Test Suite:** **155/155 PASS** (0 failures, 0 errors, 12.14s runtime).
