# Tách cột không viền (trang ký hiệu toán 3 cột)

Case: 1 box `plain-text` phủ 3 cột (ký hiệu | mô tả | ví dụ), `find_tables`=0,
grouper nối ngang → reflow chồng chữ. Model DocLayNet không tách cụm từ không lưới.

## 1. Vì sao hỏng (mã hiện tại)

- `high_level.py:500` — box `plain-text` (non-vcls) sơn nguyên vùng, không cắt dọc nội bộ.
- `converter.py:842` — `vmax = width/4`: từ cột 2/3 cách xa vẫn cùng `cls` → nối `x0 > xt.x1+1` bằng space.
- `converter.py:288` — `line_ends_paragraph` ratio 0.75 so với **cả box rộng**: dòng đủ cột hẹp vẫn "dài" → không ngắt.
- `reading_order.py:42` — `detect_column_gutters` chỉ tìm **1 split 2 cột** giữa 35–65% trang, cân bằng mỗi bên ≥2 box; trang 3 cột rớt → fallback 1 cột, sai thứ tự đọc.
- `high_level.py:549,561` — `find_tables`=0 → `matching_table_cells` (gate overlap ≥0.5, `rules.py:332`) không có cell → `cluster_table_words` không bao giờ chạy.

## 2. Thuật toán tách cột không viền (đề xuất, chỉ áp cho box `plain-text`)

1. Histogram x trên `page_words` trong box (dùng `get_text("words")` như `high_level.py:560`): dải trắng dọc = gutter ứng viên.
2. Ngưỡng khe: rộng ≥ `max(12pt, 2.5 × median glyph width)` (~12–15pt ở cỡ 10pt). Gốc: `reading_order` `min_gutter_width=12.0`, `tables.py:100` cụm cột `12.0`, cụm từ `max(3.0, 0.6×median height)` (`rules.py:431`); khe cột phải lớn hẳn khe từ.
3. Điều kiện 2 bên chồng dọc: mỗi bên có chữ phủ chồng nhau ≥60% chiều cao box (BabelDOC `bbox_overlap`, `paragraph_finder.py:100`; Surya/layoutreader cùng nguyên tắc quan hệ không gian).
4. XY-cut đệ quy theo slice: cắt ngang khối spanning trước (quy ước repo: rộng >70% trang, `reading_order.py:59,129`), rồi mới cắt dọc từng slice — tiêu đề/figure không bị chém.
5. Công thức stacked xen giữa: cặp chữ chồng x ≥0.6, khe tâm `2 < gap ≤ 1.5×max height` (`rules.py:312`) bắc qua gutter → coi như spanning, bỏ gutter đó (kế thừa `formula_regions` + `stacked_exclusions`, `high_level.py:608`).
6. BabelDOC tham chiếu: đổi layout-id → đoạn mới (`paragraph_finder.py:197`); xuống dòng khi `curr.y2 < prev.y` hoặc lùi trái >10×char width (`layout_helper.py:73`); khe từ = khoảng distinct thứ 2 (`get_char_unicode_string`) — luôn tương đối theo median, không pt tuyệt đối.

## 3. `cluster_table_words` / `matching_table_cells` làm được gì

- `matching_table_cells`: chỉ chọn cell PyMuPDF giải thích được ≥50% vùng model-table; bảng không lưới → rỗng, giữ bảo vệ toàn bảng (đúng).
- `cluster_table_words`: tách cell gộp thành cụm x (mô tả + mã phải), biên chia đôi khoảng trống (`rules.py:467`); chỉ chạy **trong cell đã match** (`high_level.py:575`) — không cứu được trang `find_tables`=0.
- Kết luận: tái dùng ý tưởng (ngưỡng tương đối + chia đôi khe) cho splitter mới, không nhét trang này vào path table-grid.

## 4. Ngưỡng an toàn (không tách nhầm văn xuôi 1 cột / 2 cột báo chí)

- Chỉ xét box rộng >2.5× median dòng trang (BabelDOC `median_width`, `paragraph_finder.py:369`; repo `0.75` ở `converter.py:288` là analog hẹp hơn).
- Mỗi cột ≥6 dòng và ≥4 từ (trên `min_box_count=4`, mỗi bên ≥2 của `reading_order.py:45,86`); phủ dọc chồng ≥50–60% box.
- Gutter phải "sạch": không quá 5% box cắt qua (`min_intersections ≤5%`, `reading_order.py:82`); 3 cột = 2 gutter đều đạt.
- Văn xuôi 1 cột thụt đầu dòng/khoảng từ lớn không đạt khe sạch + phủ 2 bên → giữ nguyên.

## 5. File chạm + constraint

- Chạm: `high_level.py` (cắt box `plain-text` trước khi sơn `box[...]=i+2`), `reading_order.py` (mở `detect_column_gutters` 1→N gutter); có thể helper mới, không sửa `converter.py` (`vmax`, `line_ends_paragraph` giữ nguyên).
- Không đụng: path table-grid (`find_tables`, gate 0.5, cụm hàng/dọc `6.0/12.0` ở `tables.py:99`); placeholder `{vN}`/`<s1..3>` + validate translator; font (không subset, giữ dingbat/ngoại lệ `vflag`).
