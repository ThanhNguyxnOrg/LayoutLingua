# ADR 0002: Persistent Segment Translation Cache and Graceful Failover

## Status
Accepted

## Context
Translating multi-page technical and scientific documents (such as 50–100+ page books like `Sotaytoanhoc.pdf`) involves thousands of translatable text segments containing mathematical formula placeholders.

Under real-world operation, long document translations are vulnerable to:
1. **Public Endpoint Rate Limiting (HTTP 429)**: Free providers (such as Google Translate RPC) enforce IP-level request rate limits when subjected to large batches.
2. **Session Interruptions**: Desktop application closes, power loss, or intentional user cancellation midway through a large document.
3. **Redundant Network & Financial Costs**: Without persistent caching, re-running a cancelled or interrupted document from the beginning re-translates previously completed segments, generating unnecessary API requests and risking repeat IP bans.

Open-source analysis (`BilingualBookMaker`, `BabelDOC`, `pdf2zh`) demonstrates that resilient document translation engines must decouple text translation persistence from in-memory session lifecycles.

## Decision

1. **Storage Mechanism (Local SQLite Store)**:
   - Implement an embedded SQLite database (`layoutlingua_translations.db`) located in the platform-standard user application data directory (`platformdirs.user_cache_dir("layoutlingua")`).
   - Store entries indexed by a deterministic SHA-256 fingerprint:
     `fingerprint = sha256(f"{source_lang}:{target_lang}:{provider_model}:{masked_text}".encode("utf-8")).hexdigest()`
   - Fields: `fingerprint` (PRIMARY KEY), `source_lang`, `target_lang`, `provider_model`, `source_text`, `translated_text`, `created_at`.
   - *Rationale*: SQLite offers ACID safety, zero-dependency deployment (standard library `sqlite3`), robust concurrent access via WAL mode, and sub-millisecond query latency.

2. **Seam Placement (Deep Module Decorator at `BaseTranslationProvider`)**:
   - Create `CachedTranslationProvider` implementing `BaseTranslationProvider` in `layoutlingua/translation/cache.py`.
   - The interface remains strictly identical:
     `translate_batch(request: BatchTranslationRequest) -> BatchTranslationResult`
   - *Internal Logic*:
     - Check incoming segments against SQLite cache in a single batch query.
     - Segments found in cache are immediately fulfilled as cache hits.
     - Only cache misses are forwarded to the underlying provider (`GoogleRpcTranslationProvider`, `OpenAITranslationProvider`, etc.).
     - Newly translated segments from the underlying provider are committed to SQLite in a single transaction.
   - *Rationale*: Adheres to Deep Module principles—the caller (`server.py`, CLI) requires zero knowledge of SQLite or cache internals. All 165 existing unit/integration tests remain 100% green without modification.

3. **Graceful Failover Policy**:
   - If a provider encounters a rate limit (HTTP 429) or connection failure:
     - All segments translated before the error are already safely persisted to disk.
     - If the user has configured alternate credentials (e.g. Gemini or Groq/OpenAI), failover can resume instantly, querying the cache for existing pages and calling the new provider only for remaining un-translated segments.
     - If no secondary credentials exist, the engine fails fast, reports the rate limit clearly, and preserves the document state without destructive loss.

## Consequences

- **Positive**:
  - **Instantaneous Resume**: Resuming or retrying an interrupted document resolves cached pages in < 0.1s with 0 HTTP requests.
  - **Rate Limit Immunity on Re-runs**: Once a page is translated, it will never trigger another Google RPC request, even across server restarts.
  - **Zero Caller Complexity**: Existing translation callers use standard `provider.translate_batch()` unchanged.
  - **Auditability**: Translated corpus can be inspected and cleared via standard SQLite tools.
- **Negative / Trade-offs**:
  - Requires maintaining a small SQLite file on disk (~5–10 MB for hundreds of books). Automatic LRU or age-based pruning can be added if storage constraints arise.
