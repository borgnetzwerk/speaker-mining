from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
import shutil
from uuid import uuid4
import zipfile

from .cache import _atomic_write_text
from process.io_guardrails import safe_rmtree, safe_unlink
from .schemas import STOP_REASONS, build_artifact_paths


_UNZIPPED_SNAPSHOT_LIMIT = 3
_NON_DAILY_ZIPPED_LIMIT = 7


@dataclass
class CheckpointManifest:
    run_id: str
    start_timestamp: str
    latest_checkpoint_timestamp: str
    stop_reason: str
    seeds_completed: int
    seeds_remaining: int
    total_nodes_discovered: dict[str, int]
    total_nodes_expanded: dict[str, int]
    total_queries: int
    inlinks_cursor: dict | None = None
    incomplete: bool = False


def _manifest_filename(manifest: CheckpointManifest) -> str:
    ts = manifest.latest_checkpoint_timestamp.replace("-", "").replace(":", "")
    unique = uuid4().hex[:8]
    return f"checkpoint__{manifest.run_id}__{ts}__{unique}.json"


def _runtime_state_files(repo_root: Path) -> list[Path]:
    paths = build_artifact_paths(Path(repo_root))
    runtime_files = [
        paths.classes_csv,
        paths.instances_csv,
        paths.instances_leftovers_csv,
        paths.properties_csv,
        paths.aliases_en_csv,
        paths.aliases_de_csv,
        paths.triples_csv,
        paths.class_hierarchy_csv,
        paths.entities_json,
        paths.properties_json,
        paths.triples_events_json,
        paths.query_inventory_csv,
        paths.entity_lookup_index_csv,
        paths.summary_json,
        paths.core_classes_csv,
        paths.root_class_csv,
        paths.other_interesting_classes_csv,
        paths.broadcasting_programs_csv,
        paths.graph_stage_resolved_targets_csv,
        paths.graph_stage_unresolved_targets_csv,
        paths.fallback_stage_candidates_csv,
        paths.fallback_stage_eligible_for_expansion_csv,
        paths.fallback_stage_ineligible_csv,
    ]
    runtime_files.extend(sorted(paths.projections_dir.glob("aliases_*.csv")))
    runtime_files.extend(sorted(paths.projections_dir.glob("instances_core_*.csv")))
    runtime_files.extend(sorted(paths.entity_chunks_dir.glob("*.jsonl")))
    runtime_files.extend(sorted(paths.projections_dir.glob("*.parquet")))
    deduped: list[Path] = []
    seen: set[Path] = set()
    for runtime_file in runtime_files:
        if runtime_file in seen:
            continue
        seen.add(runtime_file)
        deduped.append(runtime_file)
    return deduped


def _snapshot_dir_for_checkpoint(repo_root: Path, checkpoint_path: Path) -> Path:
    paths = build_artifact_paths(Path(repo_root))
    return paths.checkpoints_dir / "snapshots" / checkpoint_path.stem


def _event_store_paths(repo_root: Path) -> dict[str, Path]:
    paths = build_artifact_paths(Path(repo_root))
    return {
        "chunks_dir": paths.wikidata_dir / "chunks",
        "chunk_catalog": paths.wikidata_dir / "chunk_catalog.csv",
        "checksums": paths.wikidata_dir / "eventstore_checksums.txt",
    }


def _snapshots_root(repo_root: Path) -> Path:
    paths = build_artifact_paths(Path(repo_root))
    return paths.checkpoints_dir / "snapshots"


def _checkpoint_timeline_path(repo_root: Path) -> Path:
    paths = build_artifact_paths(Path(repo_root))
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


def _list_unzipped_snapshot_dirs(repo_root: Path) -> list[Path]:
    snapshots_root = _snapshots_root(repo_root)
    if not snapshots_root.exists():
        return []
    dirs = [path for path in snapshots_root.iterdir() if path.is_dir()]
    return sorted(dirs, key=_snapshot_sort_key)


def _list_zipped_snapshots(repo_root: Path) -> list[Path]:
    snapshots_root = _snapshots_root(repo_root)
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


def _protected_zipped_snapshots(repo_root: Path) -> set[Path]:
    protected: dict[str, Path] = {}
    for zip_path in _list_zipped_snapshots(repo_root):
        day = _snapshot_creation_day(zip_path)
        if not day:
            continue
        current = protected.get(day)
        if current is None or _snapshot_sort_key(zip_path) > _snapshot_sort_key(current):
            protected[day] = zip_path
    return set(protected.values())


def _prune_zipped_snapshots(repo_root: Path) -> None:
    protected = _protected_zipped_snapshots(repo_root)
    removable = [path for path in _list_zipped_snapshots(repo_root) if path not in protected]
    removable.sort(key=_snapshot_sort_key)

    while len(removable) > _NON_DAILY_ZIPPED_LIMIT:
        victim = removable.pop(0)
        victim.unlink(missing_ok=True)


