#!/usr/bin/env python3
"""Turn an engine failure into something a user can read, act on, and report.

The queue row has space for one short line, which is never enough to diagnose a
failure on someone else's document. Users were sent a clipped English exception
and could neither understand it nor quote it back, so every failure here gets a
stable code, a plain Vietnamese summary, one concrete instruction, and the full
technical text kept verbatim for the report.
"""

from __future__ import annotations

import platform
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

UNKNOWN_CODE = "E-UNK-99"


@dataclass(frozen=True)
class Failure:
    """One failure in the forms the app needs: label, guidance, evidence."""

    code: str
    summary: str
    advice: str
    detail: str

    @property
    def headline(self) -> str:
        """The single line the queue row shows."""
        return f"{self.summary} [{self.code}]"


# Matched in order against the flattened exception chain, so the most specific
# cause wins. Each entry is (code, markers, summary, advice); a failure matches
# when any marker appears in the chain's type names or messages.
_RULES: tuple[tuple[str, tuple[str, ...], str, str], ...] = (
    (
        "E-CORE-01",
        ("pikepdf", "_core", "extension library", "DLL load failed",
         "ImportError", "ModuleNotFoundError"),
        "Application missing internal library",
        "Please extract the FULL archive and run from the extracted folder "
        "(do not run directly from inside .zip), and add an exception in your "
        "antivirus software if needed.",
    ),
    (
        "E-OUT-05",
        ("already exists", "Output already exists"),
        "Translated file already exists",
        'Check "Overwrite previously translated files" and retry, or remove the '
        "existing file in the translated folder.",
    ),
    (
        "E-PDF-02",
        ("FzErrorSyntax", "damaged beyond repair", "Could not repair",
         "invalid key in dict", "FzErrorFormat", "PdfError"),
        "PDF file has structural damage",
        "This file is corrupted beyond repair. Please open it in a PDF reader and "
        'use "Print to PDF" to generate a clean version, then translate that version.',
    ),
    (
        "E-PDF-01",
        ("does not exist", "must have a .pdf extension", "does not contain a PDF header"),
        "File is not a valid PDF",
        "Please verify that the file is a valid PDF and remains at its location.",
    ),
    (
        "E-PDF-03",
        ("scanned", "image-only", "OCR", "no extractable text"),
        "PDF contains only scanned images",
        "This document contains scanned images without extractable text. "
        "A text-based PDF or OCR processing is required.",
    ),
    (
        "E-NET-04",
        ("ConnectionError", "Timeout", "timed out", "HTTPError", "SSLError",
         "Max retries", "getaddrinfo", "Google Translate", "RetryError"),
        "Cannot connect to translation service",
        "Check your network connection or VPN and retry. Successfully translated "
        "segments are cached to speed up subsequent runs.",
    ),
    (
        "E-MEM-06",
        ("MemoryError", "not enough memory", "Cannot allocate"),
        "Insufficient memory for this document",
        "Close other running applications or split the large file into smaller parts.",
    ),
)


def flatten(error: BaseException) -> str:
    """Join an exception chain into one searchable string.

    The core wraps every failure in a generic wrapper, so only the chain says
    what actually went wrong.
    """
    parts: list[str] = []
    seen: set[int] = set()
    current: BaseException | None = error
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        message = str(current).strip()
        parts.append(f"{type(current).__name__}: {message}" if message
                     else type(current).__name__)
        current = current.__cause__ or current.__context__
    return " <- ".join(parts)


def describe_failure(error: BaseException) -> Failure:
    """Classify one failure. Unrecognised causes keep their original text."""
    detail = flatten(error)
    haystack = detail.lower()
    for code, markers, summary, advice in _RULES:
        if any(marker.lower() in haystack for marker in markers):
            return Failure(code, summary, advice, detail)
    return Failure(
        UNKNOWN_CODE,
        "Unknown error",
        "Please submit the report below to report the issue.",
        detail,
    )


def report_text(failure: Failure, source: Path, version: str, log: Path | None = None) -> str:
    """Build the block the user copies into a bug report.

    Everything a maintainer needs to reproduce, and nothing the user has to
    type out by hand.
    """
    lines = [
        "LayoutLingua - Bug Report",
        f"Timestamp : {datetime.now():%Y-%m-%d %H:%M:%S}",
        f"Version   : {version}",
        f"OS        : {platform.system()} {platform.release()} ({platform.machine()})",
        f"Python    : {sys.version.split()[0]}",
        f"File      : {source.name}",
        f"Error Code: {failure.code}  {failure.summary}",
        "",
        "Technical Details:",
        failure.detail,
    ]
    if log is not None:
        lines += ["", f"Full Log: {log}"]
    return "\n".join(lines)
