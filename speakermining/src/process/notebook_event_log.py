from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .io_guardrails import atomic_write_text

NOTEBOOK_21_ID = "notebook_21_candidate_generation_wikidata"


def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _new_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid4().hex[:8]


def _corrupt_backup_path(path: Path) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return path.with_suffix(path.suffix + f".corrupt.{ts}")


def _repair_jsonl_if_needed(path: Path) -> dict[str, int | str] | None:
    """Quarantine malformed JSONL lines and keep valid history in place.

    Returns metadata if a repair occurred, otherwise None.
    """
    if not path.exists():
        return None

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        backup = _corrupt_backup_path(path)
        backup.write_bytes(path.read_bytes())
        atomic_write_text(path, "", encoding="utf-8")
        return {
            "repair_reason": "unicode_decode_error",
            "kept_lines": 0,
            "quarantined_lines": -1,
            "backup_path": str(backup),
        }

    valid_lines: list[str] = []
    invalid_lines: list[str] = []
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
            if isinstance(parsed, dict):
                valid_lines.append(line)
            else:
                invalid_lines.append(raw)
        except json.JSONDecodeError:
            invalid_lines.append(raw)

    if not invalid_lines:
        return None

    backup = _corrupt_backup_path(path)
    backup.parent.mkdir(parents=True, exist_ok=True)
    backup.write_text("\n".join(invalid_lines) + "\n", encoding="utf-8")
    rewritten = "\n".join(valid_lines)
    if rewritten:
        rewritten += "\n"
    atomic_write_text(path, rewritten, encoding="utf-8")
    return {
        "repair_reason": "invalid_json_lines",
        "kept_lines": len(valid_lines),
        "quarantined_lines": len(invalid_lines),
        "backup_path": str(backup),
    }


class NotebookEventLogger:
    def __init__(self, *, repo_root: Path, notebook_id: str, run_id: str) -> None:
        self.repo_root = Path(repo_root)
        self.notebook_id = str(notebook_id)
        self.run_id = str(run_id)
        self._event_counter = 0
        self.path = (
            self.repo_root
            / "data"
            / "logs"
            / "notebooks"
            / f"{self.notebook_id}.events.jsonl"
        )

    def _next_event_id(self) -> str:
        self._event_counter += 1
        return f"evt_{self._event_counter:06d}"

    def append_event(
        self,
        *,
        event_type: str,
        phase: str,
        message: str = "",
        network: dict | None = None,
        rate_limit: dict | None = None,
        budget: dict | None = None,
        entity: dict | None = None,
        query: dict | None = None,
        result: dict | None = None,
        extra: dict | None = None,
    ) -> None:
        event = {
            "timestamp_utc": _iso_now(),
            "notebook_id": self.notebook_id,
            "run_id": self.run_id,
            "phase": str(phase or "unknown"),
            "event_type": str(event_type or "unknown"),
            "event_id": self._next_event_id(),
            "message": str(message or ""),
        }
        if isinstance(network, dict) and network:
            event["network"] = network
        if isinstance(rate_limit, dict) and rate_limit:
            event["rate_limit"] = rate_limit
        if isinstance(budget, dict) and budget:
            event["budget"] = budget
        if isinstance(entity, dict) and entity:
            event["entity"] = entity
        if isinstance(query, dict) and query:
            event["query"] = query
        if isinstance(result, dict) and result:
            event["result"] = result
        if isinstance(extra, dict) and extra:
            event["extra"] = extra

        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(event, ensure_ascii=False)
        try:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
                handle.flush()
        except PermissionError as exc:
            raise RuntimeError(
                (
                    f"Permission denied while appending notebook event log at {self.path}. "
                    "Close any process locking the file and rerun."
                )
            ) from exc

    def log_phase_started(self, phase: str, *, message: str = "") -> None:
        self.append_event(
            event_type="phase_started",
            phase=phase,
            message=message or f"phase started: {phase}",
        )

    def log_phase_finished(self, phase: str, *, message: str = "", extra: dict | None = None) -> None:
        self.append_event(
            event_type="phase_finished",
            phase=phase,
            message=message or f"phase finished: {phase}",
            extra=extra,
        )


_LOGGER_BY_NOTEBOOK: dict[str, NotebookEventLogger] = {}
_STARTED_RUNS: set[tuple[str, str]] = set()


def get_or_create_notebook_logger(repo_root: Path, notebook_id: str) -> NotebookEventLogger:
    notebook_id = str(notebook_id)
    logger = _LOGGER_BY_NOTEBOOK.get(notebook_id)
    if logger is None:
        logger = NotebookEventLogger(
            repo_root=Path(repo_root),
            notebook_id=notebook_id,
            run_id=_new_run_id(),
        )
        repair_meta = _repair_jsonl_if_needed(logger.path)
        _LOGGER_BY_NOTEBOOK[notebook_id] = logger
        if isinstance(repair_meta, dict):
            logger.append_event(
                event_type="log_repaired",
                phase="run_lifecycle",
                message="notebook event log repaired from malformed history lines",
                extra=repair_meta,
            )

    run_key = (notebook_id, logger.run_id)
    if run_key not in _STARTED_RUNS:
        logger.append_event(
            event_type="run_started",
            phase="run_lifecycle",
            message="notebook run started",
        )
        _STARTED_RUNS.add(run_key)

    return logger
