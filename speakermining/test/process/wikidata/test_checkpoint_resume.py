from __future__ import annotations

# pyright: reportMissingImports=false

import json
from datetime import datetime
from pathlib import Path
import zipfile

from process.candidate_generation.wikidata.event_log import iter_query_events, write_query_event
from process.candidate_generation.wikidata.checkpoint import (
    CheckpointManifest,
    clear_runtime_artifacts,
    decide_resume_mode,
    load_latest_checkpoint,
    list_checkpoints,
    restore_checkpoint_snapshot,
    write_checkpoint_snapshot,
    write_checkpoint_manifest,
)
from process.candidate_generation.wikidata.expansion_engine import ExpansionConfig, run_graph_expansion_stage, run_seed_expansion
from process.candidate_generation.wikidata.node_store import get_item, upsert_discovered_item
from process.candidate_generation.wikidata.schemas import build_artifact_paths


def test_manifest_required_fields(tmp_path: Path) -> None:
    manifest = CheckpointManifest(
        run_id="run-1",
        start_timestamp="2026-03-31T10:00:00Z",
        latest_checkpoint_timestamp="2026-03-31T10:01:00Z",
        stop_reason="seed_complete",
        seeds_completed=1,
        seeds_remaining=2,
        total_nodes_discovered={"items": 10},
        total_nodes_expanded={"items": 5},
        total_queries=3,
        inlinks_cursor={"offset": 0},
        incomplete=False,
    )
    path = write_checkpoint_manifest(tmp_path, manifest)
    assert path.exists()

    loaded = load_latest_checkpoint(tmp_path)
    assert loaded is not None
    assert loaded.run_id == "run-1"
    assert loaded.stop_reason == "seed_complete"


def test_manifest_filenames_are_unique_with_same_timestamp(tmp_path: Path) -> None:
    manifest = CheckpointManifest(
        run_id="run-1",
        start_timestamp="2026-03-31T10:00:00Z",
        latest_checkpoint_timestamp="2026-03-31T10:01:00Z",
        stop_reason="seed_complete",
        seeds_completed=1,
        seeds_remaining=0,
        total_nodes_discovered={"items": 1},
        total_nodes_expanded={"items": 1},
        total_queries=1,
        inlinks_cursor=None,
        incomplete=False,
    )
    first = write_checkpoint_manifest(tmp_path, manifest)
    second = write_checkpoint_manifest(tmp_path, manifest)

    assert first != second
    assert first.exists()
    assert second.exists()
    assert len(list_checkpoints(tmp_path)) == 2


def test_resume_modes(tmp_path: Path) -> None:
    mode = decide_resume_mode(tmp_path, "append")
    assert mode["mode"] == "append"
    assert mode["has_checkpoint"] is False

    try:
        decide_resume_mode(tmp_path, "restart")
    except ValueError as exc:
        assert "append, revert" in str(exc)
    else:
        raise AssertionError("restart must be rejected")


def test_revert_mode_uses_previous_checkpoint_run_id(tmp_path: Path) -> None:
    first_path = write_checkpoint_manifest(
        tmp_path,
        CheckpointManifest(
            run_id="run-1",
            start_timestamp="2026-03-31T10:00:00Z",
            latest_checkpoint_timestamp="2026-03-31T10:01:00Z",
            stop_reason="seed_complete",
            seeds_completed=1,
            seeds_remaining=1,
            total_nodes_discovered={"items": 1},
            total_nodes_expanded={"items": 1},
            total_queries=1,
            inlinks_cursor=None,
            incomplete=False,
        ),
    )
    paths = build_artifact_paths(tmp_path)
    paths.entities_json.write_text('{"entities": {"Q1": {"id": "Q1"}}}', encoding="utf-8")
    write_checkpoint_snapshot(tmp_path, first_path)

    second_path = write_checkpoint_manifest(
        tmp_path,
        CheckpointManifest(
            run_id="run-2",
            start_timestamp="2026-03-31T11:00:00Z",
            latest_checkpoint_timestamp="2026-03-31T11:01:00Z",
            stop_reason="seed_complete",
            seeds_completed=2,
            seeds_remaining=0,
            total_nodes_discovered={"items": 2},
            total_nodes_expanded={"items": 2},
            total_queries=2,
            inlinks_cursor=None,
            incomplete=False,
        ),
    )
    paths.entities_json.write_text('{"entities": {"Q1": {"id": "Q1"}, "Q2": {"id": "Q2"}}}', encoding="utf-8")
    write_checkpoint_snapshot(tmp_path, second_path)

    result = run_graph_expansion_stage(
        tmp_path,
        seeds=[],
        targets=[],
        core_class_qids=set(),
        config=ExpansionConfig(max_depth=0, max_nodes=0, total_query_budget=0, per_seed_query_budget=0),
        requested_mode="revert",
    )

    checkpoints = list_checkpoints(tmp_path)
    assert len(checkpoints) == 2
    latest = load_latest_checkpoint(tmp_path)
    assert latest is not None
    assert latest.run_id == "run-2"
    assert result.checkpoint_stats["run_id"] == "run-1"
    assert result.checkpoint_stats["resume_mode"] == "append"
    restored_entities = paths.entities_json.read_text(encoding="utf-8")
    assert '"Q2"' not in restored_entities


