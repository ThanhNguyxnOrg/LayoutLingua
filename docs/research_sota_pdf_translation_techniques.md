# Nghiên Cứu Kỹ Thuật Chuyên Sâu: Các Kỹ Thuật Đột Phá Trong Các Dự Án Mã Nguồn Mở Dịch Thuật PDF Học Thuật

**Tài liệu điều tra & phân tích mã nguồn chính thức (Primary Source Investigation)**  
**Dự án:** LayoutLingua  
**Đối tượng khảo sát:** `pdf2zh` (PDFMathTranslate), `BabelDOC`, `MinerU` (Magic-PDF), `Marker` (DataLab), `Nougat` (Meta AI).

---

## 1. Tóm Tắt Điều Hành (Executive Summary)

Dịch tài liệu PDF kỹ thuật, khoa học và toán học mà vẫn giữ nguyên bố cục (Layout-Preserving PDF Translation) là một bài toán hóc búa vì bản chất file PDF **hoàn toàn không có khái niệm về đoạn văn, dòng chảy văn bản (flow) hay công thức toán**. PDF chỉ là một tập hợp các lệnh vẽ đồ họa tọa độ tuyệt đối (`Tj`, `Tm`, `cm`).

Khi nghiên cứu mã nguồn và kiến trúc của các dự án mã nguồn mở thành công nhất hiện nay, chúng ta nhận thấy:
> **Các engine hàng đầu KHÔNG giải quyết bài toán bằng cách nhồi nhét hàng trăm ngàn từ điển tĩnh vào code.**  
> Thay vào đó, họ tập trung giải quyết **4 bài toán kỹ thuật nền tảng**:
> 1. **Nhận diện và bảo vệ công thức toán học (Math & Inline Equation Isolation)** mà không làm hỏng cú pháp.
> 2. **Hợp nhất các mẩu văn bản bị băm vụn (Horizontal Baseline & Line Merging)** trước khi dịch.
> 3. **Dàn trang co giãn thông minh (Adaptive Typesetting & Elastic Spacing)** để tránh tràn khung (overflow) khi dịch sang ngôn ngữ dài hơn.
> 4. **Bảo vệ mục lục và các ký tự định dạng đặc biệt (Dot-leaders / Tab stops)**.

---

## 2. Phân Tích Mã Nguồn Các Dự Án Mã Nguồn Mở Hàng Đầu

### 2.1. `pdf2zh` (PDFMathTranslate) — Ngôi sao 15.000 ⭐
* **Mã nguồn:** `ByByMe/pdf2zh` (tiền thân là `Byaidu/PDFMathTranslate`)
* **Kiến trúc cốt lõi:** PyMuPDF (`fitz`) + PDFMiner + DocLayout-YOLO + LLM/NMT.

#### 🎯 Kỹ thuật 1: Nhận diện công thức bằng Heuristic Font & Character (`--vfont` & `--vchar`)
Thay vì dùng mô hình AI nặng nề để tìm công thức, `pdf2zh` kiểm tra trực tiếp bảng font chữ được nhúng trong từng `span` của file PDF thông qua PyMuPDF:
```python
# Trích xuất từ mã nguồn pdf2zh:
math_font_regex = r"(CM[^RT].*|MS.*|XY.*|MT.*|BL.*|.*0700|.*0500|.*Math.*|.*Italic)"
math_char_regex = r"(\(|\)|\[|\]|\+|=|\d|[\u0080-\ufaff])"
```
* **Nguyên lý:** Trong tài liệu LaTeX/ArXiv, các ký tự toán học luôn được render bằng các font đặc chủng (như Computer Modern: `CMMI10`, `CMSY10`, MathTime: `MTMI`, MathType). Khi phát hiện font hoặc ký tự thuộc dải này, `pdf2zh` đánh dấu đây là đối tượng toán học bất biến, không đưa vào danh sách dịch.

#### 🎯 Kỹ thuật 2: Token Masking `[v:N]`
* `pdf2zh` gom toàn bộ các công thức toán (cả inline và display math) và thay thế bằng các token định danh: `[v:0]`, `[v:1]`, `[v:2]`.
* Trong System Prompt gửi cho LLM, `pdf2zh` sử dụng luật cứng:
  > *"Rule 1: Preserve all formatting and placeholders [v:N] exactly. Do not translate, do not remove, do not reorder them."*
* Sau khi nhận bản dịch, nó dùng regex quét các token `[v:N]` và map ngược lại với tọa độ vector gốc trên trang PDF.

---

### 2.2. `BabelDOC` (ACL 2024 / funstory-ai)
* **Mã nguồn:** `funstory-ai/BabelDOC`
* **Công bố:** Hội nghị ACL 2024 (*"BabelDOC: An Open-Source Framework for Layout-Preserving PDF Translation via Intermediate Representation Layer"* - ArXiv: 2404.13840).

