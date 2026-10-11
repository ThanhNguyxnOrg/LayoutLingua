"""Data models and language normalization for Argos Translate offline provider."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class RouteType(str, Enum):
    """Classification of translation path capability."""

    DIRECT = "DIRECT"
    PIVOT = "PIVOT"
    UNAVAILABLE = "UNAVAILABLE"


class LanguageRegistry:
    """Standardized BCP-47 / ISO language codes mapped to Argos Translate naming conventions."""

    # Map standardized LayoutLingua language codes to Argos internal package codes
    _STANDARD_TO_ARGOS: dict[str, str] = {
        "en": "en",
        "vi": "vi",
        "zh-Hans": "zh",
        "zh": "zh",
        "zh-Hant": "zt",
        "zt": "zt",
        "ja": "ja",
        "ko": "ko",
        "fr": "fr",
        "de": "de",
        "es": "es",
        "ru": "ru",
        "it": "it",
        "pt": "pt",
        "pt-BR": "pt",
        "ar": "ar",
        "hi": "hi",
        "id": "id",
        "nl": "nl",
        "pl": "pl",
        "tr": "tr",
        "uk": "uk",
    }

    _ARGOS_TO_STANDARD: dict[str, str] = {
        "en": "en",
        "vi": "vi",
        "zh": "zh-Hans",
        "zt": "zh-Hant",
        "ja": "ja",
        "ko": "ko",
        "fr": "fr",
        "de": "de",
        "es": "es",
        "ru": "ru",
        "it": "it",
        "pt": "pt",
        "ar": "ar",
        "hi": "hi",
        "id": "id",
        "nl": "nl",
        "pl": "pl",
        "tr": "tr",
        "uk": "uk",
    }

    _LANGUAGE_NAMES: dict[str, str] = {
        "en": "English",
        "vi": "Vietnamese",
        "zh-Hans": "Chinese (Simplified)",
        "zh-Hant": "Chinese (Traditional)",
        "ja": "Japanese",
        "ko": "Korean",
        "fr": "French",
        "de": "German",
        "es": "Spanish",
        "ru": "Russian",
        "it": "Italian",
        "pt": "Portuguese",
        "ar": "Arabic",
        "hi": "Hindi",
        "id": "Indonesian",
        "nl": "Dutch",
        "pl": "Polish",
        "tr": "Turkish",
        "uk": "Ukrainian",
    }

    @classmethod
    def to_argos_code(cls, code: str) -> str:
        """Convert standard LayoutLingua language code to Argos internal code."""
        normalized = code.strip()
        return cls._STANDARD_TO_ARGOS.get(normalized, normalized.lower()[:2])

    @classmethod
    def from_argos_code(cls, code: str) -> str:
        """Convert Argos internal code to standard LayoutLingua code."""
        normalized = code.strip()
        return cls._ARGOS_TO_STANDARD.get(normalized, normalized)

    @classmethod
    def get_name(cls, code: str) -> str:
        """Return human-readable English name for language code."""
        std = cls.from_argos_code(code)
        return cls._LANGUAGE_NAMES.get(std, std.upper())


@dataclass(frozen=True, slots=True)
class RouteStep:
    """A single atomic language translation hop."""

    from_code: str
    to_code: str
    package_name: str
    download_size_bytes: int = 0
    is_installed: bool = False


@dataclass(frozen=True, slots=True)
class TranslationRoute:
    """A directional translation execution plan (direct or multi-step pivot)."""

    from_code: str
    to_code: str
    route_type: RouteType
    steps: tuple[RouteStep, ...]

    @property
    def is_fully_installed(self) -> bool:
        """Return True if all intermediate models are installed locally."""
        return all(s.is_installed for s in self.steps)

    @property
    def total_download_size_bytes(self) -> int:
        """Sum of download bytes for uninstalled packages required by this route."""
        return sum(s.download_size_bytes for s in self.steps if not s.is_installed)

    def describe(self) -> str:
        """Human-readable description of translation path."""
        if not self.steps:
            return "Unavailable"
        hops = [LanguageRegistry.get_name(self.steps[0].from_code)]
        for s in self.steps:
            hops.append(LanguageRegistry.get_name(s.to_code))
        arrow_path = " -> ".join(hops)
        pivot_tag = " (Direct)" if self.route_type == RouteType.DIRECT else " (Pivot)"
        return f"{arrow_path}{pivot_tag}"


@dataclass(frozen=True, slots=True)
class ArgosModelInfo:
    """Metadata describing a downloadable or installed Argos Translate language model package."""

    from_code: str
    to_code: str
    package_name: str
    version: str
    download_url: str
    size_bytes: int = 0
    sha256: str | None = None
    is_installed: bool = False
    is_curated: bool = False
    checksum_verified: bool = False


@dataclass(frozen=True, slots=True)
class PackageDownloadProgress:
    """Progress event during package download."""

    package_name: str
    downloaded_bytes: int
    total_bytes: int
    percent: float
