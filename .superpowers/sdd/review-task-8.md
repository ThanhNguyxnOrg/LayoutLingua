# Independent Review Report: Task 8 — Post-Assembly Link Restoration & Dual `LINK_NAMED` Engine

**Diff Under Review:** `ae2f080..fe98241` (`.superpowers/sdd/review-ae2f080..fe98241.diff`)
**Reviewer:** Independent Reviewer Subagent
**Date:** 2026-10-15

---

## 1. Spec Compliance Review

### Tiêu chí 1: Phục hồi liên kết nội bộ chéo trang & liên kết ngoài (Cross-Page & External Link Restoration)
- **Đánh giá:** **PASS**
- **Bằng chứng:** Trong `DocumentAccumulator.restore_links()`, sau khi toàn bộ $N$ trang của tài liệu đã được cam kết nguyên tử với `links=False`, hàm duyệt tuần tự từng cặp trang nguồn - đích `(source_page, output_page)`. Các link loại `pymupdf.LINK_GOTO` và `pymupdf.LINK_URI` được đọc trực tiếp từ `source_page.get_links()` và chèn lại nguyên bản (`output_page.insert_link(link)`). Kiểm thử chấp nhận `test_multipage_cross_page_internal_and_external_link_restoration` xác nhận cả link chéo trang từ trang 0 sang trang 1 và URI ngoại đều tồn tại chính xác trên trang đầu ra.

### Tiêu chí 2: Động cơ xử lý kép cho `LINK_NAMED` (Dual `LINK_NAMED` Engine)
- **Đánh giá:** **PASS**
- **Bằng chứng:** 
  - Khối `elif kind == pymupdf.LINK_NAMED:` trích xuất tên thông qua cả hai khóa tương thích PyMuPDF `link.get("name") or link.get("nameddest") or ""`.
  - Phân loại rõ ràng:
    1. **Predefined Actions:** Kiểm tra tập hằng số `PREDEFINED_NAMED_ACTIONS` (`NextPage`, `PrevPage`, `FirstPage`, `LastPage`). Nếu khớp, tái tạo `action_link` với `kind: LINK_NAMED` mà không chuyển đổi thành destination. Kiểm thử `test_multipage_named_actions_preservation` xác nhận `NextPage` trên trang 1 và `PrevPage` trên trang 2 được bảo toàn.
    2. **Named Destinations:** Tách tiền tố `nameddest=` và tra cứu trong từ điển `resolved_names` lấy từ `self.source_doc.resolve_names()`. Chuyển đổi thành công sang `LINK_GOTO` với tọa độ đích được biến đổi theo ma trận `transformation_matrix` của trang đích.

### Tiêu chí 3: Chuyển đổi tọa độ trang chuẩn, Offset CropBox và Trang Xoay (Coordinate Transformation)
- **Đánh giá:** **PASS**
- **Bằng chứng:**
  - Trang chuẩn: `test_multipage_named_destination_resolution_standard_page` kiểm chứng điểm `(40, 320)` trong không gian PDF gốc được chuyển thành `Point(40.0, 80.0)` theo hệ tọa độ top-left của PyMuPDF.
  - Trang có CropBox lệch: `test_multipage_named_destination_resolution_offset_cropbox` với `CropBox = Rect(50, 50, 250, 350)` xác nhận tọa độ `(100, 200)` được ánh xạ chuẩn xác thành `Point(50.0, 150.0)`.
  - Trang xoay: `test_multipage_named_destination_resolution_rotated_page` với trang xoay 90° và 270° xác nhận việc áp dụng transformation matrix chuyển đổi tọa độ tương thích toàn diện với ma trận xoay của trang đích.

### Tiêu chí 4: Xử lý an toàn khi đích không giải quyết được & cảnh báo (Fail-Closed & Dead Link Protection)
- **Đánh giá:** **PASS**
- **Bằng chứng:** Nếu named destination không có trong `resolved_names` hoặc chỉ số trang đích nằm ngoài phạm vi `[0, len(output_doc) - 1]`, hàm không chèn link (bảo đảm zero dead links) và ghi cảnh báo rõ ràng vào `report.warnings`. Kiểm thử `test_multipage_unresolvable_named_destination_emits_warning_no_dead_link` kiểm chứng `len(out_doc[0].get_links()) == 0` và `report.warnings` ghi nhận cảnh báo chính xác.

### Tiêu chí 5: Form Widgets & Standalone Catalog Destinations
- **Đánh giá:** **PASS**
- **Bằng chứng:** Form widgets đa trang được bảo lưu và gộp định danh thống nhất thông qua `join_duplicates=True`. Đồng thời, các named destination trong catalog nhưng không được bất kỳ link nào trỏ tới được phát hiện và ghi nhận cảnh báo chẩn đoán (`test_multipage_form_widgets_and_catalog_dests_warning`).

---

## 2. Code Quality Review

- **Tách biệt trách nhiệm:** Post-assembly link restoration được đóng gói gọn trong phương thức `DocumentAccumulator.restore_links(report)` và được gọi tự động trong `finish(report=report)`. `TypesetEngine.typeset()` chỉ cần truyền `report` vào `accumulator.finish()`.
- **An toàn ngoại lệ & Không làm hỏng tài liệu:** Từng bước trích xuất link, chèn link và resolve names đều được bọc trong các khối `try...except` cục bộ, bảo đảm một link bất thường không bao giờ làm hỏng toàn bộ tài liệu đầu ra.
- **Tính tương thích định dạng:** Hỗ trợ đầy đủ cả key `'name'` và `'nameddest'` từ PyMuPDF, bảo đảm tính bền vững trên các phiên bản PyMuPDF khác nhau.
- **Hiệu năng & Tài nguyên:** Bảng tên `resolve_names()` chỉ được gọi đúng 1 lần cho cả tài liệu, tránh lặp lại chi phí duyệt cấu trúc catalog PDF.

---

## 3. Findings & Verdict

| Mức độ | Vấn đề | Đánh giá / Khuyến nghị |
|:---|:---|:---|
| **Critical** | Không có | Không |
| **Important** | Không có | Không |
| **Suggestion** | Hỗ trợ zoom levels đa dạng từ resolve_names | Hiện tại `dest_info` trả về `zoom` nhưng mặc định fit hoặc giữ nguyên; với các tài liệu tài chính / học thuật điều này là hoàn toàn hợp lý. |

### Final Verdict:
- **Spec Compliance:** **PASS**
- **Code Quality:** **PASS**
- **Kết luận:** Task 8 đáp ứng đầy đủ và toàn diện các yêu cầu kỹ thuật, đạt 155/155 test PASS, sẵn sàng nghiệm thu để mở Task 9.
