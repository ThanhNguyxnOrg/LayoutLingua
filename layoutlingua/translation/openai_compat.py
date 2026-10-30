"""OpenAI-compatible translation provider adapter for DeepSeek, OpenAI, Groq, and Ollama."""

from __future__ import annotations

import json
import re
from typing import Any

from layoutlingua.translation.errors import (
    AuthenticationError,
    InvalidTranslationResponseError,
    ModelUnavailableError,
    ProviderUnavailableError,
    QuotaExceededError,
    RateLimitError,
)
from layoutlingua.translation.models import (
    BatchTranslationRequest,
    BatchTranslationResult,
    ProviderCapabilities,
)
from layoutlingua.translation.provider import BaseTranslationProvider

_TAGGED_SEGMENT_REGEX = re.compile(r"<segment\s+id=[\"'](.*?)[\"']>(.*?)</segment>", re.DOTALL)


class OpenAITranslationProvider(BaseTranslationProvider):
    """Adapter for any OpenAI-compatible API endpoint with capability negotiation."""

    def __init__(
        self,
        api_key: str,
        model_id: str,
        base_url: str = "https://api.openai.com/v1",
        supports_structured_json: bool = False,
        timeout: float = 60.0,
        client: Any | None = None,
    ) -> None:
        key = (api_key or "").strip()
        if not key:
            # Local endpoints (Ollama, LM Studio, vLLM) do not require authentication
            key = "ollama"
        clean_base = (base_url or "https://api.openai.com/v1").rstrip("/")
        mid = (model_id or "").strip()
        if not mid:
            b_low = clean_base.lower()
            if "deepseek" in b_low:
                mid = "deepseek-chat"
            elif "groq" in b_low:
                mid = "llama-3.3-70b-versatile"
            elif "openrouter" in b_low:
                mid = "openai/gpt-4o-mini"
            elif "ollama" in b_low or ":11434" in b_low:
                mid = "llama3.2"
            elif "dashscope" in b_low or "aliyun" in b_low:
                mid = "qwen-plus"
            else:
                mid = "gpt-4o-mini"

        self._api_key = key
        self._model_id = mid
        self._base_url = clean_base
        # User constraint: supports_structured_json defaults to False for custom endpoints
        self._supports_structured_json = supports_structured_json
        self._timeout = timeout
        self._client = client

        self._capabilities = ProviderCapabilities(
            supports_structured_json=self._supports_structured_json,
            requires_data_use_consent=False,
            tier="byok",
            policy_version="1.0",
            max_batch_segments=25,
            max_batch_chars=12000,
            requests_per_minute=60.0,
        )

    @property
    def name(self) -> str:
        return "openai-compatible"

    @property
    def model(self) -> str:
        return self._model_id

    @property
    def capabilities(self) -> ProviderCapabilities:
        return self._capabilities

    def _get_client(self) -> Any:
        """Lazily initialize OpenAI SDK client if installed, else zero-dependency native_rest."""
        if self._client is not None:
            return self._client

        try:
            from openai import OpenAI  # type: ignore

            self._client = OpenAI(
                api_key=self._api_key,
                base_url=self._base_url,
                timeout=self._timeout,
            )
            return self._client
        except ImportError:
            # Zero-dependency standard library urllib.request fallback
            self._client = "native_rest"
            return self._client

    def list_remote_models(self) -> list[str]:
        """Optional model discovery via GET /models endpoint if supported."""
        client = self._get_client()
        try:
            if hasattr(client, "models") and hasattr(client.models, "list"):
                resp = client.models.list()
                data = getattr(resp, "data", [])
                return [m.id for m in data if hasattr(m, "id")]
            if client == "native_rest":
                import urllib.request

                headers = {"User-Agent": "LayoutLingua/2.0"}
                if self._api_key and self._api_key != "ollama":
                    headers["Authorization"] = f"Bearer {self._api_key}"
                req = urllib.request.Request(f"{self._base_url}/models", headers=headers)
                with urllib.request.urlopen(req, timeout=min(self._timeout, 10.0)) as resp:
                    payload = json.loads(resp.read().decode("utf-8"))
                    items = payload.get("data", []) if isinstance(payload, dict) else []
                    return [str(m.get("id")) for m in items if isinstance(m, dict) and m.get("id")]
            return []
        except Exception:
            return []

    def translate_batch(self, request: BatchTranslationRequest) -> BatchTranslationResult:
        """Dispatch batch translation request to OpenAI-compatible endpoint."""
        if not request.segments:
            return BatchTranslationResult(translations={})

        client = self._get_client()
        src_lang = request.source_language if (request.source_language and request.source_language != "auto") else "the source language"

        system_instruction = (
            f"You are a professional academic and technical document translator.\n"
            f"Translate the following segments from {src_lang} to {request.target_language}.\n"
            f"Strict invariants:\n"
            f"1. Never modify, omit, or translate formula placeholder tokens: ⟦LL_FORMULA_XXXX⟧, <b0></b0>, <b1></b1>, ⟦CIT_0⟧, ⟦ABBR_0⟧, or ⟦M0⟧.\n"
            f"2. Keep the exact token ID, XML tags (<b0></b0>), and brackets unchanged in their appropriate grammatical position.\n"
            f"3. Return the exact segment IDs provided.\n"
        )

        use_json = self._supports_structured_json

        # Try execution with structured output if enabled
        try:
            response_text = self._dispatch_with_format(client, request, system_instruction, use_json)
        except Exception as e:
            # Conditional fallback: ONLY fallback if error explicitly indicates unsupported format
            err_str = str(e).lower()
            unsupported_markers = (
                "response_format",
                "json_object",
                "json schema",
                "structured outputs",
                "unrecognized parameter",
                "unsupported parameter",
            )
            if use_json and any(m in err_str for m in unsupported_markers):
                # Downgrade and retry with tagged format
                self._supports_structured_json = False
                try:
                    response_text = self._dispatch_with_format(client, request, system_instruction, False)
                except Exception as retry_exc:
                    self._map_and_raise_error(retry_exc)
            else:
                self._map_and_raise_error(e)

        # Parse translated output
        translations = self._parse_response(response_text, [s.segment_id for s in request.segments])
        return BatchTranslationResult(translations=translations)

    def _dispatch_with_format(
        self,
        client: Any,
        request: BatchTranslationRequest,
        system_instruction: str,
        use_json: bool,
    ) -> str:
        """Execute chat completion call with or without json_object response format."""
        if use_json:
            user_content = json.dumps(
                [{"id": s.segment_id, "text": s.masked_text} for s in request.segments],
                ensure_ascii=False,
            )
            prompt = (
                f"Input segments to translate (JSON array):\n{user_content}\n"
                f"Respond with a JSON object containing a 'translations' key mapping list of objects "
                f"with 'id' and 'text'."
            )
        else:
            tagged_content = "\n".join(
                f'<segment id="{s.segment_id}">{s.masked_text}</segment>'
                for s in request.segments
            )
            prompt = (
                f"Input segments to translate:\n{tagged_content}\n"
                f"Respond using the exact XML tags: <segment id=\"...\">translated text</segment> for each segment."
            )

        messages = [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": prompt},
        ]

        if hasattr(client, "chat") and hasattr(client.chat, "completions"):
            kwargs: dict[str, Any] = {
                "model": self.model,
                "messages": messages,
                "temperature": 0.0,
            }
            if use_json:
                kwargs["response_format"] = {"type": "json_object"}

            resp = client.chat.completions.create(**kwargs)
            if resp.choices and resp.choices[0].message and resp.choices[0].message.content:
                return resp.choices[0].message.content
            raise InvalidTranslationResponseError("Empty response received from OpenAI endpoint.")

        if client == "native_rest":
            import urllib.request
            import urllib.error

            url = f"{self._base_url}/chat/completions"
            payload: dict[str, Any] = {
                "model": self.model,
                "messages": messages,
                "temperature": 0.0,
            }
            if use_json:
                payload["response_format"] = {"type": "json_object"}

            headers: dict[str, str] = {
                "Content-Type": "application/json",
                "User-Agent": "LayoutLingua/2.0",
            }
            if self._api_key and self._api_key != "ollama":
                headers["Authorization"] = f"Bearer {self._api_key}"

            req_bytes = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(url, data=req_bytes, headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    choices = data.get("choices", []) if isinstance(data, dict) else []
                    if choices and isinstance(choices[0], dict):
                        msg = choices[0].get("message", {})
                        content = msg.get("content") if isinstance(msg, dict) else None
                        if content:
                            return str(content)
                    raise InvalidTranslationResponseError(
                        f"Empty or unexpected response received from OpenAI endpoint: {data}"
                    )
            except urllib.error.HTTPError as he:
                body = ""
                try:
                    body = he.read().decode("utf-8", errors="replace")
                except Exception:
                    pass
                err = RuntimeError(f"HTTP {he.code}: {body or he.reason}")
                setattr(err, "status_code", he.code)
                raise err from he

        # Callable mock fallback for testing
        if callable(client):
            return str(client(messages, use_json))

        raise ProviderUnavailableError("Invalid OpenAI client handle.")

    def _parse_response(self, text: str, expected_ids: list[str]) -> dict[str, str]:
        """Parse structured JSON or tagged block translations from LLM response."""
        from layoutlingua.translation.google_rpc import _sanitize_translated_tokens

        results: dict[str, str] = {}

        # 1. Try JSON parsing
        clean_text = text.strip()
        if clean_text.startswith("```json"):
            clean_text = clean_text[7:]
        if clean_text.startswith("```"):
            clean_text = clean_text[3:]
        if clean_text.endswith("```"):
            clean_text = clean_text[:-3]
        clean_text = clean_text.strip()

        try:
            data = json.loads(clean_text)
            if isinstance(data, dict):
                items = (
                    data.get("translations")
                    or data.get("segments")
                    or data.get("results")
                    or data.get("data")
                )
                if isinstance(items, list):
                    for item in items:
                        if isinstance(item, dict):
                            sid = item.get("id") or item.get("segment_id")
                            val = item.get("text") if "text" in item else item.get("translated")
                            if sid is not None and val is not None:
                                results[str(sid)] = _sanitize_translated_tokens(str(val))
                else:
                    for k, v in data.items():
                        if isinstance(v, str):
                            results[str(k)] = _sanitize_translated_tokens(v)
            elif isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        sid = item.get("id") or item.get("segment_id")
                        val = item.get("text") if "text" in item else item.get("translated")
                        if sid is not None and val is not None:
                            results[str(sid)] = _sanitize_translated_tokens(str(val))
        except json.JSONDecodeError:
            pass

        # 2. Try XML tagged parsing
        if not results:
            for match in _TAGGED_SEGMENT_REGEX.finditer(text):
                seg_id = match.group(1).strip()
                translated = match.group(2).strip()
                results[seg_id] = _sanitize_translated_tokens(translated)

        if not results:
            raise InvalidTranslationResponseError(
                f"Failed to parse translated segments from OpenAI endpoint response:\n{text[:300]}"
            )

        return results


    def _map_and_raise_error(self, exc: Exception) -> None:
        """Map API/HTTP status codes to standardized LayoutLingua error taxonomy."""
        err_msg = str(exc)
        status_code = getattr(exc, "status_code", getattr(exc, "code", None))

        if status_code == 401 or "invalid_api_key" in err_msg or "Incorrect API key" in err_msg:
            raise AuthenticationError(f"OpenAI authentication failed: {err_msg}") from exc

        if status_code == 403:
            if "quota" in err_msg.lower() or "billing" in err_msg.lower() or "insufficient_quota" in err_msg:
                raise QuotaExceededError(f"OpenAI quota/billing error: {err_msg}") from exc
            raise AuthenticationError(f"OpenAI permission denied: {err_msg}") from exc

        if status_code == 404 or "model_not_found" in err_msg or "does not exist" in err_msg.lower():
            raise ModelUnavailableError(
                model_id=self.model,
                provider_id=self.name,
                message=f"Model '{self.model}' was not found or is unavailable on endpoint {self._base_url}.",
            ) from exc

        if status_code == 429 or "rate_limit" in err_msg.lower():
            retry_after = getattr(exc, "retry_after", None)
            raise RateLimitError(
                message=f"OpenAI rate limit exceeded: {err_msg}",
                retry_after=retry_after,
            ) from exc

        if status_code and 500 <= status_code < 600 or "timeout" in err_msg.lower():
            raise ProviderUnavailableError(f"OpenAI endpoint unavailable: {err_msg}") from exc

        # Default fallback
        raise ProviderUnavailableError(f"OpenAI translation request failed: {err_msg}") from exc