def test_revert_mode_restores_eventlog_to_previous_checkpoint(tmp_path: Path) -> None:
    write_query_event(
        tmp_path,
        endpoint="wikidata_api",
        normalized_query="entity Q1",
        source_step="entity_fetch",
        status="success",
        key="Q1",
        payload={"entities": {"Q1": {"id": "Q1"}}},
        http_status=200,
        error=None,
    )

    first_path = write_checkpoint_manifest(
        tmp_path,
        CheckpointManifest(
            run_id="run-1",
            start_timestamp="2026-03-31T10:00:00Z",
            latest_checkpoint_timestamp="2026-03-31T10:01:00Z",
            stop_reason="seed_complete",
            seeds_completed=1,
            seeds_remaining=1,
            total_nodes_discovered={"items": 1},
            total_nodes_expanded={"items": 1},
            total_queries=1,
            inlinks_cursor=None,
            incomplete=False,
        ),
    )
    write_checkpoint_snapshot(tmp_path, first_path)

    write_query_event(
        tmp_path,
        endpoint="wikidata_api",
        normalized_query="entity Q2",
        source_step="entity_fetch",
        status="success",
        key="Q2",
        payload={"entities": {"Q2": {"id": "Q2"}}},
        http_status=200,
        error=None,
    )

    second_path = write_checkpoint_manifest(
        tmp_path,
        CheckpointManifest(
            run_id="run-2",
            start_timestamp="2026-03-31T11:00:00Z",
            latest_checkpoint_timestamp="2026-03-31T11:01:00Z",
            stop_reason="seed_complete",
            seeds_completed=2,
            seeds_remaining=0,
            total_nodes_discovered={"items": 2},
            total_nodes_expanded={"items": 2},
            total_queries=2,
            inlinks_cursor=None,
            incomplete=False,
        ),
    )
    write_checkpoint_snapshot(tmp_path, second_path)

    run_graph_expansion_stage(
        tmp_path,
        seeds=[],
        targets=[],
        core_class_qids=set(),
        config=ExpansionConfig(max_depth=0, max_nodes=0, total_query_budget=0, per_seed_query_budget=0),
        requested_mode="revert",
    )

    restored_keys = {
        str(event.get("payload", {}).get("key", ""))
        for event in iter_query_events(tmp_path)
        if isinstance(event, dict)
    }
    assert "Q1" in restored_keys
    assert "Q2" not in restored_keys

