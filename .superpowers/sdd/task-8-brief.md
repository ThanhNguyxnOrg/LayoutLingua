# Task 8 Brief: Post-Assembly Link Restoration & Dual `LINK_NAMED` Engine

**Base Commit:** `ae2f080`
**Target Commit:** `feat(typesetting): implement post-assembly link restoration and dual LINK_NAMED contract`

## 1. Mục tiêu và Phạm vi
Khôi phục các liên kết nội bộ, liên kết web và các named destinations sau khi tất cả các trang đã được ghép vào tài liệu đích `output_doc`:
1. **Liên kết chéo trang (Cross-page internal links - `LINK_GOTO`):**
   - Không phụ thuộc vào `insert_pdf()` từng trang (vốn làm mất internal links trỏ tới trang khác).
   - Duyệt qua từng trang nguồn và re-insert liên kết nội bộ `LINK_GOTO` trên trang đích tương ứng với đầy đủ `page`, `to` (Point) và vùng clickable `from` (Rect).
2. **Liên kết ngoại (External URI links - `LINK_URI`):**
   - Re-insert chính xác trên trang đích với `uri` và vùng clickable `from`.
3. **Dual `LINK_NAMED` Engine:**
   - Phân biệt giữa hành động định trước (predefined viewer actions: `NextPage`, `PrevPage`, `FirstPage`, `LastPage`) và named destination (`nameddest=section_x`).
   - Nếu là predefined named action: bảo toàn dạng `LINK_NAMED`.
   - Nếu là named destination: tra cứu trong `source_doc.resolve_names()`, chuyển đổi tọa độ điểm đến qua `dest_page.transformation_matrix` (xử lý chuẩn cả trang thường, trang offset CropBox, trang xoay 90°/270°), và re-insert dưới dạng `LINK_GOTO`.
   - Đích không tồn tại (unresolvable): bỏ qua không tạo link chết (no dead links), ghi nhận diagnostic telemetry warning vào `report.warnings`.
4. **Form Widgets & Standalone Catalog Destinations:**
   - Giữ nguyên các widget biểu mẫu không làm hỏng PDF (`annots=True, widgets=True, join_duplicates=True`).
   - Ghi nhận cảnh báo chẩn đoán nếu tài liệu nguồn có standalone catalog destinations.

## 2. Ranh giới (Scope Boundaries)
- **Không bao gồm:** GUI hay thay đổi CLI bên ngoài.
- **Không bao gồm:** Sửa đổi logic fitting hoặc cell partitioner của các task trước.
- **Không bao gồm:** git push hay merge vào main từ remote.

## 3. Acceptance Tests dự kiến (TDD)
1. `test_multipage_cross_page_internal_and_external_link_restoration`: Khôi phục `LINK_GOTO` chéo trang và `LINK_URI`.
2. `test_multipage_named_actions_preservation`: Bảo toàn `LINK_NAMED` với các action định trước (`NextPage`, `PrevPage`).
3. `test_multipage_named_destination_resolution_standard_page`: Giải quyết named destination thành `LINK_GOTO` trên trang chuẩn.
4. `test_multipage_named_destination_resolution_offset_cropbox`: Giải quyết named destination với offset CropBox qua transformation matrix.
5. `test_multipage_named_destination_resolution_rotated_page`: Giải quyết named destination trên trang xoay 90°/270°.
6. `test_multipage_unresolvable_named_destination_emits_warning_no_dead_link`: Bỏ qua named destination không tồn tại, ghi warning, không tạo dead link.
7. `test_multipage_form_widgets_and_catalog_dests_warning`: Bảo toàn form widgets và ghi warning catalog dests.
