from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
import shutil
from uuid import uuid4

from .cache import _atomic_write_text
from .schemas import STOP_REASONS, build_artifact_paths


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
    return [
        paths.classes_csv,
        paths.instances_csv,
        paths.properties_csv,
        paths.aliases_en_csv,
        paths.aliases_de_csv,
        paths.triples_csv,
        paths.entities_json,
        paths.properties_json,
        paths.triples_events_json,
        paths.query_inventory_csv,
        paths.summary_json,
        paths.core_classes_csv,
        paths.broadcasting_programs_csv,
        paths.graph_stage_resolved_targets_csv,
        paths.graph_stage_unresolved_targets_csv,
        paths.fallback_stage_candidates_csv,
        paths.fallback_stage_eligible_for_expansion_csv,
        paths.fallback_stage_ineligible_csv,
    ]


def _snapshot_dir_for_checkpoint(repo_root: Path, checkpoint_path: Path) -> Path:
    paths = build_artifact_paths(Path(repo_root))
    return paths.checkpoints_dir / "snapshots" / checkpoint_path.stem


def write_checkpoint_snapshot(repo_root: Path, checkpoint_path: Path) -> Path:
    paths = build_artifact_paths(Path(repo_root))
    from .event_writer import reset_event_store_cache
    from .node_store import flush_node_store
    from .query_inventory import materialize_query_inventory
    from .triple_store import flush_triple_events

    reset_event_store_cache(repo_root)
    flush_node_store(repo_root)
    flush_triple_events(repo_root)
    materialize_query_inventory(repo_root)
    snapshot_dir = _snapshot_dir_for_checkpoint(repo_root, checkpoint_path)
    if snapshot_dir.exists():
        shutil.rmtree(snapshot_dir)
    snapshot_dir.mkdir(parents=True, exist_ok=True)

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

    return snapshot_dir


def restore_checkpoint_snapshot(repo_root: Path, checkpoint_path: Path) -> None:
    paths = build_artifact_paths(Path(repo_root))
    from .cache import reset_latest_cached_record_index
    from .event_writer import reset_event_store_cache
    from .node_store import reset_node_store_cache
    from .query_inventory import reset_query_inventory_cache
    from .triple_store import reset_triple_store_cache

    snapshot_dir = _snapshot_dir_for_checkpoint(repo_root, checkpoint_path)
    if not snapshot_dir.exists():
        raise RuntimeError(f"Checkpoint snapshot not found for restore: {checkpoint_path}")

    paths.wikidata_dir.mkdir(parents=True, exist_ok=True)
    reset_latest_cached_record_index(repo_root)
    reset_event_store_cache(repo_root)
    reset_node_store_cache(repo_root)
    reset_query_inventory_cache(repo_root)
    reset_triple_store_cache(repo_root)
    for runtime_file in _runtime_state_files(repo_root):
        runtime_file.unlink(missing_ok=True)

    if paths.raw_queries_dir.exists():
        shutil.rmtree(paths.raw_queries_dir)

    snapshot_files_dir = snapshot_dir / "files"
    for runtime_file in _runtime_state_files(repo_root):
        src = snapshot_files_dir / runtime_file.name
        if src.exists():
            runtime_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, runtime_file)

    snapshot_raw_dir = snapshot_dir / "raw_queries"
    if snapshot_raw_dir.exists():
        shutil.copytree(snapshot_raw_dir, paths.raw_queries_dir)
    else:
        paths.raw_queries_dir.mkdir(parents=True, exist_ok=True)


def write_checkpoint_manifest(repo_root: Path, manifest: CheckpointManifest) -> Path:
    if manifest.stop_reason not in STOP_REASONS:
        raise ValueError(f"Unsupported stop_reason: {manifest.stop_reason}")
    paths = build_artifact_paths(Path(repo_root))
    paths.checkpoints_dir.mkdir(parents=True, exist_ok=True)
    path = paths.checkpoints_dir / _manifest_filename(manifest)
    _atomic_write_text(path, json.dumps(asdict(manifest), ensure_ascii=False, indent=2))
    write_checkpoint_snapshot(repo_root, path)
    return path


def load_latest_checkpoint(repo_root: Path) -> CheckpointManifest | None:
    paths = build_artifact_paths(Path(repo_root))
    if not paths.checkpoints_dir.exists():
        return None
    candidates = sorted(paths.checkpoints_dir.glob("checkpoint__*.json"))
    if not candidates:
        return None
    payload = json.loads(candidates[-1].read_text(encoding="utf-8"))
    return CheckpointManifest(**payload)


def list_checkpoints(repo_root: Path) -> list[Path]:
    paths = build_artifact_paths(Path(repo_root))
    if not paths.checkpoints_dir.exists():
        return []
    return sorted(paths.checkpoints_dir.glob("checkpoint__*.json"))


def delete_checkpoint(path: Path) -> None:
    snapshot_dir = path.parent / "snapshots" / path.stem
    if snapshot_dir.exists():
        shutil.rmtree(snapshot_dir)
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
    shutil.rmtree(paths.wikidata_dir)


def decide_resume_mode(repo_root: Path, requested_mode: str | None) -> dict:
    latest = load_latest_checkpoint(repo_root)
    checkpoints = list_checkpoints(repo_root)
    mode = (requested_mode or "append").strip().lower()
    if mode not in {"append", "restart", "revert"}:
        raise ValueError("requested_mode must be one of: append, restart, revert")
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
