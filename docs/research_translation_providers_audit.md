# Research: In-Depth Audit and Resilience Architecture for Translation Providers

## Executive Summary

This research investigates the root causes of failures across LayoutLingua's translation provider adapters (**Google RPC Free**, **Google Gemini**, and **OpenAI-Compatible / Local LLM**). By cross-referencing industry standards and leading open-source layout-preserving document translation engines (**`pdf2zh` / `PDFMathTranslate`**, **`funstory-ai/BabelDOC`**, **`deep-translator`**, and **`googletrans`**), this document details the engineering flaws currently causing translation drops, quota blocks, and silent crashes, along with proven architectural remediations.

---

## 1. Provider Audit & Root Cause Analysis

### 1.1 Google RPC (Free Web MT Provider)

#### Failure Mode Observed
- Intermittent HTTP `414 Request-URI Too Large`, HTTP `400 Bad Request`, or dropped TCP connections during large multi-segment translation batches.
- The UI stalls on Page 1 or reports a rate-limit error even on modest documents.

#### Primary Source Audit & Comparison
- **LayoutLingua Current Implementation (`layoutlingua/translation/google_rpc.py`)**:
  - Encodes the joined segment batch as a URL query parameter:
    ```python
    url = f"https://{host}/translate_a/single?client={client}&sl={s_lang}&tl={t_lang}&dt=t&q={encoded}"
    req = urllib.request.Request(url, ...)
    ```
  - For 25–35 academic segments (with LaTeX placeholder tokens like `<b0></b0>` and academic terms), the URL routinely reaches **4,000–8,000 characters**.
  - Google Frontend (GFE) reverse proxies strictly limit HTTP GET request URIs to ~2KB–4KB. When exceeded, GFE immediately returns HTTP 414 or abruptly terminates the connection.

- **Open-Source Reference Implementations (`deep-translator`, `pdf2zh`, Chromium Extension RPC)**:
  - Open-source libraries send **HTTP POST** with an `application/x-www-form-urlencoded` body:
    ```python
    data = urllib.parse.urlencode({"client": "gtx", "sl": s_lang, "tl": t_lang, "dt": "t", "q": text}).encode("utf-8")
    req = urllib.request.Request("https://translate.googleapis.com/translate_a/single", data=data, headers={"User-Agent": "Mozilla/5.0"})
    ```
  - **POST bodies have NO URL length limits**, preventing HTTP 414 entirely.
  - Multi-client fallback pool: Alternating between `client=gtx` and `client=dict-chrome-ex` isolates quota pools, dramatically reducing 429 rate-limiting.

---

### 1.2 Google Gemini Provider

#### Failure Mode Observed
- Attempting to translate with Gemini displays:
  `GEMINI stopped responding: The provider returned an error on page 1`.

#### Primary Source Audit & Comparison
- **Missing Dependency**:
  - `layoutlingua/translation/gemini.py` strictly attempts `from google import genai`.
  - The Python environment does not have `google-genai` installed (`ModuleNotFoundError: No module named 'google.genai'`).
  - This raises an uncaught `ProviderUnavailableError`, causing the background worker to fail immediately on page 1.
- **Model Name Fragility**:
  - When users enter unreleased, experimental, or mistyped model names (such as `gemini-3.5-flash-lite`), Gemini API returns HTTP 404 (`Model not found`).
  - Without alias normalization, this crashes the entire document session.
- **Open-Source Architectural Pattern**:
  - Official Google Gemini Developer API natively exposes three interoperable interfaces:
    1. **Google GenAI SDK** (`google-genai`).
    2. **OpenAI Compatibility Layer**: Base URL `https://generativelanguage.googleapis.com/v1beta/openai/` accepting standard OpenAI API clients (which *is* installed in this repo).
    3. **Zero-Dependency Direct REST**: POST to `https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}` using Python standard library `urllib.request`.
  - By implementing a **Tri-Mode Fallback Adapter** (SDK → OpenAI Client → Direct REST), Gemini works 100% out of the box with zero missing package errors.

---

### 1.3 OpenAI-Compatible & Local LLMs (DeepSeek, Groq, Ollama)

#### Failure Mode Observed
- Missing granular error feedback when endpoints reject API keys or rate-limit requests.
- The UI displayed generic fallback text (`The provider returned an error on page 1`) instead of specific API error codes (e.g., `401 Unauthorized: Invalid API Key` or `404 Model Not Found`).

#### Primary Source Audit & Comparison
- Standard OpenAI API specifications return structured error objects:
  ```json
  {"error": {"message": "Invalid API key", "type": "invalid_request_error", "code": "invalid_api_key"}}
  ```
- Catching and propagating the exact `message` field from the error payload directly to `session["progress"]["message"]` and rendering it in the UI allows users to immediately fix configuration issues.

---

## 2. Proposed Architecture & Remediation Strategy

| Provider | Root Cause | Remediation (Based on Open-Source Best Practices) |
| :--- | :--- | :--- |
| **Google RPC (Free)** | HTTP GET query string overflow (>4KB) causing HTTP 414 / 400. | Switch to **HTTP POST** with urlencoded body; rotate between `gtx` and `dict-chrome-ex` clients; retry on 429 with jitter. |
| **Gemini** | `google-genai` SDK missing; invalid model names crash with 404. | Implement **Tri-Mode Adapter** (SDK → OpenAI Client → Native REST); add model alias normalization (`gemini-3.5-flash-lite` → `gemini-2.5-flash`). |
| **OpenAI / LLMs** | Generic error messages in UI. | Surface exact upstream API error message in desktop UI `StateNotice`. |
