// Deterministic demonstration data. Not produced by the LayoutLingua engine.
export type Block =
  | { kind: 'h'; id: string; en: string; vi: string }
  | { kind: 'p'; id: string; en: string; vi: string }
  | { kind: 'eq'; id: string; tex: string; no: string }
  | { kind: 'table'; id: string; caption: [string, string]; head: [string, string][]; rows: [string, string][][] }
  | { kind: 'fig'; id: string; caption: [string, string] }
  | { kind: 'title'; id: string; en: string; vi: string; authors: string }

export type PageStatus = 'ok' | 'warn' | 'fallback' | 'pending'
export type Page = { n: number; status: PageStatus; blocks: Block[]; blockCount: number; cellCount: number }

export type Severity = 'info' | 'warning' | 'failure'
export type Issue = { id: string; severity: Severity; page: number; region?: string; title: string; detail: string; next: string; action: string; code: string }

const P = (id: string, en: string, vi: string): Block => ({ kind: 'p', id, en, vi })
const H = (id: string, en: string, vi: string): Block => ({ kind: 'h', id, en, vi })

export const pages: Page[] = [
  { n: 1, status: 'ok', blockCount: 9, cellCount: 0, blocks: [
    { kind: 'title', id: 'b1', en: 'Sparse Attention for Long-Context Document Layout Analysis', vi: 'Chú ý thưa cho phân tích bố cục tài liệu ngữ cảnh dài', authors: 'A. Moreau, K. Tanaka, L. Hoang — Institute for Document Computing' },
    H('b2', 'Abstract', 'Tóm tắt'),
    P('b3', 'We study layout analysis for documents whose structure spans many pages. Existing models truncate context, which breaks the association between captions, tables and their references. We propose a sparse attention scheme that scales linearly with page count.', 'Chúng tôi nghiên cứu phân tích bố cục cho các tài liệu có cấu trúc trải dài trên nhiều trang. Các mô hình hiện có cắt ngắn ngữ cảnh, làm đứt mối liên kết giữa chú thích, bảng biểu và các tham chiếu của chúng. Chúng tôi đề xuất một cơ chế chú ý thưa có độ phức tạp tăng tuyến tính theo số trang.'),
    H('b4', '1  Introduction', '1  Giới thiệu'),
    P('b5', 'Scientific PDFs encode reading order implicitly. Columns, floats and footnotes interleave, and a single table may be referenced from three different sections.', 'Các tệp PDF khoa học mã hóa thứ tự đọc một cách ngầm định. Các cột, phần tử nổi và chú thích cuối trang đan xen nhau, và một bảng có thể được tham chiếu từ ba mục khác nhau.'),
    P('b6', 'Our contributions are a block-sparse attention mask derived from page geometry, and an evaluation protocol that measures structural agreement rather than token accuracy.', 'Đóng góp của chúng tôi gồm một mặt nạ chú ý thưa theo khối được suy ra từ hình học trang, và một quy trình đánh giá đo mức độ thống nhất cấu trúc thay vì độ chính xác theo token.'),
  ]},
  { n: 2, status: 'ok', blockCount: 11, cellCount: 0, blocks: [
    H('b1', '2  Related Work', '2  Công trình liên quan'),
    P('b2', 'Layout models fall into two families: detection-based methods that predict bounding regions, and sequence-based methods that serialise the page into tokens with positional embeddings.', 'Các mô hình bố cục chia thành hai nhóm: phương pháp dựa trên phát hiện, dự đoán các vùng bao, và phương pháp dựa trên chuỗi, tuần tự hóa trang thành các token kèm nhúng vị trí.'),
    P('b3', 'Sparse transformers reduce quadratic cost by restricting attention to local windows and a small set of global tokens.', 'Các transformer thưa giảm chi phí bậc hai bằng cách giới hạn sự chú ý trong các cửa sổ cục bộ và một tập nhỏ token toàn cục.'),
    { kind: 'fig', id: 'b4', caption: ['Figure 1. Attention pattern across four consecutive pages.', 'Hình 1. Mẫu chú ý trên bốn trang liên tiếp.'] },
    P('b5', 'Unlike prior work, we derive the sparsity pattern from detected column boundaries rather than fixed windows.', 'Khác với các công trình trước, chúng tôi suy ra mẫu thưa từ ranh giới cột được phát hiện thay vì các cửa sổ cố định.'),
  ]},
  { n: 3, status: 'warn', blockCount: 8, cellCount: 14, blocks: [
    H('b1', '3  Method', '3  Phương pháp'),
    P('b2', 'Let each page contribute n blocks with geometry gᵢ. The attention weight between blocks i and j is masked by their geometric affinity:', 'Giả sử mỗi trang đóng góp n khối với hình học gᵢ. Trọng số chú ý giữa khối i và j được che bởi độ tương hợp hình học của chúng:'),
    { kind: 'eq', id: 'b3', tex: 'A(i,j) = softmax( qᵢ·kⱼ / √d + λ · log φ(gᵢ, gⱼ) )', no: '(1)' },
    P('b4', 'where φ is zero for blocks in non-adjacent columns. Table 1 compares cost on the evaluation corpus.', 'trong đó φ bằng không đối với các khối nằm ở các cột không liền kề. Bảng 1 so sánh chi phí trên tập dữ liệu đánh giá.'),
    { kind: 'table', id: 'b5', caption: ['Table 1. Cost per document (illustrative).', 'Bảng 1. Chi phí trên mỗi tài liệu (minh họa).'],
      head: [['Configuration', 'Cấu hình'], ['Memory', 'Bộ nhớ']],
      rows: [
        [['Dense baseline', 'Cơ sở dày đặc'], ['O(n²)', 'O(n²)']],
        [['Fixed window', 'Cửa sổ cố định'], ['O(n·w)', 'O(n·w)']],
        [['Geometry mask (ours)', 'Mặt nạ hình học (của chúng tôi)'], ['O(n·c)', 'O(n·c)']],
        [['Geometry mask + global tokens', 'Mặt nạ hình học kết hợp token toàn cục'], ['O(n·(c+g))', 'O(n·(c+g))']],
      ] },
    P('b6', 'In practice c is bounded by the number of columns, so memory grows linearly with page count.', 'Trong thực tế c bị chặn bởi số cột, vì vậy bộ nhớ tăng tuyến tính theo số trang.'),
  ]},
  { n: 4, status: 'ok', blockCount: 10, cellCount: 0, blocks: [
    H('b1', '4  Experiments', '4  Thực nghiệm'),
    P('b2', 'We evaluate on 1,240 documents drawn from engineering reports and conference proceedings, each between 8 and 60 pages.', 'Chúng tôi đánh giá trên 1.240 tài liệu lấy từ báo cáo kỹ thuật và kỷ yếu hội nghị, mỗi tài liệu dài từ 8 đến 60 trang.'),
    { kind: 'eq', id: 'b3', tex: 'S = (1/|D|) Σ_d  |T_d ∩ T̂_d| / |T_d ∪ T̂_d|', no: '(2)' },
    P('b4', 'Structural agreement S measures the overlap between reference and predicted structure trees.', 'Độ thống nhất cấu trúc S đo mức chồng lấn giữa cây cấu trúc tham chiếu và cây cấu trúc dự đoán.'),
    { kind: 'fig', id: 'b5', caption: ['Figure 2. Agreement as a function of document length.', 'Hình 2. Độ thống nhất theo độ dài tài liệu.'] },
  ]},
  { n: 5, status: 'fallback', blockCount: 0, cellCount: 0, blocks: [
    H('b1', '5  Discussion', '5  Discussion'),
    P('b2', 'The geometry mask fails when columns are not rectangular, for example in magazine layouts with wrapped figures. We observed this in 3% of the corpus.', 'The geometry mask fails when columns are not rectangular, for example in magazine layouts with wrapped figures. We observed this in 3% of the corpus.'),
    { kind: 'fig', id: 'b3', caption: ['Figure 3. Failure case with a wrapped figure.', 'Figure 3. Failure case with a wrapped figure.'] },
    P('b4', 'Future work could learn φ directly from rendered page images.', 'Future work could learn φ directly from rendered page images.'),
  ]},
  { n: 6, status: 'ok', blockCount: 7, cellCount: 0, blocks: [
    H('b1', '6  Conclusion', '6  Kết luận'),
    P('b2', 'Geometry-derived sparsity preserves long-range structure at linear cost. See Section 3.2 for the derivation.', 'Tính thưa suy ra từ hình học giữ được cấu trúc tầm xa với chi phí tuyến tính. Xem Mục 3.2 để biết phần suy dẫn.'),
    H('b3', 'References', 'Tài liệu tham khảo'),
    P('b4', '[1] Beltagy, I. et al. Longformer: The long-document transformer. 2020.', '[1] Beltagy, I. và cộng sự. Longformer: The long-document transformer. 2020.'),
    P('b5', '[2] Xu, Y. et al. LayoutLM: Pre-training of text and layout. KDD 2020.', '[2] Xu, Y. và cộng sự. LayoutLM: Pre-training of text and layout. KDD 2020.'),
    P('b6', '[3] Zhong, X. et al. PubLayNet: Largest dataset for document layout. ICDAR 2019.', '[3] Zhong, X. và cộng sự. PubLayNet: Largest dataset for document layout. ICDAR 2019.'),
  ]},
]

