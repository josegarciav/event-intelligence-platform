"""
Batch Writer for Ingestion Pipeline Output.

Saves normalized EventSchema objects to disk as JSONL files under data/batches/,
organized by source and date. This replaces direct-to-DB persistence for the
ingestion step.

The LLM enrichment layer reads from these batch files to apply normalization,
taxonomy classification, and other AI-driven enrichment before final DB persistence.

Directory structure:
    data/batches/
        {source_name}/
            {YYYY-MM-DD}_{batch_id}.jsonl   <- one EventSchema JSON per line
            {YYYY-MM-DD}_{batch_id}.meta.json  <- batch metadata / stats
"""

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.schemas.event import EventSchema

logger = logging.getLogger(__name__)

# Default output root (relative to project root — resolved at runtime)
DEFAULT_BATCH_DIR = Path(__file__).resolve().parents[4] / "data" / "batches"


class BatchWriter:
    """
    Writes ingestion batch results to disk as JSONL files.

    Each call to `save_batch` produces two files:
    - ``{batch_dir}/{source}/{date}_{batch_id}.jsonl``  — one serialized EventSchema per line
    - ``{batch_dir}/{source}/{date}_{batch_id}.meta.json`` — batch metadata

    These files are the hand-off point between the ingestion pipeline and the
    LLM enrichment layer.
    """

    def __init__(self, batch_dir: str | Path | None = None):
        """
        Initialize the BatchWriter.

        Args:
            batch_dir: Root directory for batch output. Defaults to
                       ``<project_root>/data/batches/``.
        """
        self.batch_dir = Path(batch_dir) if batch_dir else DEFAULT_BATCH_DIR

    def save_batch(
        self,
        source_name: str,
        events: list[EventSchema],
        batch_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> Path:
        """
        Serialize and save a list of EventSchema objects to a JSONL file.

        Args:
            source_name: Name of the source (e.g. "ra_co", "ticketmaster")
            events: Normalized EventSchema objects to persist
            batch_id: Unique identifier for this batch (typically execution_id)
            metadata: Optional extra metadata to include in the .meta.json file

        Returns:
            Path to the written JSONL file
        """
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        source_dir = self.batch_dir / source_name
        source_dir.mkdir(parents=True, exist_ok=True)

        stem = f"{today}_{batch_id}"
        jsonl_path = source_dir / f"{stem}.jsonl"
        meta_path = source_dir / f"{stem}.meta.json"

        # Write events as JSONL (one JSON object per line)
        written = 0
        errors = 0
        with open(jsonl_path, "w", encoding="utf-8") as f:
            for event in events:
                try:
                    line = event.model_dump_json()
                    f.write(line + "\n")
                    written += 1
                except Exception as e:
                    logger.warning(
                        "Failed to serialize event '%s' (id=%s): %s",
                        event.title,
                        event.event_id,
                        e,
                    )
                    errors += 1

        # Write metadata sidecar
        batch_meta: dict[str, Any] = {
            "source_name": source_name,
            "batch_id": batch_id,
            "date": today,
            "created_at": datetime.now(UTC).isoformat(),
            "total_events": len(events),
            "written_events": written,
            "serialization_errors": errors,
            "jsonl_file": jsonl_path.name,
        }
        if metadata:
            batch_meta.update(metadata)

        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(batch_meta, f, indent=2, ensure_ascii=False)

        logger.info(
            "BatchWriter: saved %d/%d events for '%s' → %s",
            written,
            len(events),
            source_name,
            jsonl_path,
        )
        return jsonl_path

    def load_batch(self, jsonl_path: str | Path) -> list[dict[str, Any]]:
        """
        Load raw dicts from a JSONL batch file.

        Args:
            jsonl_path: Path to a .jsonl batch file

        Returns:
            List of parsed event dicts (not validated as EventSchema)
        """
        path = Path(jsonl_path)
        records: list[dict[str, Any]] = []
        with open(path, encoding="utf-8") as f:
            for line_no, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError as e:
                    logger.warning("Skipping malformed line %d in %s: %s", line_no, path, e)
        return records

    def list_batches(
        self,
        source_name: str | None = None,
        date_prefix: str | None = None,
    ) -> list[Path]:
        """
        List all JSONL batch files, optionally filtered.

        Args:
            source_name: If set, only list files for this source
            date_prefix: If set (e.g. "2026-02"), only list files with this date prefix

        Returns:
            Sorted list of JSONL file paths (oldest first)
        """
        if source_name:
            search_root = self.batch_dir / source_name
        else:
            search_root = self.batch_dir

        if not search_root.exists():
            return []

        pattern = f"{date_prefix}*.jsonl" if date_prefix else "*.jsonl"
        paths = sorted(search_root.rglob(pattern))
        return paths

    def get_batch_metadata(self, jsonl_path: str | Path) -> dict[str, Any] | None:
        """
        Load the metadata sidecar for a given JSONL batch file.

        Args:
            jsonl_path: Path to the .jsonl file

        Returns:
            Metadata dict, or None if the sidecar file doesn't exist
        """
        meta_path = Path(str(jsonl_path).replace(".jsonl", ".meta.json"))
        if not meta_path.exists():
            return None
        with open(meta_path, encoding="utf-8") as f:
            return json.load(f)