def _apply_snapshot_retention_policy(repo_root: Path) -> None:
    unzipped = _list_unzipped_snapshot_dirs(repo_root)
    while len(unzipped) > _UNZIPPED_SNAPSHOT_LIMIT:
        oldest = unzipped[0]
        _zip_snapshot_dir(oldest)
        unzipped = _list_unzipped_snapshot_dirs(repo_root)

    _prune_zipped_snapshots(repo_root)


def _append_checkpoint_timeline_event(repo_root: Path, *, checkpoint_path: Path, snapshot_dir: Path, manifest: CheckpointManifest) -> None:
    timeline_path = _checkpoint_timeline_path(repo_root)
    timeline_path.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "event_type": "checkpoint_created",
        "timestamp_utc": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "checkpoint_file": checkpoint_path.name,
        "snapshot_ref": snapshot_dir.name,
        **asdict(manifest),
    }
    with timeline_path.open("a", encoding="utf-8", newline="") as f:
        f.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")


def write_checkpoint_snapshot(repo_root: Path, checkpoint_path: Path) -> Path:
    paths = build_artifact_paths(Path(repo_root))
    event_store_paths = _event_store_paths(repo_root)
    from .event_writer import reset_event_store_cache
    from .node_store import flush_node_store
    from .query_inventory import materialize_query_inventory
    from .triple_store import flush_triple_events

    reset_event_store_cache(repo_root)
    flush_node_store(repo_root)
    flush_triple_events(repo_root)
    materialize_query_inventory(repo_root)
    snapshot_dir = _snapshot_dir_for_checkpoint(repo_root, checkpoint_path)
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
    for runtime_file in _runtime_state_files(repo_root):
        if runtime_file.exists():
            shutil.copy2(runtime_file, files_dir / runtime_file.name)

    raw_snapshot_dir = snapshot_dir / "raw_queries"
    if paths.raw_queries_dir.exists():
        shutil.copytree(paths.raw_queries_dir, raw_snapshot_dir)
    else:
        raw_snapshot_dir.mkdir(parents=True, exist_ok=True)

    eventstore_snapshot_dir = snapshot_dir / "eventstore"
    eventstore_snapshot_dir.mkdir(parents=True, exist_ok=True)

    chunks_snapshot_dir = eventstore_snapshot_dir / "chunks"
    if event_store_paths["chunks_dir"].exists():
        shutil.copytree(event_store_paths["chunks_dir"], chunks_snapshot_dir)
    else:
        chunks_snapshot_dir.mkdir(parents=True, exist_ok=True)

    for file_key, file_name in (("chunk_catalog", "chunk_catalog.csv"), ("checksums", "eventstore_checksums.txt")):
        src = event_store_paths[file_key]
        if src.exists():
            shutil.copy2(src, eventstore_snapshot_dir / file_name)

    _apply_snapshot_retention_policy(repo_root)

    return snapshot_dir


def restore_checkpoint_snapshot(repo_root: Path, checkpoint_path: Path) -> None:
    paths = build_artifact_paths(Path(repo_root))
    event_store_paths = _event_store_paths(repo_root)
    from .cache import reset_latest_cached_record_index
    from .event_writer import reset_event_store_cache
    from .node_store import reset_node_store_cache
    from .query_inventory import reset_query_inventory_cache
    from .triple_store import reset_triple_store_cache

    snapshot_dir = _snapshot_dir_for_checkpoint(repo_root, checkpoint_path)
    if not snapshot_dir.exists() and not _extract_snapshot_zip(snapshot_dir):
        raise RuntimeError(f"Checkpoint snapshot not found for restore: {checkpoint_path}")

    paths.wikidata_dir.mkdir(parents=True, exist_ok=True)
    reset_latest_cached_record_index(repo_root)
    reset_event_store_cache(repo_root)
    reset_node_store_cache(repo_root)
    reset_query_inventory_cache(repo_root)
    reset_triple_store_cache(repo_root)
    if paths.projections_dir.exists():
        safe_rmtree(paths.projections_dir)
    paths.projections_dir.mkdir(parents=True, exist_ok=True)

    if paths.raw_queries_dir.exists():
        safe_rmtree(paths.raw_queries_dir)

    if event_store_paths["chunks_dir"].exists():
        safe_rmtree(event_store_paths["chunks_dir"])
    safe_unlink(event_store_paths["chunk_catalog"], missing_ok=True)
    safe_unlink(event_store_paths["checksums"], missing_ok=True)

    snapshot_files_dir = snapshot_dir / "files"
    if snapshot_files_dir.exists():
        for src in sorted(snapshot_files_dir.iterdir()):
            if not src.is_file():
                continue
            dst = paths.projections_dir / src.name
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

    snapshot_raw_dir = snapshot_dir / "raw_queries"
    if snapshot_raw_dir.exists():
        shutil.copytree(snapshot_raw_dir, paths.raw_queries_dir)
    else:
        paths.raw_queries_dir.mkdir(parents=True, exist_ok=True)

    snapshot_eventstore_dir = snapshot_dir / "eventstore"
    snapshot_chunks_dir = snapshot_eventstore_dir / "chunks"
    if snapshot_chunks_dir.exists():
        shutil.copytree(snapshot_chunks_dir, event_store_paths["chunks_dir"])

    snapshot_chunk_catalog = snapshot_eventstore_dir / "chunk_catalog.csv"
    if snapshot_chunk_catalog.exists():
        event_store_paths["chunk_catalog"].parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(snapshot_chunk_catalog, event_store_paths["chunk_catalog"])

    snapshot_checksums = snapshot_eventstore_dir / "eventstore_checksums.txt"
    if snapshot_checksums.exists():
        event_store_paths["checksums"].parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(snapshot_checksums, event_store_paths["checksums"])


