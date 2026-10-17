# LayoutLingua

> **State-of-the-Art Academic & Technical PDF Translation Engine** with strict typography geometry preservation, neural layout analysis, and formula shielding.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![ONNX Runtime](https://img.shields.io/badge/Vision%20Engine-DocLayout--YOLO%20(ONNX)-green.svg)](https://github.com/opendatalab/DocLayout-YOLO)

---

## 🌟 Điểm Nổi Bật & Kỹ Thuật Đột Phá

LayoutLingua kết hợp tinh hoa kiến trúc từ các dự án mã nguồn mở hàng đầu thế giới (**pdf2zh**, **BabelDOC**, **MinerU**, **Marker**), giải quyết triệt để bài toán vỡ khung hình, sai trật tự đọc, và mất công thức khi dịch tài liệu khoa học:

1. **Bảo Tồn Hình Học & Typography Tuyệt Đối:**
   - Trích xuất và xây dựng cấu trúc trung gian **DocumentIR** độc lập.
   - Cơ chế **Soft Margin Absorption** (hấp thụ 8% lề dọc) và **Micro-Compaction** thích ứng (thu nhỏ tỷ lệ vi mô 1.02x) ngăn ngừa hoàn toàn hiện tượng tràn khung (overflow) hay vỡ trang.

2. **Bảo Vệ Công Thức & Ký Hiệu Khoa Học (Shielding):**
   - Tự động phát hiện công thức nội dòng và hiển thị ($\LaTeX$, Unicode math, MathJax).
   - Che chắn tham chiếu học thuật (`[1]`, `[2, 3]`, `[1-5]`) và từ viết tắt chuyên ngành (`et al.`, `Fig.`, `i.e.`, `e.g.`) qua token bảo vệ `⟦LL_REF_...⟧` và `⟦LL_ABBR_...⟧`.
   - Chuẩn hóa Unicode Mojibake tự động bằng `ftfy` trước khi dịch.

3. **Thuật Toán Đọc Đa Cột & Khử Nối Từ (De-hyphenation):**
   - **XY-Cut Spatial Clustering**: Tự động phân tách bài báo khoa học 2 cột thành luồng đọc chuẩn (Tiêu đề $\rightarrow$ Cột trái $\rightarrow$ Cột phải $\rightarrow$ Chú thích chân trang), triệt tiêu lỗi dịch nhảy dòng xuyên cột.
   - **Line-Break De-hyphenation**: Nối liền các từ bị ngắt dòng (`distri-\n bution` $\rightarrow$ `distribution`) nhưng bảo toàn nghiêm ngặt các từ ghép nguyên bản (`state-of-the-art`, `U-Net`, `X-ray`).

4. **Tự Động Loại Bỏ Nhiễu Header & Footer Lặp Lại:**
   - Phân tích tần suất và tọa độ biên lề để nhận diện các dòng running header / running footer lặp lại trên nhiều trang, giữ nguyên bản mà không gửi lặp lại vào LLM gây lãng phí token và làm sai ngữ cảnh.

5. **Bộ Từ Điển Thuật Ngữ Học Thuật Đa Ngữ (Academic Glossaries):**
   - Tích hợp sẵn 6 cặp ngôn ngữ: `en-vi`, `en-zh`, `en-ja`, `en-de`, `en-fr`, `en-es`.
   - Hỗ trợ thêm từ điển tùy biến (Custom Glossary) với cơ chế regex bảo toàn token.

6. **Tối Ưu Hóa Tốc Độ Dịch Song Song (Concurrent Batching):**
   - ThreadPool Worker Pool thông minh: dịch đồng thời đa luồng (3 workers) đối với các Cloud LLM (OpenAI, Gemini, Ollama), tự động điều tiết tuần tự với Google RPC để tránh rate limit.

7. **Thị Giác Máy Tính Phân Vùng Trang (Pluggable ONNX Vision Layout):**
   - Tích hợp adapter `DocLayout-YOLO` chạy trực tiếp qua **ONNXRuntime** và **OpenCV** siêu nhẹ trên CPU, không đòi hỏi PyTorch cồng kềnh (tiết kiệm 95% dung lượng tải).

8. **Xuất Bản Đa Định Dạng:**
   - Xuất PDF đơn ngữ (Monolingual) hoặc PDF song ngữ (Bilingual) trang xen kẽ đối chiếu.
   - Xuất ghi chú học tập Markdown (`.md`) sạch, giữ nguyên công thức toán học $\LaTeX$.
   - Dịch mục lục PDF (Bookmarks/TOC) và tự động tính toán lại số trang trong chế độ song ngữ.

---

## 🚀 Hướng Dẫn Cài Đặt & Sử Dụng

### 1. Cài đặt Python trực tiếp (Khuyên dùng)

Yêu cầu: Python 3.10 - 3.12.

```bash
# Clone repository
git clone https://github.com/ThanhNguyxnOrg/LayoutLingua.git
cd LayoutLingua

# Tạo và kích hoạt môi trường ảo
python -m venv .venv
source .venv/bin/activate  # Trên Linux/macOS
# Hoặc trên Windows PowerShell:
.venv\Scripts\Activate.ps1

# Cài đặt LayoutLingua cùng toàn bộ tính năng tăng tốc thị giác ONNX
pip install -r requirements.txt
pip install -e .
```

Khởi chạy API server:
```bash
python -m layoutlingua.server
# Server sẽ lắng nghe tại: http://127.0.0.1:8765/
```

### 2. Triển khai bằng Docker (Một lệnh duy nhất)

Không cần cài đặt thủ công Python hay thư viện C++:

```bash
docker compose up -d
```
Container sẽ tự động build và chạy LayoutLingua server tại cổng `8765` với đầy đủ ONNX Runtime và OpenCV headless.

---

## 🛠️ Cấu Trúc Mã Nguồn

```
LayoutLingua/
├── layoutlingua/
│   ├── core/              # IR (Intermediate Representation) & PyMuPDF Parser
│   ├── processing/        # De-hyphenation, Reading Order, Citation Shielding, TOC, Sanitizer
│   │   ├── vision/        # DocLayout-YOLO ONNX Vision Layout Detector
│   │   └── formula/       # Math & formula detection
│   ├── translation/       # Multi-provider translation service, Concurrent Pool, Glossaries
│   │   ├── openai_compat.py
│   │   ├── gemini.py
│   │   ├── google_rpc.py
│   │   ├── argos_offline.py
│   │   └── concurrent_pool.py
│   ├── typesetting/       # Fitting, font mapping, margin absorption & PDF accumulation
│   └── server.py          # High-performance local HTTP server (port 8765)
├── desktop/               # React + TypeScript + Tailwind modern GUI client
├── tests/                 # 200+ comprehensive automated tests (100% green)
├── Dockerfile             # Multi-stage production container
└── docker-compose.yml     # Docker compose orchestration
```

---

## 🧪 Kiểm Thử Hệ Thống

Chạy toàn bộ 200+ unit & integration tests:
```bash
pytest
```

---

## 📄 Bản Quyền & Giấy Phép
Dự án được phân phối dưới giấy phép **MIT License**.
