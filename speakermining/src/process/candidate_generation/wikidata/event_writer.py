from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from .checksums import write_chunk_checksum
from .chunk_catalog import rebuild_chunk_catalog
from .graceful_shutdown import should_terminate


def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _wikidata_dir(repo_root: Path) -> Path:
    return Path(repo_root) / "data" / "20_candidate_generation" / "wikidata"


def _chunks_dir(repo_root: Path) -> Path:
    return _wikidata_dir(repo_root) / "chunks"


def _eventstore_file_name(now_utc: datetime, day_counter: int) -> str:
    return f"eventstore_chunk_{now_utc.strftime('%Y-%m-%d')}_{day_counter:04d}.jsonl"


def _next_day_counter(chunks_dir: Path, now_utc: datetime) -> int:
    prefix = f"eventstore_chunk_{now_utc.strftime('%Y-%m-%d')}_"
    max_counter = 0
    for path in chunks_dir.glob(f"{prefix}*.jsonl"):
        tail = path.stem.rsplit("_", 1)
        if len(tail) != 2:
            continue
        try:
            counter = int(tail[1])
        except ValueError:
            continue
        max_counter = max(max_counter, counter)
    return max_counter + 1


def _truncate_partial_jsonl_tail(path: Path) -> None:
    if not path.exists():
        return

    with path.open("rb+") as f:
        last_valid_end = 0
        while True:
            line_start = f.tell()
            line = f.readline()
            if not line:
                break
            stripped = line.strip()
            if not stripped:
                last_valid_end = f.tell()
                continue
            try:
                json.loads(stripped.decode("utf-8"))
            except Exception:
                f.truncate(line_start)
                break
            last_valid_end = f.tell()

        f.seek(0, os.SEEK_END)
        end_pos = f.tell()
        if last_valid_end < end_pos:
            f.truncate(last_valid_end)


def _iter_events(path: Path):
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                break
            if isinstance(event, dict):
                yield event


def _last_sequence_across_chunks(chunks_dir: Path) -> int:
    max_seq = 0
    for chunk_path in sorted(chunks_dir.glob("*.jsonl")):
        for event in _iter_events(chunk_path):
            seq = event.get("sequence_num")
            if isinstance(seq, int):
                max_seq = max(max_seq, seq)
    return max_seq


def _last_event(path: Path) -> dict | None:
    last: dict | None = None
    for event in _iter_events(path):
        last = event
    return last


def _event_count(path: Path) -> int:
    count = 0
    for _ in _iter_events(path):
        count += 1
    return count


def _chunk_id_from_file_name(path: Path) -> str:
    stem = path.stem
    return f"chunk_{stem}"


class EventStore:
    def __init__(self, repo_root: Path):
        self.repo_root = Path(repo_root)
        self.chunks_dir = _chunks_dir(self.repo_root)
        self.chunks_dir.mkdir(parents=True, exist_ok=True)

        self.active_chunk_path, self._active_chunk_was_created = self._resolve_active_chunk_path()
        _truncate_partial_jsonl_tail(self.active_chunk_path)
        self._next_sequence_num = _last_sequence_across_chunks(self.chunks_dir) + 1
        self._events_in_active_chunk = _event_count(self.active_chunk_path)

        max_events_raw = os.environ.get("WIKIDATA_EVENTSTORE_MAX_EVENTS_PER_CHUNK", "50000")
        try:
            self._max_events_per_chunk = max(0, int(max_events_raw))
        except ValueError:
            self._max_events_per_chunk = 50000

        if self._active_chunk_was_created and self._events_in_active_chunk == 0:
            self._emit_opened_event_for_active_chunk(prev_chunk_id="")

    def _resolve_active_chunk_path(self) -> tuple[Path, bool]:
        chunk_files = sorted(self.chunks_dir.glob("*.jsonl"))
        if chunk_files:
            last_chunk = chunk_files[-1]
            last_event = _last_event(last_chunk)
            if not isinstance(last_event, dict) or last_event.get("event_type") != "eventstore_closed":
                return last_chunk, False

        now_utc = datetime.now(timezone.utc)
        counter = _next_day_counter(self.chunks_dir, now_utc)
        next_name = _eventstore_file_name(now_utc, counter)
        return self.chunks_dir / next_name, True

    def _emit_opened_event_for_active_chunk(self, prev_chunk_id: str) -> None:
        self.append_event(
            {
                "event_type": "eventstore_opened",
                "timestamp_utc": _iso_now(),
                "payload": {
                    "chunk_id": _chunk_id_from_file_name(self.active_chunk_path),
                    "prev_chunk_id": str(prev_chunk_id or ""),
                },
            },
            _allow_rotation=False,
        )

    def _validate_event(self, event: dict) -> None:
        if not isinstance(event, dict):
            raise ValueError("event must be a dict")
        if not str(event.get("event_type", "") or ""):
            raise ValueError("event_type is required")
        if not str(event.get("timestamp_utc", "") or ""):
            raise ValueError("timestamp_utc is required")
        payload = event.get("payload")
        if payload is None:
            event["payload"] = {}
        elif not isinstance(payload, dict):
            raise ValueError("payload must be a dict")

    def _append_jsonl_line(self, chunk_path: Path, event: dict) -> None:
        chunk_path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n"
        with chunk_path.open("a", encoding="utf-8", newline="") as f:
            f.write(line)
            f.flush()
            os.fsync(f.fileno())

    def append_event(self, event: dict, *, _allow_rotation: bool = True) -> int:
        if should_terminate(_wikidata_dir(self.repo_root) / ".shutdown"):
            raise RuntimeError("Termination requested; refusing to append event")

        event_payload = dict(event)
        event_payload.setdefault("timestamp_utc", _iso_now())
        event_payload["event_version"] = "v3"
        event_payload["recorded_at"] = _iso_now()
        event_payload["sequence_num"] = self._next_sequence_num

        self._validate_event(event_payload)
        self._append_jsonl_line(self.active_chunk_path, event_payload)
        seq = self._next_sequence_num
        self._next_sequence_num += 1
        self._events_in_active_chunk += 1

        # Rotate after flush when threshold is reached; boundary writes disable re-rotation.
        if (
            _allow_rotation
            and self._max_events_per_chunk > 0
            and self._events_in_active_chunk >= self._max_events_per_chunk
            and event_payload.get("event_type") not in {"eventstore_closed", "eventstore_opened"}
        ):
            self.rotate_chunk()

        return seq

    def rotate_chunk(self) -> tuple[Path, Path]:
        old_path = self.active_chunk_path
        old_chunk_id = _chunk_id_from_file_name(old_path)

        now = datetime.now(timezone.utc)
        counter = _next_day_counter(self.chunks_dir, now)
        new_path = self.chunks_dir / _eventstore_file_name(now, counter)
        new_chunk_id = _chunk_id_from_file_name(new_path)

        self.append_event(
            {
                "event_type": "eventstore_closed",
                "timestamp_utc": _iso_now(),
                "payload": {
                    "chunk_id": old_chunk_id,
                    "next_chunk_id": new_chunk_id,
                },
            }
            , _allow_rotation=False
        )

        # Closed chunk checksum is persisted immediately after close event is flushed.
        write_chunk_checksum(self.repo_root, old_path)

        self.active_chunk_path = new_path
        self._events_in_active_chunk = 0
        self._emit_opened_event_for_active_chunk(prev_chunk_id=old_chunk_id)

        rebuild_chunk_catalog(self.repo_root)
        return old_path, new_path

    def rebuild_catalog(self) -> list[dict]:
        return rebuild_chunk_catalog(self.repo_root)
