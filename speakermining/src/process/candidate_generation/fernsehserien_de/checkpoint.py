from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
import shutil
from uuid import uuid4
import zipfile

import pandas as pd

from process.io_guardrails import atomic_write_csv, atomic_write_text

from .paths import FernsehserienPaths


_UNZIPPED_SNAPSHOT_LIMIT = 3
_NON_DAILY_ZIPPED_LIMIT = 7


@dataclass(frozen=True)
class FernsehserienCheckpointManifest:
    run_id: str
    latest_checkpoint_timestamp: str
    phase: str
    programs_processed: int
    network_calls_used: int
    normalized_events_emitted: int


def _manifest_filename(manifest: FernsehserienCheckpointManifest) -> str:
    ts = str(manifest.latest_checkpoint_timestamp).replace("-", "").replace(":", "")
    unique = uuid4().hex[:8]
    return f"checkpoint__{manifest.run_id}__{ts}__{unique}.json"


def _snapshot_dir_for_checkpoint(paths: FernsehserienPaths, checkpoint_path: Path) -> Path:
    return paths.checkpoints_dir / "snapshots" / checkpoint_path.stem


def _checkpoint_timeline_path(paths: FernsehserienPaths) -> Path:
    return paths.checkpoints_dir / "checkpoint_timeline.jsonl"


def _snapshot_zip_path(snapshot_dir: Path) -> Path:
    return Path(snapshot_dir).with_suffix(".zip")


def _snapshot_timestamp_from_stem(stem: str) -> datetime:
    try:
        _prefix, ts_token, _unique = str(stem).rsplit("__", 2)
        return datetime.strptime(ts_token, "%Y%m%dT%H%M%SZ")
    except Exception:
        return datetime.min


def _snapshot_sort_key(path: Path) -> tuple[datetime, str]:
    stem = Path(path).stem if Path(path).suffix.lower() == ".zip" else Path(path).name
    return (_snapshot_timestamp_from_stem(stem), stem)


def _list_unzipped_snapshot_dirs(paths: FernsehserienPaths) -> list[Path]:
    snapshots_root = paths.checkpoints_dir / "snapshots"
    if not snapshots_root.exists():
        return []
    dirs = [path for path in snapshots_root.iterdir() if path.is_dir()]
    return sorted(dirs, key=_snapshot_sort_key)


def _list_zipped_snapshots(paths: FernsehserienPaths) -> list[Path]:
    snapshots_root = paths.checkpoints_dir / "snapshots"
    if not snapshots_root.exists():
        return []
    zips = [path for path in snapshots_root.iterdir() if path.is_file() and path.suffix.lower() == ".zip"]
    return sorted(zips, key=_snapshot_sort_key)


def _zip_snapshot_dir(snapshot_dir: Path) -> Path:
    snapshot_dir = Path(snapshot_dir)
    zip_path = _snapshot_zip_path(snapshot_dir)
    zip_path.parent.mkdir(parents=True, exist_ok=True)

    zip_path.unlink(missing_ok=True)

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file_path in sorted(snapshot_dir.rglob("*")):
            if not file_path.is_file():
                continue
            rel = file_path.relative_to(snapshot_dir)
            rel_posix = str(rel).replace("\\", "/")
            arcname = f"{snapshot_dir.name}/{rel_posix}"
            zf.write(file_path, arcname)

    shutil.rmtree(snapshot_dir)

    return zip_path


def _extract_snapshot_zip(snapshot_dir: Path) -> bool:
    snapshot_dir = Path(snapshot_dir)
    if snapshot_dir.exists():
        return True

    zip_path = _snapshot_zip_path(snapshot_dir)
    if not zip_path.exists():
        return False

    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(snapshot_dir.parent)
    return snapshot_dir.exists()


def _snapshot_creation_day(path: Path) -> str:
    stem = Path(path).stem if Path(path).suffix.lower() == ".zip" else Path(path).name
    ts = _snapshot_timestamp_from_stem(stem)
    return ts.strftime("%Y-%m-%d") if ts != datetime.min else ""


def _protected_zipped_snapshots(paths: FernsehserienPaths) -> set[Path]:
    protected: dict[str, Path] = {}
    for zip_path in _list_zipped_snapshots(paths):
        day = _snapshot_creation_day(zip_path)
        if not day:
            continue
        current = protected.get(day)
        if current is None or _snapshot_sort_key(zip_path) > _snapshot_sort_key(current):
            protected[day] = zip_path
    return set(protected.values())


