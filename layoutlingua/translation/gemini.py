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
            raw_model_str = str(profile_or_model or "gemini.fast").strip()
            if raw_model_str.startswith("models/"):
                raw_model_str = raw_model_str[len("models/") :]
            try:
                self.profile = ModelProfileCatalog.get_profile(raw_model_str)
            except KeyError:
                # Custom user-specified model ID
                self.profile = ModelProfileCatalog.create_custom(
                    provider_id="gemini",
                    model_id=raw_model_str,
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
        """Lazily initialize Google GenAI SDK client, OpenAI-compatible client, or native REST."""
        if self._client is not None:
            return self._client

        # Mode 1: Official google.genai SDK if installed
        try:
            from google import genai  # type: ignore

            self._client = genai.Client(api_key=self._api_key)
            return self._client
        except ImportError:
            pass

        # Mode 2: Official Google OpenAI compatibility layer via installed openai package
        try:
            from openai import OpenAI  # type: ignore

            self._client = OpenAI(
                api_key=self._api_key,
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
                timeout=60.0,
            )
            return self._client
        except ImportError:
            pass

        # Mode 3: Native REST fallback via standard library urllib (zero dependencies)
        self._client = "native_rest"
        return self._client

    def translate_batch(self, request: BatchTranslationRequest) -> BatchTranslationResult:
        """Dispatch batch translation request to Gemini."""
        if not request.segments:
            return BatchTranslationResult(translations={})

        client = self._get_client()
        src_lang = request.source_language if (request.source_language and request.source_language != "auto") else "the source language"

        # Build prompt
        system_instruction = (
            f"You are a professional academic and technical document translator.\n"
            f"Translate the following segments from {src_lang} to {request.target_language}.\n"
            f"Strict invariants:\n"
            f"1. Never modify, omit, or translate formula placeholder tokens: ⟦LL_FORMULA_XXXX⟧, <b0></b0>, <b1></b1>, ⟦CIT_0⟧, ⟦ABBR_0⟧, or ⟦M0⟧.\n"
            f"2. Keep the exact token ID, XML tags (<b0></b0>), and brackets unchanged in their appropriate grammatical position.\n"
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
        clean_model = self.model[7:] if self.model.startswith("models/") else self.model

        # 1. Google GenAI SDK (has client.models.generate_content)
        if hasattr(client, "models") and hasattr(client.models, "generate_content"):
            config: dict[str, Any] = {}
            if use_json:
                config["response_mime_type"] = "application/json"

            resp = client.models.generate_content(
                model=clean_model,
                contents=prompt,
                config=config if config else None,
            )
            if hasattr(resp, "text") and resp.text:
                return resp.text
            raise InvalidTranslationResponseError("Empty response received from Gemini.")

        # 2. OpenAI SDK client (has client.chat.completions.create)
        if hasattr(client, "chat") and hasattr(client.chat, "completions"):
            kwargs: dict[str, Any] = {
                "model": clean_model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
            }
            if use_json:
                kwargs["response_format"] = {"type": "json_object"}

            resp = client.chat.completions.create(**kwargs)
            if resp.choices and resp.choices[0].message and resp.choices[0].message.content:
                return resp.choices[0].message.content
            raise InvalidTranslationResponseError("Empty response received from Gemini OpenAI endpoint.")

        # 3. Native REST via urllib.request (zero dependencies)
        if client == "native_rest":
            import urllib.request
            import urllib.error

            url = f"https://generativelanguage.googleapis.com/v1beta/models/{clean_model}:generateContent?key={self._api_key}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.1},
            }
            if use_json:
                payload["generationConfig"]["responseMimeType"] = "application/json"

            req_bytes = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=req_bytes,
                headers={"Content-Type": "application/json", "User-Agent": "LayoutLingua/2.0"},
            )
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts and "text" in parts[0]:
                            return str(parts[0]["text"])
                    raise InvalidTranslationResponseError(f"Unexpected REST response structure from Gemini: {data}")
            except urllib.error.HTTPError as he:
                body = ""
                try:
                    body = he.read().decode("utf-8", errors="replace")
                except Exception:
                    pass
                err = RuntimeError(f"HTTP {he.code}: {body or he.reason}")
                setattr(err, "status_code", he.code)
                raise err from he

        # Fallback for custom or mock callables
        if callable(client):
            return str(client(prompt))

        raise ProviderUnavailableError("Invalid Gemini client handle.")

    def _parse_response(self, text: str, expected_ids: list[str], was_json: bool) -> dict[str, str]:
        """Parse structured JSON or tagged block translations from LLM response."""
        from layoutlingua.translation.google_rpc import _sanitize_translated_tokens

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
                    # Flat dictionary mapping segment_id -> translated text
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

        # 2. Try parsing XML tagged blocks if JSON yielded nothing or was incomplete
        if not results:
            for match in _TAGGED_SEGMENT_REGEX.finditer(text):
                seg_id = match.group(1).strip()
                translated = match.group(2).strip()
                results[seg_id] = _sanitize_translated_tokens(translated)

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
        if (
            status_code == 401
            or "UNAUTHENTICATED" in err_msg
            or "API_KEY_INVALID" in err_msg
            or "pass a valid API key" in err_msg
        ):
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