def test_checkpoint_snapshot_restores_dynamic_core_projections(tmp_path: Path) -> None:
    import json as _json

    paths = build_artifact_paths(tmp_path)
    paths.projections_dir.mkdir(parents=True, exist_ok=True)
    core_projection_json = paths.projections_dir / "core_persons.json"
    leftovers_projection = paths.instances_leftovers_csv
    leftovers_projection_parquet = leftovers_projection.with_suffix(".parquet")

    import pandas as pd
    core_projection_json.write_text('{"Q100": {"id": "Q100"}}', encoding="utf-8")
    leftovers_projection.write_text("id\nQ999\n", encoding="utf-8")
    pd.DataFrame([{"id": "Q999"}]).to_parquet(leftovers_projection_parquet, index=False)

    checkpoint_path = write_checkpoint_manifest(
        tmp_path,
        CheckpointManifest(
            run_id="run-1",
            start_timestamp="2026-03-31T10:00:00Z",
            latest_checkpoint_timestamp="2026-03-31T10:01:00Z",
            stop_reason="seed_complete",
            seeds_completed=1,
            seeds_remaining=0,
            total_nodes_discovered={"items": 1},
            total_nodes_expanded={"items": 1},
            total_queries=1,
            inlinks_cursor=None,
            incomplete=False,
        ),
    )

    # Simulate drift after checkpoint.
    core_projection_json.unlink(missing_ok=True)
    leftovers_projection.write_text("id\nQ888\n", encoding="utf-8")
    leftovers_projection_parquet.unlink(missing_ok=True)

    restore_checkpoint_snapshot(tmp_path, checkpoint_path)

    assert core_projection_json.exists()
    assert leftovers_projection.exists()
    assert leftovers_projection_parquet.exists()
    assert "Q100" in _json.loads(core_projection_json.read_text(encoding="utf-8"))
    assert "Q999" in leftovers_projection.read_text(encoding="utf-8")


def test_restart_mode_is_rejected(tmp_path: Path) -> None:
    paths = build_artifact_paths(tmp_path)
    paths.wikidata_dir.mkdir(parents=True, exist_ok=True)
    marker = paths.wikidata_dir / "stale_marker.txt"
    marker.write_text("stale", encoding="utf-8")

    try:
        run_graph_expansion_stage(
            tmp_path,
            seeds=[],
            targets=[],
            core_class_qids=set(),
            config=ExpansionConfig(max_depth=0, max_nodes=0, total_query_budget=0, per_seed_query_budget=0),
            requested_mode="restart",
        )
    except ValueError as exc:
        assert "append, revert" in str(exc)
    else:
        raise AssertionError("restart must be rejected")

    assert marker.exists()


def test_clear_runtime_artifacts_resets_cached_store_state(tmp_path: Path) -> None:
    upsert_discovered_item(
        tmp_path,
        "Q1",
        {
            "id": "Q1",
            "labels": {"en": {"value": "Cached Example"}},
            "descriptions": {},
            "aliases": {},
            "claims": {"P31": [], "P279": []},
        },
        "2026-03-31T12:00:00Z",
    )

    assert get_item(tmp_path, "Q1") is not None

    clear_runtime_artifacts(tmp_path)

    assert get_item(tmp_path, "Q1") is None
    assert not build_artifact_paths(tmp_path).entities_json.exists()


def test_partial_seed_budget_stop_does_not_increment_completed_count(tmp_path: Path, monkeypatch) -> None:
    manifests: list[CheckpointManifest] = []

    def _fake_run_seed_expansion(*args, **kwargs):
        _ = (args, kwargs)
        return {
            "seed_qid": "Q100",
            "discovered_qids": {"Q100"},
            "expanded_qids": {"Q100"},
            "network_queries": 1,
            "stop_reason": "per_seed_budget_exhausted",
            "inlinks_cursor": {"seed_qid": "Q100", "target_qid": "Q100", "offset": 0, "page_index": 0, "exhausted": False},
        }

    def _fake_write_checkpoint_manifest(_repo_root, manifest):
        manifests.append(manifest)
        return tmp_path / "fake_checkpoint.json"

    monkeypatch.setattr("process.candidate_generation.wikidata.expansion_engine.run_seed_expansion", _fake_run_seed_expansion)
    monkeypatch.setattr(
        "process.candidate_generation.wikidata.expansion_engine.write_checkpoint_manifest",
        _fake_write_checkpoint_manifest,
    )

    seeds = [
        {"label": "Seed A", "wikidata_id": "Q100"},
        {"label": "Seed B", "wikidata_id": "Q200"},
    ]
    cfg = ExpansionConfig(max_depth=1, max_nodes=10, total_query_budget=10, per_seed_query_budget=1)

    run_graph_expansion_stage(
        tmp_path,
        seeds=seeds,
        targets=[],
        core_class_qids=set(),
        config=cfg,
        requested_mode="append",
    )

    assert manifests
    assert manifests[-1].seeds_completed == 0
    assert manifests[-1].seeds_remaining == 2
    assert manifests[-1].stop_reason == "per_seed_budget_exhausted"