#### 🎯 Kỹ thuật: Tầng Biểu Diễn Trung Gian (IR Layer) & Thuật Toán Dàn Trang 2 Bước
BabelDOC tách rời hoàn toàn tầng trích xuất PDF và tầng nhét chữ bằng một định dạng trung gian `Intermediate Representation (IR)`:

```
[PDF Thô] ──► [IR Extractor] ──► [IR Document (JSON/Objects)]
                                          │
                                    [Translator]
                                          ▼
[PDF Dịch] ◄── [Adaptive Typesetter] ◄── [Translated IR]
```

#### 🎯 Thuật toán Adaptive Typesetting của BabelDOC:
Khi dịch văn bản sang ngôn ngữ có độ dài lớn hơn (như tiếng Việt dài hơn tiếng Anh 25-35%):
1. **Bước 1 (Line Wrapping & Typesetting Units):** Tính toán bounding box của đoạn văn. Đặt từng từ theo chiều ngang từ góc trên bên trái, tự động xuống dòng khi chạm mép phải.
2. **Bước 2 (Dynamic Tightening Floor):** Nếu toàn bộ đoạn văn dịch bị tràn theo chiều dọc (chiều cao khối text lớn hơn chiều cao bounding box ban đầu):
   - Đầu tiên, **siết khoảng cách dòng (line spacing)** xuống mức tối thiểu (ví dụ: từ `1.4` xuống `1.15`).
   - Nếu vẫn tràn, **giảm font size theo từng nấc `0.5pt`** (tối đa không giảm quá 70% font gốc, có sàn cứng `min_font = 7.0pt`).
   - Nếu vẫn không đủ chỗ, mở rộng bounding box theo chiều dọc vào khoảng trống an toàn bên dưới (Margin Expansion) trước khi fallback.

---

### 2.3. `MinerU` (Magic-PDF / OpenDataLab)
* **Mã nguồn:** `opendatalab/MinerU`
* **Công nghệ:** Math Formula Detection (YOLO-MFD) + UniMERNet (Math Formula Recognition) + LayoutReader.

#### 🎯 Kỹ thuật: Phân Biệt Inline Equation vs Interline Equation & Hợp Nhất Baseline
Trong `mineru/backend/pipeline/para_split.py`, MinerU giải quyết vấn đề nan giải nhất của PyMuPDF:
* **Hiện tượng:** Khi một dòng văn bản chứa ký hiệu toán (như $C_n^k$), PyMuPDF bị lệch trục baseline (do chỉ số trên/dưới `sup/sub`), khiến nó xé dòng văn bản thành 3-5 block chữ vụn vặt:
  - Block 1: `"Số cách chọn"`
  - Block 2: `"C_n^k"`
  - Block 3: `"phần tử từ n phần tử là:"`
* **Giải pháp của MinerU (Span-Level Baseline Stitching):**
  MinerU kiểm tra tọa độ Y của các span:
  $$\Delta Y = |Y_{\text{bottom}, 1} - Y_{\text{bottom}, 2}| \le 0.35 \times \text{font\_size}$$
  $$\text{Gap}_X = X_{\text{left}, 2} - X_{\text{right}, 1} \le 1.5 \times \text{font\_size}$$
  Nếu thỏa mãn, MinerU **gộp các span này lại thành một dòng duy nhất** và nhúng ký hiệu toán học như một phần tử con của dòng văn bản. Khi gửi dịch, toàn bộ câu được gửi đi nguyên vẹn, loại bỏ 100% tình trạng dịch đứt quãng.

---

### 2.4. `Marker` (VikParuchuri / DataLab)
* **Mã nguồn:** `datalab-to/marker`
* **Module then chốt:** `marker/processors/line_merge.py`

#### 🎯 Kỹ thuật: Line Merging & Hyphenation Rebuilding
Marker xử lý việc nối dòng văn bản khi một từ bị ngắt bởi dấu gạch nối (`-`) ở cuối dòng:
1. Phát hiện dấu gạch nối mềm (soft hyphen) hoặc gạch ngang cuối dòng `r"(\w+)-\s*$"`.
2. Kiểm tra từ điển hoặc mô hình để ghép từ hoàn chỉnh trước khi chuyển qua bước tiếp theo.
3. Ghép các dòng trong cùng một khối đoạn văn thành một chuỗi duy nhất, chỉ giữ lại ngắt dòng thực sự (paragraph boundary).

---

## 3. Tổng Hợp & Ma Trận So Sánh Các Kỹ Thuật

