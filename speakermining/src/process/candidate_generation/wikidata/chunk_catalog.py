from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from process.io_guardrails import atomic_write_text


def _chunks_dir(repo_root: Path) -> Path:
    return Path(repo_root) / "data" / "20_candidate_generation" / "wikidata" / "chunks"


def _catalog_path(repo_root: Path) -> Path:
    return Path(repo_root) / "data" / "20_candidate_generation" / "wikidata" / "chunk_catalog.csv"


@dataclass(frozen=True)
class ChunkSummary:
    file_name: str
    first_sequence: int | None
    last_sequence: int | None
    status: str
    chunk_id: str
    opened_at: str
    closed_at: str


def _iter_events(path: Path):
    with path.open("r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                # Allow recovery-oriented readers to ignore a trailing partial line.
                break
            if isinstance(event, dict):
                yield event


def _chunk_id_fallback(file_name: str) -> str:
    stem = file_name.rsplit(".", 1)[0]
    return f"chunk_{stem}"


def summarize_chunk(path: Path) -> ChunkSummary:
    first_sequence: int | None = None
    last_sequence: int | None = None
    first_event: dict | None = None
    last_event: dict | None = None

    for event in _iter_events(path):
        seq = event.get("sequence_num")
        if isinstance(seq, int):
            if first_sequence is None:
                first_sequence = seq
            last_sequence = seq
        if first_event is None:
            first_event = event
        last_event = event

    opened_at = ""
    closed_at = ""
    chunk_id = _chunk_id_fallback(path.name)
    status = "active"

    if isinstance(first_event, dict) and first_event.get("event_type") == "eventstore_opened":
        payload = first_event.get("payload", {})
        if isinstance(payload, dict) and payload.get("chunk_id"):
            chunk_id = str(payload.get("chunk_id"))
        opened_at = str(first_event.get("recorded_at", "") or "")

    if isinstance(last_event, dict):
        if not opened_at:
            opened_at = str(last_event.get("recorded_at", "") or "")
        if last_event.get("event_type") == "eventstore_closed":
            payload = last_event.get("payload", {})
            if isinstance(payload, dict) and payload.get("chunk_id"):
                chunk_id = str(payload.get("chunk_id"))
            status = "closed"
            closed_at = str(last_event.get("recorded_at", "") or "")

    return ChunkSummary(
        file_name=path.name,
        first_sequence=first_sequence,
        last_sequence=last_sequence,
        status=status,
        chunk_id=chunk_id,
        opened_at=opened_at,
        closed_at=closed_at,
    )


def rebuild_chunk_catalog(repo_root: Path) -> list[dict]:
    chunks_dir = _chunks_dir(repo_root)
    chunks_dir.mkdir(parents=True, exist_ok=True)
    chunk_files = sorted(chunks_dir.glob("*.jsonl"))

    rows: list[dict] = []
    for chunk_file in chunk_files:
        summary = summarize_chunk(chunk_file)
        rows.append(
            {
                "chunk_id": summary.chunk_id,
                "file_name": summary.file_name,
                "first_sequence": "" if summary.first_sequence is None else str(summary.first_sequence),
                "last_sequence": "" if summary.last_sequence is None else str(summary.last_sequence),
                "status": summary.status,
                "compression": "none",
                "checksum_sha256": "",
                "opened_at": summary.opened_at,
                "closed_at": summary.closed_at,
            }
        )

    header = [
        "chunk_id",
        "file_name",
        "first_sequence",
        "last_sequence",
        "status",
        "compression",
        "checksum_sha256",
        "opened_at",
        "closed_at",
    ]

    # Use manual CSV serialization to keep dependency surface minimal.
    output_rows = [",".join(header)]
    for row in rows:
        escaped = []
        for col in header:
            value = str(row.get(col, "") or "")
            if "," in value or '"' in value:
                value = '"' + value.replace('"', '""') + '"'
            escaped.append(value)
        output_rows.append(",".join(escaped))

    atomic_write_text(_catalog_path(repo_root), "\n".join(output_rows) + "\n", encoding="utf-8")
    return rows