def test_append_resume_scans_from_first_seed_and_materializes_once(tmp_path: Path, monkeypatch) -> None:
    from process.candidate_generation.wikidata.checkpoint import CheckpointManifest, write_checkpoint_manifest

    write_checkpoint_manifest(
        tmp_path,
        CheckpointManifest(
            run_id="run-1",
            start_timestamp="2026-03-31T10:00:00Z",
            latest_checkpoint_timestamp="2026-03-31T10:01:00Z",
            stop_reason="seed_complete",
            seeds_completed=1,
            seeds_remaining=2,
            total_nodes_discovered={"items": 1},
            total_nodes_expanded={"items": 1},
            total_queries=1,
            inlinks_cursor=None,
            incomplete=False,
        ),
    )

    seen_seeds: list[str] = []
    materialize_calls = {"count": 0}

    def _fake_run_seed_expansion(*args, **kwargs):
        _ = args
        seed = kwargs.get("seed", {})
        seen_seeds.append(str(seed.get("wikidata_id", "")))
        return {
            "seed_qid": str(seed.get("wikidata_id", "")),
            "discovered_qids": set(),
            "expanded_qids": set(),
            "network_queries": 0,
            "neighbor_prefetch_batches_attempted": 0,
            "neighbor_prefetch_batches_succeeded": 0,
            "neighbor_prefetch_candidates_total": 0,
            "stop_reason": "seed_complete",
            "inlinks_cursor": None,
        }

    def _fake_materialize_final(_repo_root, *, run_id):
        _ = (run_id, _repo_root)
        materialize_calls["count"] += 1
        return {
            "seed_id": None,
            "instances_rows": 0,
            "classes_rows": 0,
            "properties_rows": 0,
            "triples_rows": 0,
            "query_inventory_rows": 0,
            "entity_lookup_rows": 0,
            "core_instance_projection_files": 0,
            "instances_leftovers_rows": 0,
        }

    def _fake_write_checkpoint_manifest(_repo_root, manifest):
        _ = (manifest, _repo_root)
        return tmp_path / "fake_checkpoint.json"

    monkeypatch.setattr("process.candidate_generation.wikidata.expansion_engine.run_seed_expansion", _fake_run_seed_expansion)
    monkeypatch.setattr("process.candidate_generation.wikidata.expansion_engine.materialize_final", _fake_materialize_final)
    monkeypatch.setattr("process.candidate_generation.wikidata.expansion_engine.write_checkpoint_manifest", _fake_write_checkpoint_manifest)

    result = run_graph_expansion_stage(
        tmp_path,
        seeds=[
            {"label": "Seed 1", "wikidata_id": "Q1"},
            {"label": "Seed 2", "wikidata_id": "Q2"},
            {"label": "Seed 3", "wikidata_id": "Q3"},
        ],
        targets=[],
        core_class_qids=set(),
        config=ExpansionConfig(max_depth=0, max_nodes=0, total_query_budget=-1, per_seed_query_budget=-1),
        requested_mode="append",
    )

    assert seen_seeds == ["Q2", "Q3"]
    assert materialize_calls["count"] == 1
    assert result.checkpoint_stats["resume_mode"] == "append"