def _prune_zipped_snapshots(paths: FernsehserienPaths) -> None:
    protected = _protected_zipped_snapshots(paths)
    removable = [path for path in _list_zipped_snapshots(paths) if path not in protected]
    removable.sort(key=_snapshot_sort_key)

    while len(removable) > _NON_DAILY_ZIPPED_LIMIT:
        victim = removable.pop(0)
        victim.unlink(missing_ok=True)


def _apply_snapshot_retention_policy(paths: FernsehserienPaths) -> None:
    unzipped = _list_unzipped_snapshot_dirs(paths)
    while len(unzipped) > _UNZIPPED_SNAPSHOT_LIMIT:
        oldest = unzipped[0]
        _zip_snapshot_dir(oldest)
        unzipped = _list_unzipped_snapshot_dirs(paths)

    _prune_zipped_snapshots(paths)


def _compute_chunk_catalog(paths: FernsehserienPaths) -> pd.DataFrame:
    rows: list[dict] = []
    for chunk_path in sorted(paths.chunks_dir.glob("*.jsonl")):
        event_count = 0
        min_sequence = None
        max_sequence = None
        with chunk_path.open("r", encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                sequence = int(event.get("sequence_num", 0) or 0)
                event_count += 1
                if min_sequence is None or sequence < min_sequence:
                    min_sequence = sequence
                if max_sequence is None or sequence > max_sequence:
                    max_sequence = sequence
        rows.append(
            {
                "chunk_file": chunk_path.name,
                "event_count": int(event_count),
                "min_sequence": int(min_sequence or 0),
                "max_sequence": int(max_sequence or 0),
            }
        )
    return pd.DataFrame(rows, columns=["chunk_file", "event_count", "min_sequence", "max_sequence"])


def _compute_checksums_text(paths: FernsehserienPaths) -> str:
    lines: list[str] = []
    for chunk_path in sorted(paths.chunks_dir.glob("*.jsonl")):
        digest = hashlib.sha256(chunk_path.read_bytes()).hexdigest()
        lines.append(f"{chunk_path.name} {digest}")
    text = "\n".join(lines)
    if text:
        text += "\n"
    return text


def _append_checkpoint_timeline_event(
    paths: FernsehserienPaths,
    *,
    checkpoint_path: Path,
    snapshot_dir: Path,
    manifest: FernsehserienCheckpointManifest,
) -> None:
    timeline_path = _checkpoint_timeline_path(paths)
    timeline_path.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "event_type": "checkpoint_created",
        "timestamp_utc": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "checkpoint_file": checkpoint_path.name,
        "snapshot_ref": snapshot_dir.name,
        **asdict(manifest),
    }
    with timeline_path.open("a", encoding="utf-8", newline="") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")


def write_checkpoint_snapshot(repo_root: Path, checkpoint_path: Path) -> Path:
    paths = FernsehserienPaths(repo_root=Path(repo_root))
    paths.ensure()

    snapshot_dir = _snapshot_dir_for_checkpoint(paths, checkpoint_path)
    manifest_name = Path(checkpoint_path).name

    preserved_manifest_text: str | None = None
    if Path(checkpoint_path).exists() and Path(checkpoint_path).resolve().parent == snapshot_dir.resolve():
        preserved_manifest_text = Path(checkpoint_path).read_text(encoding="utf-8")

    if snapshot_dir.exists():
        raise RuntimeError(f"Refusing to overwrite existing checkpoint backup directory: {snapshot_dir}")
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    if preserved_manifest_text is not None:
        (snapshot_dir / manifest_name).write_text(preserved_manifest_text, encoding="utf-8")

    if checkpoint_path.exists() and Path(checkpoint_path).resolve().parent != snapshot_dir.resolve():
        shutil.copy2(checkpoint_path, snapshot_dir / checkpoint_path.name)

    files_dir = snapshot_dir / "files"
    files_dir.mkdir(parents=True, exist_ok=True)
    for projection_file in sorted(paths.projections_dir.glob("*")):
        if projection_file.is_file():
            shutil.copy2(projection_file, files_dir / projection_file.name)

    raw_snapshot_dir = snapshot_dir / "raw_queries"
    if paths.raw_queries_dir.exists():
        shutil.copytree(paths.raw_queries_dir, raw_snapshot_dir)
    else:
        raw_snapshot_dir.mkdir(parents=True, exist_ok=True)

    eventstore_snapshot_dir = snapshot_dir / "eventstore"
    eventstore_snapshot_dir.mkdir(parents=True, exist_ok=True)

    chunks_snapshot_dir = eventstore_snapshot_dir / "chunks"
    if paths.chunks_dir.exists():
        shutil.copytree(paths.chunks_dir, chunks_snapshot_dir)
    else:
        chunks_snapshot_dir.mkdir(parents=True, exist_ok=True)

    chunk_catalog_df = _compute_chunk_catalog(paths)
    chunk_catalog_path = paths.runtime_root / "chunk_catalog.csv"
    atomic_write_csv(chunk_catalog_path, chunk_catalog_df, index=False)
    shutil.copy2(chunk_catalog_path, eventstore_snapshot_dir / "chunk_catalog.csv")

    checksums_text = _compute_checksums_text(paths)
    checksums_path = paths.runtime_root / "eventstore_checksums.txt"
    atomic_write_text(checksums_path, checksums_text, encoding="utf-8")
    shutil.copy2(checksums_path, eventstore_snapshot_dir / "eventstore_checksums.txt")

    _apply_snapshot_retention_policy(paths)
    return snapshot_dir


