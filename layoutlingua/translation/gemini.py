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

    DYNAMIC_MODEL_ALIASES = {"auto", "latest", "gemini-auto", "gemini-latest", "gemini.auto"}

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

    @staticmethod
    def _is_usable_text_model(model_id: str) -> bool:
        """Return True if the Gemini model ID is a text/multimodal generation model suitable for translation."""
        m_low = model_id.lower().strip()
        if not m_low.startswith("gemini"):
            return False
        excluded_tokens = (
            "embedding",
            "imagen",
            "veo",
            "aqa",
            "tts",
            "audio",
            "robotics",
            "computer-use",
            "learnlm",
            "image-generation",
            "live",
        )
        return not any(tok in m_low for tok in excluded_tokens)

    @staticmethod
    def _score_gemini_model(model_id: str, preferred_hint: str = "") -> tuple[int, int, int, int, int]:
        """Score a candidate Gemini model so the newest stable Flash/Pro model wins."""
        m_low = model_id.lower().strip()
        hint_low = (preferred_hint or "").lower().strip()

        want_pro = "pro" in hint_low
        want_lite = "lite" in hint_low

        is_pro = "pro" in m_low
        is_flash = "flash" in m_low
        is_lite = "lite" in m_low or "8b" in m_low
        is_preview_or_exp = any(tag in m_low for tag in ("exp", "preview", "thinking", "customtools"))
        is_latest_alias = m_low in ("gemini-flash-latest", "gemini-pro-latest")

        if want_pro:
            family_score = 2 if is_pro else (1 if is_flash else 0)
        else:
            family_score = 2 if is_flash else (1 if is_pro else 0)

        variant_score = (1 if is_lite else 0) if want_lite else (1 if not is_lite else 0)
        stability_score = 2 if not is_preview_or_exp else 0

        ver_match = re.search(r"gemini-(\d+)(?:\.(\d+))?", m_low)
        if ver_match:
            major = int(ver_match.group(1))
            minor = int(ver_match.group(2) or 0)
        elif is_latest_alias:
            major, minor = 2, 4
        else:
            major, minor = 1, 0

        return (family_score, variant_score, stability_score, major, minor)

    def list_remote_models(self) -> list[str]:
        """Discover available Gemini text generation models from the API."""
        client = self._get_client()
        discovered: list[str] = []

        # 1. Try client.models.list() if client provides it
        if hasattr(client, "models") and hasattr(client.models, "list"):
            try:
                resp = client.models.list()
                items = getattr(resp, "data", None) or resp
                for item in items:
                    raw_name = getattr(item, "name", None) or getattr(item, "id", None)
                    if not isinstance(raw_name, str) or not raw_name.strip():
                        continue
                    methods = getattr(item, "supported_generation_methods", None) or getattr(
                        item, "supportedGenerationMethods", None
                    )
                    if isinstance(methods, (list, tuple, set)) and methods and "generateContent" not in methods:
                        continue
                    clean_name = raw_name.strip()
                    if clean_name.startswith("models/"):
                        clean_name = clean_name[7:]
                    if self._is_usable_text_model(clean_name) and clean_name not in discovered:
                        discovered.append(clean_name)
                if discovered:
                    return discovered
            except Exception:
                pass

        # 2. Native REST discovery via /v1beta/models (skip only if client is an isolated unit-test mock)
        is_mock_client = type(client).__module__.startswith("unittest.mock")
        if not is_mock_client:
            try:
                import urllib.request

                url = f"https://generativelanguage.googleapis.com/v1beta/models?key={self._api_key}"
                req = urllib.request.Request(url, headers={"User-Agent": "LayoutLingua/2.0"})
                with urllib.request.urlopen(req, timeout=8.0) as resp:
                    payload = json.loads(resp.read().decode("utf-8"))
                    models_list = payload.get("models", []) if isinstance(payload, dict) else []
                    for m in models_list:
                        if not isinstance(m, dict):
                            continue
                        methods = m.get("supportedGenerationMethods", [])
                        if isinstance(methods, list) and methods and "generateContent" not in methods:
                            continue
                        raw_name = str(m.get("name", "")).strip()
                        if raw_name.startswith("models/"):
                            raw_name = raw_name[7:]
                        if self._is_usable_text_model(raw_name) and raw_name not in discovered:
                            discovered.append(raw_name)
            except Exception:
                pass

        return discovered

    def resolve_best_available_model(
        self,
        preferred_hint: str = "",
        exclude_models: set[str] | None = None,
    ) -> str | None:
        """Select the highest-ranked active Gemini model, excluding any deprecated/failed models."""
        excluded = {
            m[7:] if m.startswith("models/") else m
            for m in (exclude_models or set())
            if isinstance(m, str)
        }
        candidates = [m for m in self.list_remote_models() if m not in excluded]
        if not candidates:
            return None
        hint = preferred_hint or self.model
        candidates.sort(key=lambda m: self._score_gemini_model(m, hint), reverse=True)
        return candidates[0]

    @staticmethod
    def _is_model_not_found_error(exc: Exception) -> bool:
        """Return True when an exception indicates a 404 / deprecated / non-existent model."""
        status_code = getattr(exc, "status_code", getattr(exc, "code", None))
        err_msg = str(exc)
        err_low = err_msg.lower()
        return bool(
            status_code == 404
            or "NOT_FOUND" in err_msg
            or "is not found" in err_low
            or "model_not_found" in err_low
            or "does not exist" in err_low
            or "deprecated" in err_low
            or "no longer available" in err_low
        )

    def translate_batch(self, request: BatchTranslationRequest) -> BatchTranslationResult:
        """Dispatch batch translation request to Gemini with dynamic model resolution and 404 auto-healing."""
        if not request.segments:
            return BatchTranslationResult(translations={})

        client = self._get_client()

        # Resolve dynamic 'auto' / 'latest' alias before calling the API
        if self.model.lower().strip() in self.DYNAMIC_MODEL_ALIASES:
            resolved = self.resolve_best_available_model(preferred_hint="flash") or "gemini-flash-latest"
            self.profile = ModelProfileCatalog.create_custom(
                provider_id="gemini",
                model_id=resolved,
                supports_structured_json=self.profile.supports_structured_json,
            )

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
            # Auto-heal if the configured model was deprecated or removed (e.g. gemini-2.5-flash deleted in the future)
            if self._is_model_not_found_error(e):
                failed_model = self.model
                replacement = self.resolve_best_available_model(
                    preferred_hint=failed_model,
                    exclude_models={failed_model, f"models/{failed_model}"},
                )
                if replacement and replacement != failed_model:
                    print(
                        f"[LayoutLingua] Gemini model '{failed_model}' is unavailable/deprecated; "
                        f"auto-switching to active model '{replacement}'."
                    )
                    self.profile = ModelProfileCatalog.create_custom(
                        provider_id="gemini",
                        model_id=replacement,
                        supports_structured_json=self.profile.supports_structured_json,
                    )
                    try:
                        response_text = self._execute_call(client, prompt, use_json)
                    except Exception as retry_err:
                        self._map_and_raise_error(retry_err)
                else:
                    self._map_and_raise_error(e)
            else:
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