def test_run_seed_expansion_resumes_inlinks_from_cursor_offset(tmp_path: Path, monkeypatch) -> None:
    offsets: list[int] = []

    def _fake_entity(_repo_root, qid, _cache_max_age_days, timeout=30):
        _ = timeout
        return {
            "entities": {
                qid: {
                    "id": qid,
                    "labels": {},
                    "descriptions": {},
                    "aliases": {},
                    "claims": {"P31": [], "P279": []},
                }
            }
        }

    def _fake_outlinks(_repo_root, qid, _entity_payload, _cache_max_age_days):
        return {"qid": qid, "property_ids": [], "linked_qids": [], "edges": []}

    def _fake_inlinks(_repo_root, _qid, _cache_max_age_days, _inlinks_limit, offset=0, timeout=30):
        _ = timeout
        offsets.append(int(offset))
        return {"rows": []}

    monkeypatch.setattr("process.candidate_generation.wikidata.expansion_engine.get_or_fetch_entity", _fake_entity)
    monkeypatch.setattr("process.candidate_generation.wikidata.expansion_engine.get_or_build_outlinks", _fake_outlinks)
    monkeypatch.setattr("process.candidate_generation.wikidata.expansion_engine.get_or_fetch_inlinks", _fake_inlinks)
    monkeypatch.setattr("process.candidate_generation.wikidata.expansion_engine.parse_inlinks_results", lambda payload: payload.get("rows", []))

    cfg = ExpansionConfig(max_depth=0, max_nodes=1, inlinks_limit=200)
    run_seed_expansion(
        tmp_path,
        seed={"label": "Seed", "wikidata_id": "Q100"},
        seed_qids={"Q100"},
        core_class_qids=set(),
        total_budget_remaining=0,
        config=cfg,
        resume_inlinks_cursor={
            "target_qid": "Q100",
            "seed_qid": "Q100",
            "page_index": 1,
            "offset": 200,
            "exhausted": False,
        },
    )

    assert offsets
    assert offsets[0] == 400


def test_run_seed_expansion_stops_gracefully_on_user_interrupt(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "process.candidate_generation.wikidata.expansion_engine._termination_requested",
        lambda _repo_root: True,
    )

    cfg = ExpansionConfig(max_depth=1, max_nodes=10, total_query_budget=-1, per_seed_query_budget=-1)
    summary = run_seed_expansion(
        tmp_path,
        seed={"label": "Seed", "wikidata_id": "Q100"},
        seed_qids={"Q100"},
        core_class_qids=set(),
        total_budget_remaining=-1,
        config=cfg,
        resume_inlinks_cursor=None,
    )

    assert summary["stop_reason"] == "user_interrupted"
    assert summary["network_queries"] == 0


def test_run_seed_expansion_prefetches_neighbors_with_batch_fetch(tmp_path: Path, monkeypatch) -> None:
    batch_calls: list[list[str]] = []
    single_fetch_calls: list[str] = []

    def _fake_get_or_fetch_entity(_repo_root, qid, _cache_max_age_days, timeout=30):
        _ = timeout
        single_fetch_calls.append(str(qid))
        return {
            "entities": {
                str(qid): {
                    "id": str(qid),
                    "labels": {},
                    "descriptions": {},
                    "aliases": {},
                    "claims": {"P31": [], "P279": []},
                }
            }
        }

    def _fake_get_or_fetch_entities_batch(_repo_root, qids, _cache_max_age_days, timeout=30):
        _ = timeout
        qid_list = sorted(str(qid) for qid in qids)
        batch_calls.append(qid_list)
        return {
            qid: {
                "entities": {
                    qid: {
                        "id": qid,
                        "labels": {},
                        "descriptions": {},
                        "aliases": {},
                        "claims": {"P31": [], "P279": []},
                    }
                }
            }
            for qid in qid_list
        }

    def _fake_outlinks(_repo_root, qid, _entity_payload, _cache_max_age_days):
        if str(qid) == "Q100":
            return {
                "qid": "Q100",
                "property_ids": [],
                "linked_qids": ["Q200", "Q201"],
                "edges": [],
            }
        return {"qid": str(qid), "property_ids": [], "linked_qids": [], "edges": []}

    def _fake_inlinks(_repo_root, _qid, _cache_max_age_days, _inlinks_limit, offset=0, timeout=30):
        _ = (offset, timeout)
        return {"rows": []}

    monkeypatch.setattr("process.candidate_generation.wikidata.expansion_engine.get_or_fetch_entity", _fake_get_or_fetch_entity)
    monkeypatch.setattr(
        "process.candidate_generation.wikidata.expansion_engine.get_or_fetch_entities_batch",
        _fake_get_or_fetch_entities_batch,
    )
    monkeypatch.setattr("process.candidate_generation.wikidata.expansion_engine.get_or_build_outlinks", _fake_outlinks)
    monkeypatch.setattr("process.candidate_generation.wikidata.expansion_engine.get_or_fetch_inlinks", _fake_inlinks)
    monkeypatch.setattr("process.candidate_generation.wikidata.expansion_engine.parse_inlinks_results", lambda payload: payload.get("rows", []))

    cfg = ExpansionConfig(max_depth=0, max_nodes=10, total_query_budget=-1, per_seed_query_budget=-1)
    summary = run_seed_expansion(
        tmp_path,
        seed={"label": "Seed", "wikidata_id": "Q100"},
        seed_qids={"Q100"},
        core_class_qids=set(),
        total_budget_remaining=-1,
        config=cfg,
        resume_inlinks_cursor=None,
    )

    assert batch_calls == [["Q200", "Q201"]]
    assert single_fetch_calls == ["Q100", "Q200", "Q201"]
    assert "Q200" in summary["discovered_qids"]
    assert "Q201" in summary["discovered_qids"]
    assert summary["neighbor_prefetch_batches_attempted"] == 1
    assert summary["neighbor_prefetch_batches_succeeded"] == 1
    assert summary["neighbor_prefetch_candidates_total"] == 2


