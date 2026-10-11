"""Model profile catalog managing curated LLM profiles and custom user overrides."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ModelProfile:
    """Specification of an evaluated model configuration.
    
    Quality tier and model lifecycle are decoupled from account billing tiers (Free vs Paid).
    """

    profile_id: str
    display_name: str
    provider_id: str
    model_id: str
    supports_structured_json: bool
    description: str
    lifecycle_note: str = ""
    is_curated: bool = True


class ModelProfileCatalog:
    """Central registry of verified model recommendations for LayoutLingua."""

    _CURATED_PROFILES: dict[str, ModelProfile] = {
        "gemini.fast": ModelProfile(
            profile_id="gemini.fast",
            display_name="Gemini Fast",
            provider_id="gemini",
            model_id="gemini-3.5-flash-lite",
            supports_structured_json=True,
            description="High throughput, low-latency translation with minimal cost.",
            lifecycle_note="Active generation. Successor to 3.1-flash-lite.",
            is_curated=True,
        ),
        "gemini.balanced": ModelProfile(
            profile_id="gemini.balanced",
            display_name="Gemini Balanced",
            provider_id="gemini",
            model_id="gemini-3.6-flash",
            supports_structured_json=True,
            description="Balanced speed and translation accuracy for standard prose.",
            lifecycle_note="Active. Replaced 3.5-flash as the standard balanced model.",
            is_curated=True,
        ),
        "gemini.quality": ModelProfile(
            profile_id="gemini.quality",
            display_name="Gemini Quality",
            provider_id="gemini",
            model_id="gemini-3.8-flash",
            supports_structured_json=True,
            description="High-reasoning synthesis for complex academic papers and math.",
            lifecycle_note="Active flagship tier for demanding document layouts.",
            is_curated=True,
        ),
        "openai.fast": ModelProfile(
            profile_id="openai.fast",
            display_name="OpenAI Fast",
            provider_id="openai-compatible",
            model_id="gpt-4o-mini",
            supports_structured_json=True,
            description="Fast, cost-effective OpenAI model for rapid document translation.",
            lifecycle_note="Active standard model for OpenAI endpoints.",
            is_curated=True,
        ),
        "openai.quality": ModelProfile(
            profile_id="openai.quality",
            display_name="OpenAI Quality",
            provider_id="openai-compatible",
            model_id="gpt-4o",
            supports_structured_json=True,
            description="Flagship OpenAI model with high reasoning for dense technical text.",
            lifecycle_note="Active high-capability flagship model.",
            is_curated=True,
        ),
    }

    @classmethod
    def list_profiles(cls) -> list[ModelProfile]:
        """Return all curated model profiles."""
        return list(cls._CURATED_PROFILES.values())

    @classmethod
    def get_profile(cls, profile_id: str) -> ModelProfile:
        """Fetch profile by ID. Raises KeyError if profile does not exist."""
        profile = cls._CURATED_PROFILES.get(profile_id)
        if profile is None:
            available = list(cls._CURATED_PROFILES.keys())
            raise KeyError(
                f"Model profile '{profile_id}' not found. Available profiles: {available}"
            )
        return profile

    @classmethod
    def create_custom(
        cls,
        provider_id: str,
        model_id: str,
        supports_structured_json: bool = False,
        display_name: str | None = None,
    ) -> ModelProfile:
        """Create a custom profile for user-selected models (e.g. DeepSeek, Ollama, vLLM).
        
        Important: supports_structured_json defaults to False for custom endpoints
        unless verified or explicitly enabled by caller.
        """
        clean_model = model_id.strip()
        name = display_name or f"Custom ({clean_model})"
        return ModelProfile(
            profile_id="custom",
            display_name=name,
            provider_id=provider_id,
            model_id=clean_model,
            supports_structured_json=supports_structured_json,
            description=f"User-specified model '{clean_model}' on {provider_id}.",
            lifecycle_note="User-managed endpoint and lifecycle.",
            is_curated=False,
        )
