# Research: vì sao `@requesting-code-review` chậm

Phạm vi: chỉ primary sources, không sửa code. Ngày đo: 2026-10-09.

## 1. File thực tế: tracked ít, disk nhiều

- Tracked 174 files (`(git ls-files | Measure-Object -Line).Lines` → 174).
- Worktree sạch: `(git status --porcelain=v1 --untracked-files=all | Measure-Object).Lines` → 0.
- Disk 23407 files (`Get-ChildItem -Recurse -File -Force | Measure-Object`).
- Trong đó `.venv/` 23085 files (`Get-ChildItem .venv -Recurse -File -Force`); `build/` và `output/` không tồn tại (`Test-Path` → no-build/no-output).
- Ignored 23157 entries (`git status --porcelain=v1 --ignored`, top là `!! .venv/...`).
- `.gitignore:1,8,10-11` đã ignore `.venv/`, `output/`, `tmp/`, `dist/`, `build/` — nhưng reviewer không exclude vẫn quét disk.
- `tests/` có 19 files (`Get-ChildItem tests -File`); `def test_` đếm được 252 (`Select-String -Path tests/*.py -Pattern 'def test_'`).

## 2. Gate nặng trong agent-knowledge

- `AGENTS.md:16-18`: trước handoff chạy full `unittest` + `pip check` + Ruff hard-error + PDF render QA proportionate.
- `agent-knowledge/repository.md:6`: badge `Tests-219_Passed`; `:31,42` lệnh `python -m unittest discover -s tests -v`.
- `agent-knowledge/validation.md:13-20`: gate = `unittest discover -s tests -v` + `pip check` + `ruff check pdf2zh scripts app tests --select E9,F63,F7,F82` + `git diff --check` + `app/gui.py --smoke-test` + packaged `--smoke-test` exit 0.
- `agent-knowledge/validation.md:24-35`: PDF gate render mọi page, contact sheet, check `{vN}/<bN>/<sN>/U+0000/U+FFFD`, span-box vs canvas, cell-text vs cell-boundary.
- `agent-knowledge/pdf-engine.md:86-89`: large = 200 pages/50 MiB; light serialization `garbage=1`, no subset — render + serialize tốn GIL hàng chục giây.
- `agent-knowledge/regressions.md:45-46`: guard mới phải có unit test geometry nhỏ nhất + validate visual tài liệu thật.

## 3. So sánh 2 skill review

- `requesting-code-review/SKILL.md:28-29`: mặc định `BASE_SHA=$(git rev-parse HEAD~1)`, comment `# or: git merge-base origin/main HEAD`.
- `requesting-code-review/code-reviewer.md:29-31`: chạy cả `git diff --stat [BASE]..[HEAD]` và full `git diff [BASE]..[HEAD]` (two-dot, không merge-base).
- `code-review/SKILL.md:21`: dùng `git diff <fixed-point>...HEAD` (three-dot = so với merge-base) + `git log <fixed-point>..HEAD --oneline`.
- Scope `code-reviewer.md:63-93` rộng: plan-alignment + quality + architecture + testing + production-readiness (migration, backward-compat, docs).
- `code-reviewer.md:83-87`: mục Testing hỏi `All tests passing?` — kéo theo gate mục 2 ở trên.
- `code-review/SKILL.md:62-72`: mỗi sub-agent giới hạn `Under 400 words`, aggregate không rerank (`:78-80`).
- `code-reviewer.md:54-61`: cấm dispatch subagent tiếp, review nhiều pass tự thân — 1 agent ôm full diff.

## 4. Guard còn thiếu trong template requesting

- Không có guard empty-diff: `code-review/SKILL.md:23` yêu cầu `rev-parse` + diff non-empty, fail sớm; `code-reviewer.md` không có đoạn này.
- Không exclude binary/generated: `code-reviewer.md:29-31` không có `-- . ':!*.pdf' ':!*.onnx'` hay `git diff --numstat` lọc binary; repo có PDF/model/font (`repository.md:11,18-19`, `.gitignore:13-15,26`).
- Không giới hạn context: không có `stat`-first-then-hunk, không cap từ như `code-review` 400 từ.
