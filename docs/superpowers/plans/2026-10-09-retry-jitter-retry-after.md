# Retry Jitter + Retry-After Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop 4 worker threads from retrying in lockstep and honor server-sent `Retry-After` on 429/503.

**Architecture:** Replace the fixed exponential wait on `request_translation` with a jittered wait plus a custom `Retry-After`-reading wait composed via tenacity primitives. Pure wait-strategy change: no touch to batching, breaker, cache, or typesetting.

**Tech Stack:** Python 3.12, tenacity 9.1.4 (`wait_exponential_jitter`, `wait_combine`), stdlib `email.utils` for HTTP-date parsing.

**Spec:** `docs/research-followup-optimizations.md` R1 (jitter + `Retry-After`, keep retry-4 + transient-only + breaker). Preservation contract `references/preservation-rules.md` (fail-closed, keep source + report reason).

## Global Constraints

- Python 3.12, repo venv `.venv`; style: four spaces, annotations, `snake_case`, `pathlib.Path`.
- `pdf2zh/` changes stay small and carry a regression test per `AGENTS.md:14-15`.
- No commit/push/merge/tag without explicit user authorization (`AGENTS.md:19`); plan commit steps below are SKIPPED, changes stay in working tree.
- Retry budget stays 4 attempts, transient-only (`_is_transient_translation_error`), breaker untouched.
- Fail-closed: any wait/parser error must fall back to exponential, never to skipping the retry or dropping the segment.

## Review Focus

- A 429 with `Retry-After: 120` while the breaker trips at 5 consecutive 429s: a reasonable person expects the wait to sleep ~120s OR the breaker to fail fast first — pin which wins.
- A garbage `Retry-After: banana` header: expect plain exponential fallback, no crash.
- An HTTP-date in the past: expect no negative sleep (clamp to exponential).
- Two threads hitting 429 at once: expect sleeps to differ (jitter), not lockstep.
- A BREAK in wait composition that silently drops the exponential floor: expect every path to wait at least the jittered exponential.

---
### Task 1: Jittered exponential wait on `request_translation`

**Files:**
- Modify: `pdf2zh/converter.py` (retry decorator on `request_translation`, ~line 1095)
- Test: `tests/test_perf_guards.py` (`TestRetryWaits`)

**Interfaces:**
- Consumes: tenacity `wait_exponential_jitter`, existing `stop_after_attempt(4)`, `retry_if_exception(_is_transient_translation_error)`.
- Produces: `request_translation` retry wait = `wait_exponential_jitter(initial=1, max=60, jitter=2)` — same ceiling/floor as today plus up to 2s jitter.

- [ ] **Step 1: Write the failing test**

```python
def test_retry_wait_has_jitter(self):
    import pdf2zh.converter as converter_module
    import inspect
    source = inspect.getsource(converter_module)
    self.assertIn("wait_exponential_jitter", source)
    self.assertNotIn("wait=wait_exponential(", source)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_perf_guards.TestRetryWaits.test_retry_wait_has_jitter -v`
Expected: FAIL with assertion on `wait_exponential_jitter`

- [ ] **Step 3: Implement in `pdf2zh/converter.py`**

Swap the tenacity import `wait_exponential` → `wait_exponential_jitter` and the decorator to `wait=wait_exponential_jitter(initial=1, max=60, jitter=2)`. One import line + one wait line, nothing else.

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_perf_guards.TestRetryWaits -v`
Expected: PASS

- [ ] **Step 5: Commit**

SKIPPED per Global Constraints (no authorization). Leave in working tree.

### Task 2: `Retry-After`-honoring wait composed with the jittered wait

**Files:**
- Modify: `pdf2zh/converter.py` (new `_retry_after_seconds(exc)` + wait class near `_is_transient_translation_error`)
- Test: `tests/test_perf_guards.py` (`TestRetryWaits`)

**Interfaces:**
- Consumes: tenacity `wait_base` subclass protocol (`__call__(self, retry_state) -> float`), `wait_combine`, Task 1 jitter wait.
- Produces: `_retry_after_seconds(exc: BaseException) -> float | None` — seconds from `exc.response.headers["Retry-After"]` (delta-seconds or HTTP-date, clamped to `[0, 60]`), `None` when absent/unparsable; decorator wait = `wait_combine(_RetryAfterWait(), wait_exponential_jitter(initial=1, max=60, jitter=2))` — tenacity takes the max, so server guidance wins but the exponential floor always applies.

- [ ] **Step 1: Write the failing tests**

```python
def test_retry_after_delta_seconds(self):
    exc = SimpleNamespace(response=SimpleNamespace(headers={"Retry-After": "120"}, status_code=429))
    self.assertEqual(_retry_after_seconds(exc), 60.0)

def test_retry_after_garbage_falls_back(self):
    exc = SimpleNamespace(response=SimpleNamespace(headers={"Retry-After": "banana"}, status_code=429))
    self.assertIsNone(_retry_after_seconds(exc))

def test_retry_after_missing_is_none(self):
    self.assertIsNone(_retry_after_seconds(ValueError("nope")))

def test_breaker_wins_over_wait(self):
    from pdf2zh.translator import CircuitOpenError
    self.assertFalse(_is_transient_translation_error(CircuitOpenError("blocked")))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_perf_guards.TestRetryWaits -v`
Expected: FAIL with "not defined" (`_retry_after_seconds`); `test_breaker_wins_over_wait` already PASSES (pins existing breaker-wins behavior, kept as documentation)

- [ ] **Step 3: Implement `_retry_after_seconds(exc) -> float | None` + `_RetryAfterWait(wait_base)` in `pdf2zh/converter.py`**

Parse with `int()` first, then `email.utils.parsedate_to_datetime` minus `datetime.now(timezone.utc)`, clamp `[0, 60]`, `None` on any failure. Wait class returns the parsed value or `0.0` (so `wait_combine` max falls through to the jittered exponential). Import: `from email.utils import parsedate_to_datetime`, `from datetime import datetime, timezone`, `from tenacity.wait import wait_base`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_perf_guards.TestRetryWaits -v`
Expected: PASS

- [ ] **Step 5: Full suite + gates**

Run: `.\.venv\Scripts\python.exe -m unittest discover -s tests`, `ruff check pdf2zh tests --select E9,F63,F7,F82`, `git diff --check`
Expected: all green

- [ ] **Step 6: Commit**

SKIPPED per Global Constraints (no authorization). Leave in working tree.
