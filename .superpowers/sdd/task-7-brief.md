# Task 7 Brief: Multi-Page Document Accumulator & Document-Level Preservation

**Base Commit:** `d3b00b7`
**Target Commit:** `feat(typesetting): implement multi-page document accumulator and document metadata preservation`

## 1. Mục tiêu và Phạm vi
Xây dựng tầng tích lũy tài liệu đa trang (`DocumentAccumulator` / tích hợp trong `TypesetEngine`) nhằm:
1. Tiếp nhận các `PageTransactionResult` và ghép vào `output_doc` theo thứ tự trang tuyệt đối (`0, 1, ..., N-1`), ngăn ngừa bỏ sót hoặc trùng lặp trang.
2. Xử lý tài liệu có các trang kết hợp: trang typeset thành công và trang fallback mà không gây xáo trộn thứ tự hay làm hỏng cấu trúc PDF.
3. Cơ chế Commit Gate an toàn với rollback nguyên tử:
   - Nếu `output_doc.insert_pdf()` gặp lỗi, rollback trang bị lỗi bằng `output_doc.delete_page(-1)` (nếu trang đã lỡ thêm vào) và commit trang nguồn pristine `source_doc[p]`.
   - Cổng ghi nhận Telemetry: Chỉ ghi nhận các metric `SUCCESS` vào `FittingReport` khi commit thành công vào `output_doc`. Khi commit thất bại, chuyển thành metric fallback (`TRANSACTION_FALLBACK`).
4. Bảo toàn thuộc tính cấp tài liệu (Document-Level Preservation):
   - Metadata: `set_metadata(source_doc.metadata)` (Title, Author, Subject, Keywords, Creator, Producer, CreationDate, ModDate).
   - Mục lục (TOC): `set_toc(source_doc.get_toc())`.
   - Nhãn trang (Page Labels): `set_page_labels(source_doc.get_page_labels())`.
   - File đính kèm (Embedded files): Duyệt qua `embfile_names()` và chuyển sang `output_doc`.
   - XML Metadata: `set_xml_metadata(source_doc.get_xml_metadata())`.
   - Form widgets: Hợp nhất qua `join_duplicates=True`.

## 2. Ranh giới (Scope Boundaries)
- **Không bao gồm:** Khôi phục liên kết chéo trang (`LINK_GOTO`, `LINK_URI`, `LINK_NAMED`) - phần này thuộc Task 8.
- **Không bao gồm:** GUI hay thay đổi CLI bên ngoài.
- **Không bao gồm:** git push hay merge vào main từ remote.

## 3. Acceptance Tests dự kiến (TDD)
1. `test_multipage_assembly_exact_order_and_no_duplication`: Ghép 3 trang theo đúng thứ tự 1, 2, 3 không trùng lặp, không mất trang ngay cả khi PageIR đưa vào không đúng thứ tự.
2. `test_multipage_transaction_isolation_rollback_preserves_other_pages`: Trang 1 thành công, trang 2 fallback, trang 3 không đổi -> cả 3 trang xuất hiện đúng thứ tự trong file PDF đầu ra với nội dung tương ứng.
3. `test_multipage_document_level_metadata_and_toc_preservation`: Title, Author, TOC, embedded files được bảo toàn nguyên vẹn trong file output.
4. `test_multipage_commit_phase_exception_recovery`: Mô phỏng exception trong lúc `output_doc.insert_pdf()`, hệ thống rollback và commit fallback source page, đảm bảo tổng số trang và không ghi nhận false SUCCESS.
5. `test_multipage_catastrophic_page_exception_emergency_fallback`: Unhandled exception trong một trang kích hoạt fallback khẩn cấp cho trang đó, các trang khác vẫn bình thường.
