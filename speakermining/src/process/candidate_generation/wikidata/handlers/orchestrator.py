"""Sequential handler orchestrator for v3 event-sourcing projections."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from process.io_guardrails import atomic_write_text
from process.candidate_generation.wikidata.event_log import iter_all_events
from process.candidate_generation.wikidata.handler_registry import HandlerRegistry
from process.candidate_generation.wikidata.handlers.backoff_learning_handler import BackoffLearningHandler
from process.candidate_generation.wikidata.handlers.candidates_handler import CandidatesHandler
from process.candidate_generation.wikidata.handlers.classes_handler import ClassesHandler
from process.candidate_generation.wikidata.handlers.instances_handler import InstancesHandler
from process.candidate_generation.wikidata.handlers.relevancy_handler import RelevancyHandler
from process.candidate_generation.wikidata.handlers.query_inventory_handler import QueryInventoryHandler
from process.candidate_generation.wikidata.handlers.triple_handler import TripleHandler
from process.candidate_generation.wikidata.schemas import build_artifact_paths


_MATERIALIZATION_MODE_INCREMENTAL = "incremental"
_MATERIALIZATION_MODE_FULL_REBUILD = "full_rebuild"


def _normalize_materialization_mode(mode: object) -> str:
    token = str(mode or "").strip().lower()
    if token == _MATERIALIZATION_MODE_FULL_REBUILD:
        return _MATERIALIZATION_MODE_FULL_REBUILD
    return _MATERIALIZATION_MODE_INCREMENTAL


def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _write_handler_run_summary(paths, summary_payload: dict) -> Path:
    run_dir = paths.wikidata_dir / "handler_runs"
    run_dir.mkdir(parents=True, exist_ok=True)
    ts_token = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_path = run_dir / f"handler_run_summary_{ts_token}.json"
    latest_path = run_dir / "handler_run_summary_latest.json"
    content = json.dumps(summary_payload, ensure_ascii=False, indent=2)
    atomic_write_text(run_path, content, encoding="utf-8")
    atomic_write_text(latest_path, content, encoding="utf-8")
    return run_path


def _try_bootstrap_handler_from_projection(handler, output_path: Path) -> tuple[bool, str]:
    bootstrap_fn = getattr(handler, "bootstrap_from_projection", None)
    if not callable(bootstrap_fn):
        return False, "unsupported"
    try:
        ok = bool(bootstrap_fn(output_path))
    except Exception:
        return False, "error"
    return (ok, "projection") if ok else (False, "empty_or_missing")


def run_handlers(
    repo_root: Path,
    batch_size: int = 1000,
    *,
    materialization_mode: str = _MATERIALIZATION_MODE_INCREMENTAL,
) -> dict[str, int]:
    """Run all handlers in deterministic order and update projections.

    Returns a summary mapping handler name -> latest processed sequence.
    """
    batch_size = max(1, int(batch_size))
    normalized_mode = _normalize_materialization_mode(materialization_mode)
    repo_root = Path(repo_root)
    paths = build_artifact_paths(repo_root)
    registry_path = paths.wikidata_dir / "eventhandler.csv"
    registry = HandlerRegistry(registry_path)

    handlers = [
        InstancesHandler(repo_root, handler_registry=registry),
        ClassesHandler(repo_root, handler_registry=registry),
        TripleHandler(repo_root, handler_registry=registry),
        QueryInventoryHandler(repo_root, handler_registry=registry),
        CandidatesHandler(repo_root, handler_registry=registry),
        RelevancyHandler(repo_root, handler_registry=registry),
        BackoffLearningHandler(repo_root, handler_registry=registry),
    ]
    managed_handler_names = {handler.name() for handler in handlers}
    removed_handlers = registry.prune_to_managed_handlers(managed_handler_names)

    output_paths = {
        "InstancesHandler": paths.instances_csv,
        "ClassesHandler": paths.classes_csv,
        "TripleHandler": paths.triples_csv,
        "QueryInventoryHandler": paths.query_inventory_csv,
        "CandidatesHandler": paths.fallback_stage_candidates_csv,
        "RelevancyHandler": paths.relevancy_csv,
        "BackoffLearningHandler": paths.projections_dir / "backoff_pattern_windows.csv",
    }

    all_events = list(iter_all_events(repo_root) or [])
    summary: dict[str, int] = {}
    handler_stats: list[dict] = []
    latest_sequence = max((int(event.get("sequence_num", 0) or 0) for event in all_events), default=0)

    for handler in handlers:
        name = handler.name()
        output_path = output_paths[name]
        registry.register_handler(name, artifact_path=str(output_path))
        before_seq = int(registry.get_progress(name) or 0)
        start_seq = before_seq + 1
        has_existing_artifact = output_path.exists()

        pending = [
            event
            for event in all_events
            if isinstance(event.get("sequence_num"), int) and int(event.get("sequence_num", 0)) >= start_seq
        ]
        materialize_without_pending = bool(
            getattr(handler, "requires_materialize_without_pending", lambda: False)()
        )

        # Incremental default: when there are no new events and a projection already
        # exists, skip replay+rewrite to avoid full rebuild cost on no-op reruns.
        if (
            normalized_mode == _MATERIALIZATION_MODE_INCREMENTAL
            and not pending
            and has_existing_artifact
            and not materialize_without_pending
        ):
            summary[name] = before_seq
            handler_stats.append(
                {
                    "handler_name": name,
                    "artifact_path": str(output_path),
                    "before_sequence": before_seq,
                    "after_sequence": before_seq,
                    "processed_events": 0,
                    "historical_replay_events": 0,
                    "pending_events": 0,
                    "materialization_mode": normalized_mode,
                    "materialization_status": "skipped_up_to_date",
                    "artifact_exists_before_run": bool(has_existing_artifact),
                    "materialization_elapsed_seconds": 0.0,
                    "artifact_size_bytes": int(output_path.stat().st_size if output_path.exists() else 0),
                }
            )
            continue

        replay_history = True
        bootstrap_status = "not_attempted"
        if (
            normalized_mode == _MATERIALIZATION_MODE_INCREMENTAL
            and has_existing_artifact
            and before_seq > 0
        ):
            bootstrapped, bootstrap_source = _try_bootstrap_handler_from_projection(handler, output_path)
            bootstrap_status = "bootstrapped" if bootstrapped else f"bootstrap_failed:{bootstrap_source}"
            if bootstrapped:
                replay_history = False

        processed_history: list[dict] = []
        if replay_history:
            processed_history = [
                event
                for event in all_events
                if isinstance(event.get("sequence_num"), int) and int(event.get("sequence_num", 0)) < start_seq
            ]

            # Handlers maintain in-memory state only. Rehydrate from historical events so
            # incremental runs don't truncate projections when pending events are unrelated.
            if processed_history:
                for i in range(0, len(processed_history), batch_size):
                    batch = processed_history[i : i + batch_size]
                    handler.process_batch(batch)

        if not pending:
            materialization_t0 = perf_counter()
            last_seq = registry.get_progress(name)
            handler.materialize(output_path)
            materialization_elapsed = perf_counter() - materialization_t0
            handler.update_progress(last_seq)
            summary[name] = last_seq
            after_seq = int(last_seq or 0)
            handler_stats.append(
                {
                    "handler_name": name,
                    "artifact_path": str(output_paths[name]),
                    "before_sequence": before_seq,
                    "after_sequence": after_seq,
                    "processed_events": max(0, after_seq - before_seq),
                    "historical_replay_events": int(len(processed_history)),
                    "pending_events": 0,
                    "materialization_mode": normalized_mode,
                    "materialization_status": "materialized_no_pending",
                    "artifact_exists_before_run": bool(has_existing_artifact),
                    "bootstrap_status": bootstrap_status,
                    "materialization_elapsed_seconds": float(round(materialization_elapsed, 6)),
                    "artifact_size_bytes": int(output_path.stat().st_size if output_path.exists() else 0),
                }
            )
            continue

        last_seq = registry.get_progress(name)
        materialization_elapsed_total = 0.0
        for i in range(0, len(pending), batch_size):
            batch = pending[i : i + batch_size]
            handler.process_batch(batch)
            materialization_t0 = perf_counter()
            handler.materialize(output_path)
            materialization_elapsed_total += perf_counter() - materialization_t0
            last_seq = max(int(e.get("sequence_num", 0)) for e in batch)
            handler.update_progress(last_seq)

        summary[name] = last_seq
        after_seq = int(last_seq or 0)
        handler_stats.append(
            {
                "handler_name": name,
                "artifact_path": str(output_paths[name]),
                "before_sequence": before_seq,
                "after_sequence": after_seq,
                "processed_events": max(0, after_seq - before_seq),
                "historical_replay_events": int(len(processed_history)),
                "pending_events": int(len(pending)),
                "materialization_mode": normalized_mode,
                "materialization_status": "materialized_with_pending",
                "artifact_exists_before_run": bool(has_existing_artifact),
                "bootstrap_status": bootstrap_status,
                "materialization_elapsed_seconds": float(round(materialization_elapsed_total, 6)),
                "artifact_size_bytes": int(output_path.stat().st_size if output_path.exists() else 0),
            }
        )

    run_summary = {
        "run_timestamp_utc": _iso_now(),
        "latest_event_sequence": int(latest_sequence),
        "batch_size": int(batch_size),
        "materialization_mode": normalized_mode,
        "stale_handlers_removed": removed_handlers,
        "registry_before_after": registry.snapshot(),
        "handler_stats": handler_stats,
    }
    _write_handler_run_summary(paths, run_summary)

    return summary