def _manifest_for(run_id: str, ts: str, *, total_queries: int = 1) -> CheckpointManifest:
    return CheckpointManifest(
        run_id=run_id,
        start_timestamp=ts,
        latest_checkpoint_timestamp=ts,
        stop_reason="seed_complete",
        seeds_completed=1,
        seeds_remaining=0,
        total_nodes_discovered={"items": total_queries},
        total_nodes_expanded={"items": total_queries},
        total_queries=total_queries,
        inlinks_cursor=None,
        incomplete=False,
    )


def _snapshot_ts(stem_or_zip_stem: str) -> datetime:
    _prefix, ts_token, _unique = str(stem_or_zip_stem).rsplit("__", 2)
    return datetime.strptime(ts_token, "%Y%m%dT%H%M%SZ")


def test_snapshot_retention_keeps_3_unzipped_and_zips_oldest(tmp_path: Path) -> None:
    manifests: list[Path] = []
    for idx, ts in enumerate(
        [
            "2026-03-31T10:00:00Z",
            "2026-03-31T10:01:00Z",
            "2026-03-31T10:02:00Z",
            "2026-03-31T10:03:00Z",
        ],
        start=1,
    ):
        manifests.append(write_checkpoint_manifest(tmp_path, _manifest_for(f"run-{idx}", ts, total_queries=idx)))

    snapshots_dir = build_artifact_paths(tmp_path).checkpoints_dir / "snapshots"
    unzipped = sorted([path for path in snapshots_dir.iterdir() if path.is_dir()])
    zipped = sorted([path for path in snapshots_dir.iterdir() if path.suffix == ".zip"])

    assert len(unzipped) == 3
    assert len(zipped) == 1
    assert zipped[0].stem == manifests[0].stem
    assert not (snapshots_dir / manifests[0].stem).exists()


def test_snapshot_contains_manifest_and_zip_keeps_manifest(tmp_path: Path) -> None:
    first_manifest = write_checkpoint_manifest(
        tmp_path,
        _manifest_for("run-1", "2026-03-31T10:00:00Z", total_queries=1),
    )
    snapshots_dir = build_artifact_paths(tmp_path).checkpoints_dir / "snapshots"
    first_snapshot_dir = snapshots_dir / first_manifest.stem
    assert (first_snapshot_dir / first_manifest.name).exists()

    # Create enough checkpoints to force zipping of the first snapshot.
    for idx, ts in enumerate(
        [
            "2026-03-31T10:01:00Z",
            "2026-03-31T10:02:00Z",
            "2026-03-31T10:03:00Z",
        ],
        start=2,
    ):
        write_checkpoint_manifest(tmp_path, _manifest_for(f"run-{idx}", ts, total_queries=idx))

    first_zip = snapshots_dir / f"{first_manifest.stem}.zip"
    assert first_zip.exists()
    with zipfile.ZipFile(first_zip, "r") as zf:
        names = set(zf.namelist())
    assert f"{first_manifest.stem}/{first_manifest.name}" in names


