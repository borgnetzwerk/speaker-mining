from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from process.io_guardrails import atomic_write_csv, atomic_write_text


@dataclass(frozen=True)
class RetiredArtifactSpec:
    artifact_name: str
    tokens: tuple[str, ...]


RETIRED_ARTIFACT_SPECS = (
    RetiredArtifactSpec(artifact_name="entities.json", tokens=("entities.json", "entities_json")),
    RetiredArtifactSpec(artifact_name="properties.json", tokens=("properties.json", "properties_json")),
    RetiredArtifactSpec(artifact_name="triple_events.json", tokens=("triple_events.json", "triples_events_json")),
)


def _iter_python_files(repo_root: Path) -> list[Path]:
    source_root = Path(repo_root) / "speakermining" / "src"
    if not source_root.exists():
        return []
    return sorted(source_root.rglob("*.py"))


def _relative_to_repo(repo_root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(repo_root)).replace("\\", "/")
    except Exception:
        return str(path).replace("\\", "/")


def _classify_access_mode(relative_path: str, excerpt: str, context_excerpt: str) -> str:
    path_token = str(relative_path or "").lower()
    text = f"{excerpt}\n{context_excerpt}".lower()

    if path_token.endswith("/schemas.py"):
        return "path_definition"
    if "_load_events" in text or "_load_json" in text or "read_text(" in text:
        return "read"
    if (
        "_atomic_write" in text
        or "atomic_write_" in text
        or "write_text(" in text
        or "to_csv(" in text
        or "flush_" in text
    ):
        return "write_or_flush"
    return "reference"


def _context_excerpt(lines: list[str], line_no: int, window: int = 2) -> str:
    start = max(1, int(line_no) - int(window))
    end = min(len(lines), int(line_no) + int(window))
    parts: list[str] = []
    for idx in range(start, end + 1):
        marker = ">" if idx == line_no else " "
        parts.append(f"{marker}{idx}: {str(lines[idx - 1]).strip()}")
    return "\n".join(parts)


def build_retired_artifact_consumer_inventory(repo_root: Path | str) -> dict:
    repo_root = Path(repo_root)
    rows: list[dict] = []

    for py_path in _iter_python_files(repo_root):
        try:
            lines = py_path.read_text(encoding="utf-8").splitlines()
        except Exception:
            continue

        relative_path = _relative_to_repo(repo_root, py_path)
        for line_no, line in enumerate(lines, start=1):
            for spec in RETIRED_ARTIFACT_SPECS:
                line_lower = str(line or "").lower()
                matched_token = next((token for token in spec.tokens if token in line_lower), "")
                if not matched_token:
                    continue
                excerpt = str(line.strip())
                context_excerpt = _context_excerpt(lines, line_no)
                rows.append(
                    {
                        "artifact_name": spec.artifact_name,
                        "artifact_token": matched_token,
                        "file_path": relative_path,
                        "line_number": int(line_no),
                        "line_excerpt": excerpt,
                        "context_excerpt": context_excerpt,
                        "access_mode": _classify_access_mode(relative_path, excerpt, context_excerpt),
                    }
                )

    inventory_dir = (
        repo_root
        / "data"
        / "20_candidate_generation"
        / "wikidata"
        / "inventory"
    )
    inventory_dir.mkdir(parents=True, exist_ok=True)

    timestamp = pd.Timestamp.utcnow().strftime("%Y%m%dT%H%M%SZ")
    csv_path = inventory_dir / f"retired_artifact_consumers_{timestamp}.csv"
    json_path = inventory_dir / f"retired_artifact_consumers_{timestamp}.json"
    latest_json_path = inventory_dir / "retired_artifact_consumers_latest.json"

    frame = pd.DataFrame(rows, columns=[
        "artifact_name",
        "artifact_token",
        "access_mode",
        "file_path",
        "line_number",
        "line_excerpt",
        "context_excerpt",
    ])
    atomic_write_csv(csv_path, frame, index=False)

    payload = {
        "timestamp_utc": pd.Timestamp.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "row_count": int(len(rows)),
        "artifacts": {
            "csv": str(csv_path),
            "json": str(json_path),
        },
        "rows": rows,
    }
    content = json.dumps(payload, ensure_ascii=False, indent=2)
    atomic_write_text(json_path, content, encoding="utf-8")
    atomic_write_text(latest_json_path, content, encoding="utf-8")
    return payload
