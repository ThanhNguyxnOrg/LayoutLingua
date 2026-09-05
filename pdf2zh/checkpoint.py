"""Checkpointing, Resumability, and Defect Manifest Manager for LayoutLingua.

Enables resilient, zero-loss translation for large documents (100-1000+ pages),
transparent stage-level failure reporting, and selective reference skipping.
Addresses Marker #885, Immersive Translate #3874, and PDFMathTranslate requests.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class DefectRecord:
    """Record of an untranslated or fallback segment with explicit reason."""
    page: int
    segment: str
    reason: str  # e.g., 'FormulaPlaceholderDamaged', 'GeometricOverflow', 'CodeProtected'


@dataclass
class CheckpointState:
    """Persistent state of a document translation session."""
    source_path: str
    output_path: str
    total_pages: int
    completed_pages: List[int] = field(default_factory=list)
    defects: List[Dict[str, Any]] = field(default_factory=list)
    glossary: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


class CheckpointManager:
    """Manages session persistence, resume capabilities, and defect manifests."""

    def __init__(
        self,
        source_path: str | Path,
        output_path: str | Path,
        total_pages: int = 0,
        checkpoint_dir: Optional[str | Path] = None,
    ):
        self.source_path = str(source_path)
        self.output_path = str(output_path)
        self.total_pages = total_pages

        if checkpoint_dir:
            self.checkpoint_file = Path(checkpoint_dir) / f"{Path(output_path).stem}.checkpoint.json"
        else:
            self.checkpoint_file = Path(f"{self.output_path}.checkpoint.json")

        self.state = CheckpointState(
            source_path=self.source_path,
            output_path=self.output_path,
            total_pages=total_pages,
        )
        self.completed_set: Set[int] = set()
        self.load()

    def is_page_completed(self, page_num: int) -> bool:
        """Check if a page was already translated and verified in a previous run."""
        return page_num in self.completed_set

    def mark_page_completed(
        self,
        page_num: int,
        defects_on_page: Optional[List[DefectRecord]] = None,
    ) -> None:
        """Mark page as completed and append any defects encountered."""
        if page_num not in self.completed_set:
            self.completed_set.add(page_num)
            self.state.completed_pages.append(page_num)
            self.state.completed_pages.sort()

        if defects_on_page:
            for d in defects_on_page:
                self.state.defects.append(asdict(d))

        self.save()

    def record_defect(self, page_num: int, segment: str, reason: str) -> None:
        """Log a fallback segment with reason."""
        rec = DefectRecord(page=page_num, segment=segment[:200], reason=reason)
        self.state.defects.append(asdict(rec))

    def save(self) -> None:
        """Persist state to JSON disk checkpoint atomically."""
        try:
            temp_file = self.checkpoint_file.with_suffix(".tmp")
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(asdict(self.state), f, indent=2, ensure_ascii=False)
            temp_file.replace(self.checkpoint_file)
        except Exception as e:
            logger.warning("Failed to save checkpoint %s: %s", self.checkpoint_file, e)

    def load(self) -> bool:
        """Load existing checkpoint if present."""
        if not self.checkpoint_file.exists():
            return False

        try:
            with open(self.checkpoint_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.state = CheckpointState(
                source_path=data.get("source_path", self.source_path),
                output_path=data.get("output_path", self.output_path),
                total_pages=data.get("total_pages", self.total_pages),
                completed_pages=data.get("completed_pages", []),
                defects=data.get("defects", []),
                glossary=data.get("glossary", {}),
                metadata=data.get("metadata", {}),
            )
            self.completed_set = set(self.state.completed_pages)
            logger.info(
                "Resuming from checkpoint: %d/%d pages completed",
                len(self.completed_set),
                self.state.total_pages,
            )
            return True
        except Exception as e:
            logger.warning("Could not read checkpoint %s: %s", self.checkpoint_file, e)
            return False

    def generate_manifest_report(self, report_path: Optional[str | Path] = None) -> Dict[str, Any]:
        """Generate final transparent defect manifest."""
        reason_counts: Dict[str, int] = {}
        for d in self.state.defects:
            r = d.get("reason", "Unknown")
            reason_counts[r] = reason_counts.get(r, 0) + 1

        manifest = {
            "source_pdf": self.source_path,
            "translated_pdf": self.output_path,
            "total_pages": self.state.total_pages,
            "completed_pages_count": len(self.completed_set),
            "total_fallback_segments": len(self.state.defects),
            "reasons_breakdown": reason_counts,
            "defects": self.state.defects,
        }

        if report_path:
            with open(report_path, "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=2, ensure_ascii=False)

        return manifest

    def cleanup(self) -> None:
        """Remove checkpoint file once translation has fully succeeded."""
        if self.checkpoint_file.exists():
            try:
                self.checkpoint_file.unlink()
            except OSError as e:
                logger.warning("Could not remove checkpoint %s: %s", self.checkpoint_file, e)


def is_reference_section_heading(text: str) -> bool:
    """Detect if a heading text denotes a bibliography/reference section."""
    cleaned = text.strip().lower()
    return cleaned in {
        "references",
        "reference",
        "bibliography",
        "literature cited",
        "tài liệu tham khảo",
        "references and notes",
    }
