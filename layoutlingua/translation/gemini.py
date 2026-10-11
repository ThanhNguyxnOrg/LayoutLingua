"""Official Google GenAI SDK translation provider adapter for Gemini."""

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
from layoutlingua.translation.profiles import ModelProfile, ModelProfileCatalog
from layoutlingua.translation.provider import BaseTranslationProvider

_TAGGED_SEGMENT_REGEX = re.compile(r"<segment\s+id=[\"'](.*?)[\"']>(.*?)</segment>", re.DOTALL)


class GeminiTranslationProvider(BaseTranslationProvider):
    """Translates text segments via Google GenAI SDK with structured output negotiation."""

    def __init__(
        self,
        api_key: str,
        profile_or_model: str | ModelProfile = "gemini.fast",
        tier: str = "paid",
        client: Any | None = None,
    ) -> None:
        if not api_key or not api_key.strip():
            raise ValueError("api_key must be provided for GeminiTranslationProvider.")
        self._api_key = api_key.strip()

        # Resolve model profile
        if isinstance(profile_or_model, ModelProfile):
            self.profile = profile_or_model
        else:
            try:
                self.profile = ModelProfileCatalog.get_profile(profile_or_model)
            except KeyError:
                # Custom user-specified model ID
                self.profile = ModelProfileCatalog.create_custom(
                    provider_id="gemini",
                    model_id=profile_or_model,
                    supports_structured_json=True,
                )

        self._tier = tier.strip().lower()
        # Security invariant: only explicit "paid" tier is exempt from data use consent
        requires_consent = self._tier != "paid"

        rpm = 60.0 if self._tier == "paid" else 15.0
        self._capabilities = ProviderCapabilities(
            supports_structured_json=self.profile.supports_structured_json,
            requires_data_use_consent=requires_consent,
            tier=self._tier,
            policy_version="2026-06",
            max_batch_segments=25,
            max_batch_chars=12000,
            requests_per_minute=rpm,
        )
        self._client = client

    @property
    def name(self) -> str:
        return "gemini"

    @property
    def model(self) -> str:
        return self.profile.model_id

    @property
    def capabilities(self) -> ProviderCapabilities:
        return self._capabilities

    def _get_client(self) -> Any:
        """Lazily initialize Google GenAI SDK client if not injected."""
        if self._client is not None:
            return self._client

        try:
            from google import genai  # type: ignore

            self._client = genai.Client(api_key=self._api_key)
            return self._client
        except ImportError:
            raise ProviderUnavailableError(
                "Google GenAI SDK is not installed. To use Gemini translation, "
                "install the SDK via: pip install google-genai"
            )

    def translate_batch(self, request: BatchTranslationRequest) -> BatchTranslationResult:
        """Dispatch batch translation request to Gemini."""
        client = self._get_client()

        # Build prompt
        system_instruction = (
            f"You are a professional academic and technical document translator.\n"
            f"Translate the following segments from {request.source_language} to {request.target_language}.\n"
            f"Strict invariants:\n"
            f"1. Never modify, omit, or translate formula placeholder tokens: ⟦LL_FORMULA_XXXX⟧.\n"
            f"2. Keep the exact token ID and brackets unchanged.\n"
            f"3. Return the exact segment IDs provided.\n"
        )

        use_json = self.capabilities.supports_structured_json

        if use_json:
            user_content = json.dumps(
                [{"id": s.segment_id, "text": s.masked_text} for s in request.segments],
                ensure_ascii=False,
            )
            prompt = (
                f"{system_instruction}\n"
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
                f"{system_instruction}\n"
                f"Input segments to translate:\n{tagged_content}\n"
                f"Respond using the exact XML tags: <segment id=\"...\">translated text</segment> for each segment."
            )

        try:
            response_text = self._execute_call(client, prompt, use_json)
        except Exception as e:
            self._map_and_raise_error(e)

        # Parse output
        translations = self._parse_response(response_text, [s.segment_id for s in request.segments], use_json)
        return BatchTranslationResult(translations=translations)

    def _execute_call(self, client: Any, prompt: str, use_json: bool) -> str:
        """Invoke client with structured configuration if supported."""
        if hasattr(client, "models") and hasattr(client.models, "generate_content"):
            config: dict[str, Any] = {}
            if use_json:
                config["response_mime_type"] = "application/json"

            resp = client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=config if config else None,
            )
            if hasattr(resp, "text") and resp.text:
                return resp.text
            raise InvalidTranslationResponseError("Empty response received from Gemini.")

        # Fallback for custom or mock callables
        if callable(client):
            return str(client(prompt))

        raise ProviderUnavailableError("Invalid Gemini client handle.")

    def _parse_response(self, text: str, expected_ids: list[str], was_json: bool) -> dict[str, str]:
        """Parse structured JSON or tagged block translations from LLM response."""
        results: dict[str, str] = {}

        # 1. Try parsing JSON
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

        # 2. Try parsing XML tagged blocks if JSON yielded nothing or was incomplete
        if not results:
            for match in _TAGGED_SEGMENT_REGEX.finditer(text):
                seg_id = match.group(1).strip()
                translated = match.group(2).strip()
                results[seg_id] = translated

        if not results:
            raise InvalidTranslationResponseError(
                f"Failed to parse translated segments from Gemini response:\n{text[:300]}"
            )

        return results

    def _map_and_raise_error(self, exc: Exception) -> None:
        """Map SDK and HTTP status codes to standardized LayoutLingua error taxonomy."""
        err_msg = str(exc)
        status_code = getattr(exc, "status_code", getattr(exc, "code", None))

        # Check status codes
        if status_code == 401 or "UNAUTHENTICATED" in err_msg or "API_KEY_INVALID" in err_msg:
            raise AuthenticationError(f"Gemini authentication failed: {err_msg}") from exc

        if status_code == 403 or "PERMISSION_DENIED" in err_msg:
            if "BILLING" in err_msg or "QUOTA" in err_msg:
                raise QuotaExceededError(f"Gemini billing or quota error: {err_msg}") from exc
            raise AuthenticationError(f"Gemini permission denied: {err_msg}") from exc

        if status_code == 404 or "NOT_FOUND" in err_msg or "is not found" in err_msg:
            raise ModelUnavailableError(
                model_id=self.model,
                provider_id=self.name,
                message=f"Gemini model '{self.model}' is not found or has been deprecated.",
            ) from exc

        if status_code == 429 or "RESOURCE_EXHAUSTED" in err_msg or "rate limit" in err_msg.lower():
            retry_after = getattr(exc, "retry_after", None)
            raise RateLimitError(
                message=f"Gemini rate limit exceeded: {err_msg}",
                retry_after=retry_after,
            ) from exc

        if status_code and 500 <= status_code < 600 or "DEADLINE_EXCEEDED" in err_msg:
            raise ProviderUnavailableError(f"Gemini server unavailable: {err_msg}") from exc

        # Default fallback
        raise ProviderUnavailableError(f"Gemini translation failed: {err_msg}") from exc
