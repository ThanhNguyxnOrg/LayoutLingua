# Research: OpenAI-Compatible Protocol Standardization & Local LLM Unification

**Date:** 2026-10-16  
**Status:** Validated  
**References:**
- OpenAI API Reference: `/v1/chat/completions`, `/v1/models` ([OpenAI API Spec](https://github.com/openai/openai-openapi))
- Ollama API Documentation: OpenAI Compatibility layer at `http://localhost:11434/v1` ([Ollama Docs](https://github.com/ollama/ollama/blob/main/docs/openai.md))
- LM Studio Local Server Documentation: OpenAI API compatibility at `http://localhost:1234/v1`
- vLLM Documentation: OpenAI-Compatible Server (`vllm.entrypoints.openai.api_server`)
- SOTA Open-Source Translation Tools: `pdf2zh`, `BabelDOC`, LibreChat, OpenWebUI

---

## 1. Executive Summary

### The Problem
1. **Brittle String-Matching Fallback:** The backend currently inspects substrings in `base_url` (`if "deepseek" in b_low ... else "gpt-4o-mini"`). This breaks for local reverse proxies, custom ports, LM Studio (`localhost:1234`), vLLM (`localhost:8000`), or enterprise gateways, causing silent failures by sending requests for non-existent models (e.g. requesting `gpt-4o-mini` from an Ollama instance).
2. **Duplicate Local vs. Cloud Provider Architecture:** Ollama, LM Studio, and vLLM implement the standard **OpenAI `/v1` REST specification** (`/v1/chat/completions` and `/v1/models`). Maintaining separate `ollama` and `openai` provider types creates redundant configuration fields (`ollamaEndpoint`, `ollamaModel` vs `openaiEndpoint`, `openaiModel`), confusing dual dropdown entries, and desynchronization between settings and workspace.

---

## 2. Technical Findings

### 2.1 Ollama is 100% OpenAI-Compatible
Ollama provides built-in compatibility without any extra middleware:
- **Base URL:** `http://localhost:11434/v1`
- **Chat Endpoint:** `POST /v1/chat/completions`
- **Models Endpoint:** `GET /v1/models` (returns `{"data": [{"id": "llama3.2:latest", "object": "model"}, ...]}`)
- **Authorization:** Accepts any dummy token or empty key (e.g., `Authorization: Bearer ollama`).

Similarly:
- **LM Studio:** `http://localhost:1234/v1`
- **vLLM:** `http://localhost:8000/v1`
- **LocalAI:** `http://localhost:8080/v1`
- **DeepSeek:** `https://api.deepseek.com/v1`
- **Groq:** `https://api.groq.com/openai/v1`
- **OpenRouter:** `https://openrouter.ai/api/v1`

All of these can be served identically by `OpenAITranslationProvider(base_url, api_key, model_id)`.

### 2.2 SOTA Open-Source Patterns (pdf2zh, BabelDOC, OpenWebUI)
1. **Dynamic Model Discovery (`/v1/models`):** Instead of guessing model names, tools call `GET {base_url}/models` using the provided API key (or empty for local servers). The returned list populates the UI model dropdown.
2. **Explicit User Selection with Presets:** The UI provides 1-click presets for common providers (Ollama, LM Studio, DeepSeek, Groq, OpenAI) that pre-fill the `base_url`, default `model_id`, and dummy API key if local.
3. **Graceful Fallback:** If `/models` fails (e.g. offline server or strict CORS), the user can directly type any custom model ID in a text input. Backend does not overwrite the user's model ID with hardcoded substring guesses.

---

## 3. Recommended Architecture

### Consolidated Provider Matrix (4 Clean Providers)
1. **Google Translate RPC** (`google`): Zero setup, 100% free neural MT, no keys or local setup required.
2. **Universal LLM / OpenAI-Compatible** (`openai`): Unifies ALL cloud and local LLMs (Ollama, LM Studio, DeepSeek, Groq, OpenAI, OpenRouter, Qwen). Powered by 1-click presets and dynamic `/models` auto-discovery.
3. **Google AI Studio** (`gemini`): Direct Gemini SDK (`gemini-2.5-flash` free tier keys).
4. **Argos Translate** (`argos`): Embedded offline CTranslate2 model (no local server or external processes needed).

### Data Flow & Synchronization
```
[User Settings / Workspace]
       │
       ▼
[Provider Selection]
├── 'google'  ──► GoogleRpcTranslationProvider()
├── 'gemini'  ──► GeminiTranslationProvider(api_key, model_id)
├── 'openai'  ──► OpenAITranslationProvider(base_url, api_key, model_id)
│                  ▲
│                  ├── Presets: Ollama (localhost:11434/v1), LM Studio, DeepSeek, Groq, OpenAI...
│                  └── Dynamic /api/models discovery button
└── 'argos'   ──► ArgosTranslationProvider()
```