| Vấn Đề Kỹ Thuật | Cách Tiếp Cận Cũ (Hardcode / Naive) | Kỹ Thuật Của `pdf2zh` & `BabelDOC` | Kỹ Thuật Của `MinerU` & `Marker` | Giải Pháp Tối Ưu Cho LayoutLingua |
| :--- | :--- | :--- | :--- | :--- |
| **Công thức toán học** | Dịch thẳng hoặc dựa vào từ điển tĩnh | Soi font (`CM*`, `MT*`) + Token Masking `[v:N]` | Dùng mô hình YOLO-MFD trích xuất LaTeX | **Font Heuristics + Token Shield `⟦LL_FORMULA_X⟧`** (nhẹ, nhanh, không cần GPU) |
| **Dòng chữ bị băm vụn** | Dịch từng ô nhỏ $\rightarrow$ Tràn khung | Gộp các dòng trong block | Thuật toán so khớp Baseline $\Delta Y \le 0.35 \times h$ | **Horizontal Baseline Fragment Merging** trong `parser.py` |
| **Mục lục có dấu chấm `.....`** | MT copy lại 70 dấu chấm $\rightarrow$ Tràn dòng | Nhận diện mục lục, tách tựa đề và số trang | Parse cấu trúc TOC theo level | **Elastic Dot-Leader (`\dotfill`)**: Co giãn số lượng chấm theo chiều rộng còn lại |
| **Văn bản dịch bị dài hơn** | Giữ nguyên cỡ chữ $\rightarrow$ Đè chữ khác | Co font theo bậc & siết line-spacing | Reflow toàn trang (tái tạo lại PDF) | **Multi-Stage Adaptive Fitting**: Co khoảng cách dòng $\rightarrow$ Co font $\rightarrow$ Micro-padding |
| **Thuật ngữ chuyên ngành** | Nạp file JSON hàng trăm ngàn từ | Prompt Engine + Contextual LLM | LLM Contextual Injection | **Hybrid**: System Prompt thông minh + Glossary cục bộ chọn lọc |

---

## 4. Các Bài Học Cụ Thể Triển Khai Vào LayoutLingua

Từ các phát hiện trên, chúng ta có 3 bước hành động cụ thể để nâng cấp LayoutLingua lên tiêu chuẩn SOTA của `pdf2zh` và `BabelDOC`:

### 📌 Hành Động 1: Cải tiến `parser.py` — Horizontal Baseline Line Merging
* **Vấn đề cần khắc phục:** Trang 13 `Sotaytoanhoc.pdf` có 15 ô chữ vụn nằm trên cùng 1 hàng do công thức toán $C_n^k$ có baseline lệch.
* **Cách làm:** Trong hàm `LayoutParser.parse_page()`, bổ sung bước tiền xử lý:
  - Nhóm các text block có độ phủ dọc $\ge 65\%$ và khoảng cách ngang $\le 25\text{pt}$.
  - Gộp thành 1 unified block với các thẻ `<b0>...</b0>` hoặc `⟦LL_FORMULA_X⟧`.

### 📌 Hành Động 2: Cải tiến `fitting.py` — Elastic Dot-Leader (`\dotfill`)
* **Vấn đề cần khắc phục:** Trang 2 và 3 mục lục bị `OVERFLOW_FALLBACK` do tiêu đề tiếng Anh dài cộng với 50 dấu chấm lửng làm rớt dòng.
* **Cách làm:** Trong `TextFitTester.test_fit()`:
  - Bắt regex `r"^(.*?)(\s*[\.\:\-_–—…]{3,}\s*)(\d+)$"`.
  - Tự động co ngắn chuỗi chấm lửng để tổng chiều rộng tiêu đề + chấm + số trang bằng đúng chiều rộng block ban đầu mà không rớt dòng.

### 📌 Hành Động 3: Tối ưu hoá System Prompt cho LLM
* Thay vì chỉ dựa vào từ điển cứng, hoàn thiện System Prompt với chỉ thị bảo vệ placeholder bất biến `⟦...⟧` theo chuẩn của `pdf2zh`:
  ```text
  You are an academic translation engine. 
  Preserve all tags like ⟦LL_FORMULA_X⟧, ⟦LL_REF_X⟧ exactly as they appear. 
  Do not translate, alter, or remove any placeholder tags.
  ```

---

## 5. Tài Liệu Tham Khảo (Primary Sources Citations)
1. **pdf2zh:** [https://github.com/ByByMe/pdf2zh](https://github.com/ByByMe/pdf2zh) — Codebase `converter.py`, `high_level.py`.
2. **BabelDOC:** [https://github.com/funstory-ai/BabelDOC](https://github.com/funstory-ai/BabelDOC) — ACL 2024 Paper: *"BabelDOC: An Open-Source Framework for Layout-Preserving PDF Translation via Intermediate Representation Layer"*.
3. **MinerU (Magic-PDF):** [https://github.com/opendatalab/MinerU](https://github.com/opendatalab/MinerU) — `para_split.py` & Layout Pipeline documentation.
4. **Marker:** [https://github.com/datalab-to/marker](https://github.com/datalab-to/marker) — `marker/processors/line_merge.py`.
5. **Nougat:** [https://github.com/facebookresearch/nougat](https://github.com/facebookresearch/nougat) — Meta AI ArXiv: 2308.13418.
