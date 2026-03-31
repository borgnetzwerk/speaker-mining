from __future__ import annotations

# pyright: reportMissingImports=false

from pathlib import Path

from process.candidate_generation.wikidata.checkpoint import (
    CheckpointManifest,
    decide_resume_mode,
    load_latest_checkpoint,
    list_checkpoints,
    write_checkpoint_snapshot,
    write_checkpoint_manifest,
)
from process.candidate_generation.wikidata.expansion_engine import ExpansionConfig, run_graph_expansion_stage, run_seed_expansion
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
    assert len(checkpoints) == 1
    latest = load_latest_checkpoint(tmp_path)
    assert latest is not None
    assert latest.run_id == "run-1"
    assert result.checkpoint_stats["resume_mode"] == "append"
    restored_entities = paths.entities_json.read_text(encoding="utf-8")
    assert '"Q2"' not in restored_entities


def test_restart_mode_clears_existing_artifacts(tmp_path: Path) -> None:
    paths = build_artifact_paths(tmp_path)
    paths.wikidata_dir.mkdir(parents=True, exist_ok=True)
    marker = paths.wikidata_dir / "stale_marker.txt"
    marker.write_text("stale", encoding="utf-8")

    result = run_graph_expansion_stage(
        tmp_path,
        seeds=[],
        targets=[],
        core_class_qids=set(),
        config=ExpansionConfig(max_depth=0, max_nodes=0, total_query_budget=0, per_seed_query_budget=0),
        requested_mode="restart",
    )

    assert result.checkpoint_stats["resume_mode"] == "append"
    assert not marker.exists()


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
