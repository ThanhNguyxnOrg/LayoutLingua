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
        if not model_id or not model_id.strip():
            raise ValueError("model_id must not be empty.")

        self._api_key = key
        self._model_id = model_id.strip()
        self._base_url = (base_url or "https://api.openai.com/v1").rstrip("/")
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
        """Lazily initialize OpenAI SDK client if not injected."""
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
            raise ProviderUnavailableError(
                "OpenAI SDK is not installed. To use OpenAI-compatible translation, "
                "install the SDK via: pip install openai"
            )

    def list_remote_models(self) -> list[str]:
        """Optional model discovery via GET /models endpoint if supported."""
        client = self._get_client()
        try:
            if hasattr(client, "models") and hasattr(client.models, "list"):
                resp = client.models.list()
                data = getattr(resp, "data", [])
                return [m.id for m in data if hasattr(m, "id")]
            return []
        except Exception:
            return []

    def translate_batch(self, request: BatchTranslationRequest) -> BatchTranslationResult:
        """Dispatch batch translation request to OpenAI-compatible endpoint."""
        client = self._get_client()

        system_instruction = (
            f"You are a professional academic and technical document translator.\n"
            f"Translate the following segments from {request.source_language} to {request.target_language}.\n"
            f"Strict invariants:\n"
            f"1. Never modify, omit, or translate formula placeholder tokens: ⟦LL_FORMULA_XXXX⟧.\n"
            f"2. Keep the exact token ID and brackets unchanged.\n"
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

        # Callable mock fallback for testing
        if callable(client):
            return str(client(messages, use_json))

        raise ProviderUnavailableError("Invalid OpenAI client handle.")

    def _parse_response(self, text: str, expected_ids: list[str]) -> dict[str, str]:
        """Parse structured JSON or tagged block translations from LLM response."""
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
            items = data.get("translations", []) if isinstance(data, dict) else data
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict) and "id" in item and "text" in item:
                        results[str(item["id"])] = str(item["text"])
        except json.JSONDecodeError:
            pass

        # 2. Try XML tagged parsing
        if not results:
            for match in _TAGGED_SEGMENT_REGEX.finditer(text):
                seg_id = match.group(1).strip()
                translated = match.group(2).strip()
                results[seg_id] = translated

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