def restore_checkpoint_snapshot(repo_root: Path, checkpoint_path: Path) -> None:
    paths = FernsehserienPaths(repo_root=Path(repo_root))
    paths.ensure()

    snapshot_dir = _snapshot_dir_for_checkpoint(paths, checkpoint_path)
    if not snapshot_dir.exists() and not _extract_snapshot_zip(snapshot_dir):
        raise RuntimeError(f"Checkpoint snapshot not found for restore: {checkpoint_path}")

    if paths.projections_dir.exists():
        shutil.rmtree(paths.projections_dir)
    paths.projections_dir.mkdir(parents=True, exist_ok=True)

    if paths.raw_queries_dir.exists():
        shutil.rmtree(paths.raw_queries_dir)

    if paths.chunks_dir.exists():
        shutil.rmtree(paths.chunks_dir)
    paths.chunks_dir.mkdir(parents=True, exist_ok=True)

    (paths.runtime_root / "chunk_catalog.csv").unlink(missing_ok=True)
    (paths.runtime_root / "eventstore_checksums.txt").unlink(missing_ok=True)

    snapshot_files_dir = snapshot_dir / "files"
    if snapshot_files_dir.exists():
        for src in sorted(snapshot_files_dir.iterdir()):
            if src.is_file():
                shutil.copy2(src, paths.projections_dir / src.name)

    snapshot_raw_dir = snapshot_dir / "raw_queries"
    if snapshot_raw_dir.exists():
        shutil.copytree(snapshot_raw_dir, paths.raw_queries_dir)
    else:
        paths.raw_queries_dir.mkdir(parents=True, exist_ok=True)

    snapshot_eventstore_dir = snapshot_dir / "eventstore"
    snapshot_chunks_dir = snapshot_eventstore_dir / "chunks"
    if snapshot_chunks_dir.exists():
        shutil.copytree(snapshot_chunks_dir, paths.chunks_dir, dirs_exist_ok=True)

    snapshot_chunk_catalog = snapshot_eventstore_dir / "chunk_catalog.csv"
    if snapshot_chunk_catalog.exists():
        shutil.copy2(snapshot_chunk_catalog, paths.runtime_root / "chunk_catalog.csv")

    snapshot_checksums = snapshot_eventstore_dir / "eventstore_checksums.txt"
    if snapshot_checksums.exists():
        shutil.copy2(snapshot_checksums, paths.runtime_root / "eventstore_checksums.txt")


def write_checkpoint_manifest(repo_root: Path, manifest: FernsehserienCheckpointManifest) -> Path:
    paths = FernsehserienPaths(repo_root=Path(repo_root))
    paths.ensure()

    manifest_name = _manifest_filename(manifest)
    snapshot_dir = paths.checkpoints_dir / "snapshots" / Path(manifest_name).stem
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    checkpoint_path = snapshot_dir / manifest_name
    atomic_write_text(checkpoint_path, json.dumps(asdict(manifest), ensure_ascii=False, indent=2), encoding="utf-8")

    snapshot_dir = write_checkpoint_snapshot(Path(repo_root), checkpoint_path)
    _append_checkpoint_timeline_event(
        paths,
        checkpoint_path=checkpoint_path,
        snapshot_dir=snapshot_dir,
        manifest=manifest,
    )
    return checkpoint_path
