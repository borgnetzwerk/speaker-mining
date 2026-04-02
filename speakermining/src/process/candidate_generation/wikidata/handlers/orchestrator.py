"""Sequential handler orchestrator for v3 event-sourcing projections."""

from __future__ import annotations

from pathlib import Path

from process.candidate_generation.wikidata.event_log import iter_all_events
from process.candidate_generation.wikidata.handler_registry import HandlerRegistry
from process.candidate_generation.wikidata.handlers.candidates_handler import CandidatesHandler
from process.candidate_generation.wikidata.handlers.classes_handler import ClassesHandler
from process.candidate_generation.wikidata.handlers.instances_handler import InstancesHandler
from process.candidate_generation.wikidata.handlers.query_inventory_handler import QueryInventoryHandler
from process.candidate_generation.wikidata.handlers.triple_handler import TripleHandler
from process.candidate_generation.wikidata.schemas import build_artifact_paths


def run_handlers(repo_root: Path, batch_size: int = 1000) -> dict[str, int]:
    """Run all handlers in deterministic order and update projections.

    Returns a summary mapping handler name -> latest processed sequence.
    """
    batch_size = max(1, int(batch_size))
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
    ]

    output_paths = {
        "InstancesHandler": paths.instances_csv,
        "ClassesHandler": paths.classes_csv,
        "TripleHandler": paths.triples_csv,
        "QueryInventoryHandler": paths.query_inventory_csv,
        "CandidatesHandler": paths.fallback_stage_candidates_csv,
    }

    all_events = list(iter_all_events(repo_root) or [])
    summary: dict[str, int] = {}

    for handler in handlers:
        name = handler.name()
        registry.register_handler(name, artifact_path=str(output_paths[name]))
        start_seq = registry.get_progress(name) + 1

        pending = [
            event
            for event in all_events
            if isinstance(event.get("sequence_num"), int) and int(event.get("sequence_num", 0)) >= start_seq
        ]

        if not pending:
            last_seq = registry.get_progress(name)
            handler.materialize(output_paths[name])
            handler.update_progress(last_seq)
            summary[name] = last_seq
            continue

        last_seq = registry.get_progress(name)
        for i in range(0, len(pending), batch_size):
            batch = pending[i : i + batch_size]
            handler.process_batch(batch)
            handler.materialize(output_paths[name])
            last_seq = max(int(e.get("sequence_num", 0)) for e in batch)
            handler.update_progress(last_seq)

        summary[name] = last_seq

    return summary
