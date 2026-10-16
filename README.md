# LayoutLingua

> **High-Precision Document Translation Engine** that preserves formatting, mathematical formulas, tables, and typography geometry.

---

## 📌 Tổng Quan Dự Án & Định Hướng Tái Thiết Kế

Kho lưu trữ đã được dọn dẹp để chuẩn bị cho giai đoạn tái cấu trúc và xây dựng lại từ đầu theo kiến trúc sạch (Clean Decoupled Architecture), kế thừa các ưu điểm vượt trội từ các dự án mã nguồn mở hàng đầu thế giới:

- **[BabelDOC](https://github.com/funstory-ai/BabelDOC):** Kiến trúc Intermediate Representation (IR), bảo toàn không gian màu gốc (CMYK/ICC/RGB), ghép nối câu xuyên trang, typography thích ứng.
- **[PDFMathTranslate](https://github.com/PDFMathTranslate/PDFMathTranslate-next):** Cơ chế bảo vệ công thức toán học và bảng biểu.
- **[AllenAI olmOCR](https://github.com/allenai/olmocr):** Khả năng xử lý tài liệu scan và bảng phức tạp với Vision-Language Models.
- **[OpenDataLab DocLayout-YOLO](https://github.com/opendatalab/DocLayout-YOLO):** Nhận diện phân vùng trang tốc độ cao (ONNX).
- **[MinerU (Magic-PDF)](https://github.com/opendatalab/MinerU):** Chuẩn hóa trích xuất công thức LaTeX và cấu trúc bảng.

---

## 📖 Tài Liệu Nghiên Cứu & Thiết Kế

Toàn bộ bản đồ kiến trúc, phân tích chi tiết từng module kỹ thuật và bản thiết kế thế hệ mới được lưu tại:
👉 **[ARCHITECTURE_AND_KNOWLEDGE_BASE.md](ARCHITECTURE_AND_KNOWLEDGE_BASE.md)**

---

## 🛡️ Bản Lưu Trữ Trạng Thái Cũ (Legacy Backup)

Nhánh mã nguồn cũ trước khi dọn dẹp đã được bảo lưu an toàn tại nhánh git:
```bash
git checkout backup/legacy-before-cleanup
```