def write_checkpoint_manifest(repo_root: Path, manifest: CheckpointManifest) -> Path:
    if manifest.stop_reason not in STOP_REASONS:
        raise ValueError(f"Unsupported stop_reason: {manifest.stop_reason}")
    paths = build_artifact_paths(Path(repo_root))
    paths.checkpoints_dir.mkdir(parents=True, exist_ok=True)
    manifest_name = _manifest_filename(manifest)
    snapshot_dir = paths.checkpoints_dir / "snapshots" / Path(manifest_name).stem
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    path = snapshot_dir / manifest_name
    _atomic_write_text(path, json.dumps(asdict(manifest), ensure_ascii=False, indent=2))
    snapshot_dir = write_checkpoint_snapshot(repo_root, path)
    _append_checkpoint_timeline_event(repo_root, checkpoint_path=path, snapshot_dir=snapshot_dir, manifest=manifest)
    return path


def _manifest_paths(repo_root: Path) -> list[Path]:
    paths = build_artifact_paths(Path(repo_root))
    manifests: list[Path] = []

    if paths.checkpoints_dir.exists():
        manifests.extend(paths.checkpoints_dir.glob("checkpoint__*.json"))

    snapshots_root = paths.checkpoints_dir / "snapshots"
    if snapshots_root.exists():
        for snapshot_dir in snapshots_root.iterdir():
            if snapshot_dir.is_dir():
                manifests.extend(snapshot_dir.glob("checkpoint__*.json"))

    return sorted(manifests)


def load_latest_checkpoint(repo_root: Path) -> CheckpointManifest | None:
    candidates = _manifest_paths(repo_root)
    if not candidates:
        return None
    payload = json.loads(candidates[-1].read_text(encoding="utf-8"))
    return CheckpointManifest(**payload)


def list_checkpoints(repo_root: Path) -> list[Path]:
    return _manifest_paths(repo_root)


def delete_checkpoint(path: Path) -> None:
    snapshot_dir = path.parent / "snapshots" / path.stem
    if snapshot_dir.exists():
        shutil.rmtree(snapshot_dir)
    snapshot_zip = snapshot_dir.with_suffix(".zip")
    snapshot_zip.unlink(missing_ok=True)
    try:
        Path(path).unlink(missing_ok=True)
    except Exception:
        return


def clear_runtime_artifacts(repo_root: Path) -> None:
    paths = build_artifact_paths(Path(repo_root))
    from .cache import reset_latest_cached_record_index
    from .event_writer import reset_event_store_cache
    from .node_store import reset_node_store_cache
    from .query_inventory import reset_query_inventory_cache
    from .triple_store import reset_triple_store_cache

    reset_latest_cached_record_index(repo_root)
    reset_event_store_cache(repo_root)
    reset_node_store_cache(repo_root)
    reset_query_inventory_cache(repo_root)
    reset_triple_store_cache(repo_root)
    if not paths.wikidata_dir.exists():
        return

    # Safety policy: preserve fetched-query history and checkpoint lineage.
    # Only remove rebuildable runtime projections/state under projections/.
    if paths.projections_dir.exists():
        safe_rmtree(paths.projections_dir)
    paths.projections_dir.mkdir(parents=True, exist_ok=True)


def decide_resume_mode(repo_root: Path, requested_mode: str | None) -> dict:
    latest = load_latest_checkpoint(repo_root)
    checkpoints = list_checkpoints(repo_root)
    mode = (requested_mode or "append").strip().lower()
    if mode not in {"append", "revert"}:
        raise ValueError("requested_mode must be one of: append, revert")
    previous = None
    if len(checkpoints) >= 2:
        previous_payload = json.loads(checkpoints[-2].read_text(encoding="utf-8"))
        previous = previous_payload
    return {
        "mode": mode,
        "has_checkpoint": latest is not None,
        "latest_checkpoint": asdict(latest) if latest else None,
        "checkpoint_count": len(checkpoints),
        "latest_checkpoint_path": str(checkpoints[-1]) if checkpoints else "",
        "previous_checkpoint": previous,
        "previous_checkpoint_path": str(checkpoints[-2]) if len(checkpoints) >= 2 else "",
    }