export const issues: Issue[] = [
  { id: 'q1', severity: 'warning', page: 3, region: 'b5', code: 'TABLE_GEOMETRY_UNVERIFIED', title: 'Table geometry could not be verified', detail: 'Table 1 has ruled borders but no reliable cell boundaries in the PDF. Cells were placed using detected lines.', next: 'Compare both pages and confirm rows still align.', action: 'Open table on page 3' },
  { id: 'q2', severity: 'warning', page: 3, region: 'b5', code: 'CELL_OVERFLOW', title: 'Cell text exceeds the available area', detail: 'Row 4, column 1: the Vietnamese text is longer than the cell. Font size was reduced to 82% of the source.', next: 'Check legibility. Shorten the term in a glossary if needed.', action: 'Open cell on page 3' },
  { id: 'q3', severity: 'failure', page: 5, code: 'PAGE_FALLBACK', title: 'Page preserved from source after a processing error', detail: 'Text extraction failed on a wrapped figure. The original page was copied into the output untranslated.', next: 'Retry this page, or export with the source page kept.', action: 'Open page 5' },
  { id: 'q4', severity: 'info', page: 6, region: 'b2', code: 'DEST_UNRESOLVED', title: 'One internal destination could not be resolved', detail: 'The link to "Section 3.2" points to a named destination that does not exist in the source PDF.', next: 'No action required. The link text is kept; the link target is removed.', action: 'Open link on page 6' },
]

export const stages = ['Reading document structure', 'Detecting tables and formulas', 'Translating text blocks', 'Fitting text to layout', 'Writing output PDF']

export const recents = [
  { name: 'Research-Paper.pdf', pages: 6, when: 'Today, 09:42', status: 'review' as const, path: '~/Documents/Papers' },
  { name: 'Thermal-Analysis-Report.pdf', pages: 48, when: 'Yesterday', status: 'done' as const, path: '~/Documents/Work' },
  { name: 'Lecture-07-Signals.pdf', pages: 22, when: '12 May', status: 'failed' as const, path: '~/Downloads' },
]

export const languages = ['English', 'Vietnamese', 'German', 'French', 'Japanese', 'Spanish', 'Chinese (Simplified)']
