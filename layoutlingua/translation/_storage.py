"""Persistent SQLite storage engine for translations, jobs, and privacy consents.

Features:
- Versioned schema migrations.
- WAL mode, busy timeout, and thread-safe connection pooling.
- Canonical JSON SHA-256 cache key calculation.
- Segregated tables: translation_cache, jobs, job_segments, privacy_consents.
- Atomic batch transactions for consistent crash recovery.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3
import threading
from typing import Any

from platformdirs import user_data_dir

from layoutlingua.translation.errors import JobConflictError, JobNotFoundError
from layoutlingua.translation.models import JobStatus, SegmentStatus, TranslationJob

_CURRENT_SCHEMA_VERSION = 1


def compute_cache_key(
    provider: str,
    model: str,
    source_language: str,
    target_language: str,
    prompt_version: str,
    normalizer_version: str,
    glossary_version: str,
    generation_settings_hash: str,
    normalized_text: str,
) -> str:
    """Compute a deterministic SHA-256 hash from canonical sorted JSON inputs."""
    payload = {
        "generation_settings_hash": generation_settings_hash,
        "glossary_version": glossary_version,
        "model": model,
        "normalizer_version": normalizer_version,
        "normalized_text": normalized_text,
        "prompt_version": prompt_version,
        "provider": provider,
        "source_language": source_language,
        "target_language": target_language,
    }
    canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


class StorageEngine:
    """Encapsulates SQLite transactions, WAL management, and state transitions."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        if db_path is None:
            base_dir = Path(user_data_dir("LayoutLingua"))
            base_dir.mkdir(parents=True, exist_ok=True)
            self._db_path = str(base_dir / "layoutlingua.sqlite")
            self._is_memory = False
        elif str(db_path) == ":memory:":
            self._db_path = ":memory:"
            self._is_memory = True
        else:
            path_obj = Path(db_path)
            path_obj.parent.mkdir(parents=True, exist_ok=True)
            self._db_path = str(path_obj)
            self._is_memory = False

        self._local = threading.local()
        self._lock = threading.RLock()
        self._connections: list[sqlite3.Connection] = []
        self._init_database()

    def _get_connection(self) -> sqlite3.Connection:
        """Get or create a thread-local SQLite connection."""
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(
                self._db_path,
                timeout=5.0,
                check_same_thread=False,
            )
            conn.row_factory = sqlite3.Row
            # Configure database pragmas
            if not self._is_memory:
                conn.execute("PRAGMA journal_mode = WAL;")
                conn.execute("PRAGMA synchronous = NORMAL;")
            conn.execute("PRAGMA busy_timeout = 5000;")
            conn.execute("PRAGMA foreign_keys = ON;")
            self._local.conn = conn
            with self._lock:
                self._connections.append(conn)
        return conn

    def close(self) -> None:
        """Close all connections opened by this storage engine instance."""
        with self._lock:
            for conn in self._connections:
                try:
                    conn.close()
                except Exception:
                    pass
            self._connections.clear()
            self._local.conn = None

    def _init_database(self) -> None:
        """Execute versioned migrations to ensure database schema matches current version."""
        with self._lock:
            conn = self._get_connection()
            with conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS schema_version (
                        version INTEGER PRIMARY KEY,
                        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                    """
                )
                cursor = conn.execute("SELECT MAX(version) FROM schema_version;")
                row = cursor.fetchone()
                current_ver = row[0] if (row and row[0] is not None) else 0

                if current_ver < 1:
                    self._apply_migration_v1(conn)
                    conn.execute("INSERT INTO schema_version (version) VALUES (1);")

    def _apply_migration_v1(self, conn: sqlite3.Connection) -> None:
        """Create baseline tables for cache, jobs, segments, and privacy consents."""
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS translation_cache (
                cache_key TEXT PRIMARY KEY,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                source_language TEXT NOT NULL,
                target_language TEXT NOT NULL,
                source_text TEXT NOT NULL,
                translated_text TEXT NOT NULL,
                prompt_version TEXT NOT NULL,
                glossary_version TEXT NOT NULL,
                settings_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                access_count INTEGER DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                document_fingerprint TEXT NOT NULL,
                source_language TEXT NOT NULL,
                target_language TEXT NOT NULL,
                prompt_version TEXT NOT NULL,
                glossary_version TEXT NOT NULL,
                settings_hash TEXT NOT NULL,
                status TEXT NOT NULL,
                total_segments INTEGER NOT NULL,
                completed_segments INTEGER NOT NULL DEFAULT 0,
                failed_segments INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS job_segments (
                job_id TEXT NOT NULL,
                segment_id TEXT NOT NULL,
                segment_index INTEGER NOT NULL,
                source_text TEXT NOT NULL,
                status TEXT NOT NULL,
                cache_key TEXT,
                translated_text TEXT,
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (job_id, segment_id),
                FOREIGN KEY (job_id) REFERENCES jobs(job_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS privacy_consents (
                provider_id TEXT NOT NULL,
                tier TEXT NOT NULL,
                policy_version TEXT NOT NULL,
                consented_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (provider_id, tier, policy_version)
            );

            CREATE INDEX IF NOT EXISTS idx_cache_lookup ON translation_cache(cache_key);
            CREATE INDEX IF NOT EXISTS idx_job_segments_status ON job_segments(job_id, status);
            """
        )

    # -------------------------------------------------------------------------
    # Cache Operations
    # -------------------------------------------------------------------------

    def lookup_cache(self, cache_key: str) -> str | None:
        """Lookup a cached translation by key. Updates access metrics on hit."""
        conn = self._get_connection()
        cursor = conn.execute(
            "SELECT translated_text FROM translation_cache WHERE cache_key = ?;",
            (cache_key,),
        )
        row = cursor.fetchone()
        if row is None:
            return None

        # Asynchronously update access metrics
        try:
            with conn:
                conn.execute(
                    """
                    UPDATE translation_cache
                    SET last_accessed_at = CURRENT_TIMESTAMP,
                        access_count = access_count + 1
                    WHERE cache_key = ?;
                    """,
                    (cache_key,),
                )
        except sqlite3.OperationalError:
            pass  # Do not fail lookup if lock contention occurs on metric bump

        return str(row[0])

    # -------------------------------------------------------------------------
    # Job and Segment Operations
    # -------------------------------------------------------------------------

    def create_or_validate_job(self, job: TranslationJob) -> tuple[JobStatus, int, int]:
        """Register or validate a translation job.
        
        Returns (status, completed_segments_count, total_segments).
        Raises JobConflictError if job_id exists with conflicting fingerprint or settings.
        """
        conn = self._get_connection()
        with conn:
            cursor = conn.execute(
                """
                SELECT document_fingerprint, source_language, target_language,
                       prompt_version, glossary_version, settings_hash,
                       status, completed_segments, total_segments
                FROM jobs WHERE job_id = ?;
                """,
                (job.job_id,),
            )
            row = cursor.fetchone()
            if row is not None:
                # Validate consistency
                if (
                    row["document_fingerprint"] != job.document_fingerprint
                    or row["source_language"] != job.source_language
                    or row["target_language"] != job.target_language
                    or row["prompt_version"] != job.prompt_version
                    or row["glossary_version"] != job.glossary_version
                    or row["settings_hash"] != job.generation_settings_hash
                ):
                    raise JobConflictError(
                        f"Job '{job.job_id}' already exists with different fingerprint or translation parameters."
                    )
                return JobStatus(row["status"]), int(row["completed_segments"]), int(row["total_segments"])

            # Create new job and initial segments
            conn.execute(
                """
                INSERT INTO jobs (
                    job_id, document_fingerprint, source_language, target_language,
                    prompt_version, glossary_version, settings_hash, status,
                    total_segments, completed_segments, failed_segments
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0);
                """,
                (
                    job.job_id,
                    job.document_fingerprint,
                    job.source_language,
                    job.target_language,
                    job.prompt_version,
                    job.glossary_version,
                    job.generation_settings_hash,
                    JobStatus.PENDING.value,
                    len(job.segments),
                ),
            )

            segment_params = [
                (
                    job.job_id,
                    seg.segment_id,
                    idx,
                    seg.masked_text,
                    SegmentStatus.PENDING.value,
                )
                for idx, seg in enumerate(job.segments)
            ]
            conn.executemany(
                """
                INSERT INTO job_segments (
                    job_id, segment_id, segment_index, source_text, status
                ) VALUES (?, ?, ?, ?, ?);
                """,
                segment_params,
            )

            return JobStatus.PENDING, 0, len(job.segments)

    def get_job_info(self, job_id: str) -> dict[str, Any]:
        """Fetch metadata and current status for an existing job."""
        conn = self._get_connection()
        cursor = conn.execute("SELECT * FROM jobs WHERE job_id = ?;", (job_id,))
        row = cursor.fetchone()
        if row is None:
            raise JobNotFoundError(f"Job '{job_id}' not found.")
        return dict(row)

    def get_pending_segments(self, job_id: str) -> list[dict[str, Any]]:
        """Retrieve segments for a job that have not yet reached COMPLETED status."""
        conn = self._get_connection()
        cursor = conn.execute(
            """
            SELECT segment_id, segment_index, source_text, status
            FROM job_segments
            WHERE job_id = ? AND status != ?
            ORDER BY segment_index ASC;
            """,
            (job_id, SegmentStatus.COMPLETED.value),
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_all_segments(self, job_id: str) -> list[dict[str, Any]]:
        """Retrieve all segments for a job ordered by original sequence index."""
        conn = self._get_connection()
        cursor = conn.execute(
            """
            SELECT segment_id, segment_index, source_text, status,
                   cache_key, translated_text, error_message
            FROM job_segments
            WHERE job_id = ?
            ORDER BY segment_index ASC;
            """,
            (job_id,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def commit_batch_success(
        self,
        job_id: str,
        results: list[dict[str, Any]],
        no_cache: bool = False,
    ) -> None:
        """Atomically commit successfully translated segments to cache and job tracking."""
        conn = self._get_connection()
        with conn:
            # 1. Update translation cache if enabled
            if not no_cache:
                cache_params = [
                    (
                        r["cache_key"],
                        r["provider"],
                        r["model"],
                        r["source_language"],
                        r["target_language"],
                        r["source_text"],
                        r["translated_text"],
                        r["prompt_version"],
                        r["glossary_version"],
                        r["settings_hash"],
                    )
                    for r in results
                    if r.get("cache_key") and r.get("translated_text") is not None
                ]
                if cache_params:
                    conn.executemany(
                        """
                        INSERT INTO translation_cache (
                            cache_key, provider, model, source_language, target_language,
                            source_text, translated_text, prompt_version,
                            glossary_version, settings_hash
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(cache_key) DO UPDATE SET
                            last_accessed_at = CURRENT_TIMESTAMP,
                            access_count = access_count + 1;
                        """,
                        cache_params,
                    )

            # 2. Update job_segments status
            segment_params = [
                (
                    SegmentStatus.COMPLETED.value,
                    r.get("cache_key"),
                    r.get("translated_text"),
                    job_id,
                    r["segment_id"],
                )
                for r in results
            ]
            conn.executemany(
                """
                UPDATE job_segments
                SET status = ?, cache_key = ?, translated_text = ?, error_message = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE job_id = ? AND segment_id = ?;
                """,
                segment_params,
            )

            # 3. Refresh job summary counts
            cursor = conn.execute(
                """
                SELECT COUNT(*) as total,
                       SUM(CASE WHEN status = ? THEN 1 ELSE 0 END) as completed,
                       SUM(CASE WHEN status = ? THEN 1 ELSE 0 END) as failed
                FROM job_segments WHERE job_id = ?;
                """,
                (SegmentStatus.COMPLETED.value, SegmentStatus.FAILED.value, job_id),
            )
            stats = cursor.fetchone()
            total = stats["total"] or 0
            completed = stats["completed"] or 0
            failed = stats["failed"] or 0

            new_status = JobStatus.IN_PROGRESS.value
            if completed == total:
                new_status = JobStatus.COMPLETED.value
            elif completed + failed == total and failed > 0:
                new_status = JobStatus.PARTIAL_FAILED.value

            conn.execute(
                """
                UPDATE jobs
                SET completed_segments = ?, failed_segments = ?, status = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE job_id = ?;
                """,
                (completed, failed, new_status, job_id),
            )

    def record_segment_failures(
        self,
        job_id: str,
        failures: list[tuple[str, str]],  # (segment_id, error_message)
    ) -> None:
        """Mark specific segments as failed with diagnostic error details."""
        conn = self._get_connection()
        with conn:
            params = [(SegmentStatus.FAILED.value, err, job_id, seg_id) for seg_id, err in failures]
            conn.executemany(
                """
                UPDATE job_segments
                SET status = ?, error_message = ?, updated_at = CURRENT_TIMESTAMP
                WHERE job_id = ? AND segment_id = ?;
                """,
                params,
            )

            # Recalculate job status
            cursor = conn.execute(
                """
                SELECT COUNT(*) as total,
                       SUM(CASE WHEN status = ? THEN 1 ELSE 0 END) as completed,
                       SUM(CASE WHEN status = ? THEN 1 ELSE 0 END) as failed
                FROM job_segments WHERE job_id = ?;
                """,
                (SegmentStatus.COMPLETED.value, SegmentStatus.FAILED.value, job_id),
            )
            stats = cursor.fetchone()
            total = stats["total"] or 0
            completed = stats["completed"] or 0
            failed = stats["failed"] or 0

            new_status = JobStatus.IN_PROGRESS.value
            if completed + failed == total:
                new_status = JobStatus.PARTIAL_FAILED.value if completed > 0 else JobStatus.FAILED.value

            conn.execute(
                """
                UPDATE jobs
                SET completed_segments = ?, failed_segments = ?, status = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE job_id = ?;
                """,
                (completed, failed, new_status, job_id),
            )

    def update_job_status(self, job_id: str, status: JobStatus) -> None:
        """Explicitly update overall job status (e.g. CANCELLED or FAILED)."""
        conn = self._get_connection()
        with conn:
            conn.execute(
                "UPDATE jobs SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE job_id = ?;",
                (status.value, job_id),
            )

    # -------------------------------------------------------------------------
    # Privacy Consent Management
    # -------------------------------------------------------------------------

    def has_privacy_consent(self, provider_id: str, tier: str, policy_version: str) -> bool:
        """Check if affirmative user consent exists for a specific provider policy."""
        conn = self._get_connection()
        cursor = conn.execute(
            """
            SELECT 1 FROM privacy_consents
            WHERE provider_id = ? AND tier = ? AND policy_version = ?;
            """,
            (provider_id, tier, policy_version),
        )
        return cursor.fetchone() is not None

    def record_privacy_consent(self, provider_id: str, tier: str, policy_version: str) -> None:
        """Persist explicit user consent for external data use."""
        conn = self._get_connection()
        with conn:
            conn.execute(
                """
                INSERT INTO privacy_consents (provider_id, tier, policy_version)
                VALUES (?, ?, ?)
                ON CONFLICT(provider_id, tier, policy_version) DO UPDATE SET
                    consented_at = CURRENT_TIMESTAMP;
                """,
                (provider_id, tier, policy_version),
            )

    def revoke_privacy_consent(self, provider_id: str, tier: str, policy_version: str) -> None:
        """Revoke previously recorded privacy consent."""
        conn = self._get_connection()
        with conn:
            conn.execute(
                """
                DELETE FROM privacy_consents
                WHERE provider_id = ? AND tier = ? AND policy_version = ?;
                """,
                (provider_id, tier, policy_version),
            )