def test_restore_checkpoint_snapshot_works_when_snapshot_is_zipped(tmp_path: Path) -> None:
    paths = build_artifact_paths(tmp_path)

    first_path = write_checkpoint_manifest(
        tmp_path,
        _manifest_for("run-1", "2026-03-31T10:00:00Z", total_queries=1),
    )
    paths.entities_json.write_text('{"entities": {"Q1": {"id": "Q1"}}}', encoding="utf-8")
    write_checkpoint_snapshot(tmp_path, first_path)

    for idx, ts in enumerate(
        [
            "2026-03-31T10:01:00Z",
            "2026-03-31T10:02:00Z",
            "2026-03-31T10:03:00Z",
        ],
        start=2,
    ):
        write_checkpoint_manifest(tmp_path, _manifest_for(f"run-{idx}", ts, total_queries=idx))

    snapshots_dir = build_artifact_paths(tmp_path).checkpoints_dir / "snapshots"
    assert (snapshots_dir / f"{first_path.stem}.zip").exists()

    paths.entities_json.write_text('{"entities": {"Q9": {"id": "Q9"}}}', encoding="utf-8")
    from process.candidate_generation.wikidata.checkpoint import restore_checkpoint_snapshot

    restore_checkpoint_snapshot(tmp_path, first_path)

    restored_entities = paths.entities_json.read_text(encoding="utf-8")
    assert '"Q1"' in restored_entities
    assert '"Q9"' not in restored_entities


def test_snapshot_retention_keeps_daily_latest_zips_and_limits_non_daily_to_7(tmp_path: Path) -> None:
    timestamps = [
        "2026-03-31T09:00:00Z",
        "2026-03-31T09:01:00Z",
        "2026-03-31T09:02:00Z",
        "2026-03-31T09:03:00Z",
        "2026-03-31T09:04:00Z",
        "2026-03-31T09:05:00Z",
        "2026-03-31T09:06:00Z",
        "2026-03-31T09:07:00Z",
        "2026-03-31T09:08:00Z",
        "2026-03-31T09:09:00Z",
        "2026-04-01T08:00:00Z",
        "2026-04-01T08:01:00Z",
        "2026-04-01T08:02:00Z",
        "2026-04-01T08:03:00Z",
        "2026-04-01T08:04:00Z",
    ]

    for idx, ts in enumerate(timestamps, start=1):
        write_checkpoint_manifest(tmp_path, _manifest_for(f"run-{idx}", ts, total_queries=idx))

    snapshots_dir = build_artifact_paths(tmp_path).checkpoints_dir / "snapshots"
    zipped = sorted([path for path in snapshots_dir.iterdir() if path.suffix == ".zip"])

    by_day: dict[str, list[Path]] = {}
    for path in zipped:
        ts = _snapshot_ts(path.stem)
        by_day.setdefault(ts.strftime("%Y-%m-%d"), []).append(path)

    protected: set[Path] = set()
    for paths_for_day in by_day.values():
        latest = max(paths_for_day, key=lambda p: _snapshot_ts(p.stem))
        protected.add(latest)

    non_daily = [path for path in zipped if path not in protected]
    assert len(non_daily) <= 7


def test_checkpoint_creation_log_is_jsonl(tmp_path: Path) -> None:
    write_checkpoint_manifest(
        tmp_path,
        _manifest_for("run-1", "2026-03-31T10:00:00Z", total_queries=1),
    )
    write_checkpoint_manifest(
        tmp_path,
        _manifest_for("run-2", "2026-03-31T10:01:00Z", total_queries=2),
    )

    timeline_path = build_artifact_paths(tmp_path).checkpoints_dir / "checkpoint_timeline.jsonl"
    assert timeline_path.exists()

    events = []
    for line in timeline_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        events.append(json.loads(line))

    assert len(events) == 2
    assert all(event.get("event_type") == "checkpoint_created" for event in events)
