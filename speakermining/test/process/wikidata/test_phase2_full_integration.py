"""Phase 2.4: Integration test for full handler pipeline on realistic sample data."""

from __future__ import annotations

# pyright: reportMissingImports=false

from pathlib import Path
from datetime import timezone, datetime

import pandas as pd

from process.candidate_generation.wikidata.event_log import (
    write_query_event,
    write_candidate_matched_event,
    _chunks_dir,
)
from process.candidate_generation.wikidata.handlers.orchestrator import run_handlers
from process.candidate_generation.wikidata.schemas import build_artifact_paths


def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def test_full_handler_pipeline_on_sample_data(tmp_path: Path) -> None:
    """Test the complete handler pipeline with realistic sample data.
    
    This test:
    1. Emits sample query_response events (entity_fetch, inlinks, outlinks)
    2. Emits sample candidate_matched events  
    3. Runs the handler orchestrator
    4. Validates all handler projections are created correctly
    5. Verifies deterministic outputs (byte-identical on re-run)
    """
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    
    # === Phase 1: Emit query_response events ===
    # Entity fetch events
    write_query_event(
        repo_root,
        endpoint="wikidata_api",
        normalized_query="entity:Q1",
        source_step="entity_fetch",
        status="success",
        key="Q1",
        payload={
            "entities": {
                "Q1": {
                    "id": "Q1",
                    "type": "item",
                    "labels": {"de": {"language": "de", "value": "Test Person"},
                               "en": {"language": "en", "value": "Test Person"}},
                    "descriptions": {"de": {"language": "de", "value": "A test person"},
                                     "en": {"language": "en", "value": "A test person"}},
                    "aliases": {"de": [{"language": "de", "value": "TP"}]},
                    "claims": {
                        "P31": [{"mainsnak": {"snaktype": "value",
                                             "property": "P31",
                                             "datavalue": {"value": {"entity-type": "item", "id": "Q5"},
                                                          "type": "wikibase-entityid"}}}],
                    }
                }
            }
        },
        http_status=200,
        error=None,
    )
    
    write_query_event(
        repo_root,
        endpoint="wikidata_api",
        normalized_query="entity:Q2",
        source_step="entity_fetch",
        status="success",
        key="Q2",
        payload={
            "entities": {
                "Q2": {
                    "id": "Q2",
                    "type": "item",
                    "labels": {"de": {"language": "de", "value": "Test Organization"}},
                    "descriptions": {"de": {"language": "de", "value": "A test organization"}},
                    "aliases": {},
                    "claims": {
                        "P31": [{"mainsnak": {"snaktype": "value",
                                             "property": "P31",
                                             "datavalue": {"value": {"entity-type": "item", "id": "Q43229"},
                                                          "type": "wikibase-entityid"}}}],
                    }
                }
            }
        },
        http_status=200,
        error=None,
    )
    
    # Inlinks query (SPARQL)
    write_query_event(
        repo_root,
        endpoint="wikidata_sparql",
        normalized_query="inlinks:target=Q1;page_size=50;offset=0;order=source_prop",
        source_step="inlinks_fetch",
        status="success",
        key="Q1_limit50_offset0",
        payload={
            "head": {"vars": ["source", "pid"]},
            "results": {"bindings": [
                {"source": {"value": "http://www.wikidata.org/entity/Q3"},
                 "pid": {"value": "http://www.wikidata.org/prop/direct/P50"}},
            ]}
        },
        http_status=200,
        error=None,
    )
    
    # Another property fetch
    write_query_event(
        repo_root,
        endpoint="wikidata_api",
        normalized_query="entity:Q3",
        source_step="entity_fetch",
        status="cache_hit",
        key="Q3",
        payload={
            "entities": {
                "Q3": {
                    "id": "Q3",
                    "type": "item",
                    "labels": {"en": {"language": "en", "value": "Third Entity"}},
                    "descriptions": {},
                    "aliases": {},
                    "claims": {
                        "P279": [{"mainsnak": {"snaktype": "value",
                                              "property": "P279",
                                              "datavalue": {"value": {"entity-type": "item", "id": "Q5"},
                                                           "type": "wikibase-entityid"}}}],
                    }
                }
            }
        },
        http_status=200,
        error=None,
    )
    
    # === Phase 2: Emit candidate_matched events ===
    write_candidate_matched_event(
        repo_root,
        mention_id="m1",
        mention_type="person",
        mention_label="Test Person",
        candidate_id="Q1",
        candidate_label="Test Person (Q1)",
        source="fallback_string",
        context="Found via fallback matching",
    )
    
    write_candidate_matched_event(
        repo_root,
        mention_id="m2",
        mention_type="organization",
        mention_label="Test Organization",
        candidate_id="Q2",
        candidate_label="Test Organization (Q2)",
        source="fallback_string",
        context="Found via fallback matching",
    )
    
    # === Phase 3: Run orchestrator ===
    results = run_handlers(repo_root, batch_size=10)
    
    # === Phase 4: Validate outputs ===
    paths = build_artifact_paths(repo_root)
    
    # Check instances.csv
    instances_csv = paths.instances_csv
    assert instances_csv.exists(), "instances.csv not created"
    instances_df = pd.read_csv(instances_csv)
    assert len(instances_df) >= 2, f"Expected >= 2 instances, got {len(instances_df)}"
    
    # Check classes.csv
    classes_csv = paths.classes_csv
    assert classes_csv.exists(), "classes.csv not created"
    classes_df = pd.read_csv(classes_csv)
    assert "id" in classes_df.columns or "qid" in classes_df.columns, "classes.csv missing 'id' or 'qid' column"
    
    # Check triples.csv
    triples_csv = paths.triples_csv
    assert triples_csv.exists(), "triples.csv not created"
    triples_df = pd.read_csv(triples_csv)
    assert "subject" in triples_df.columns, "triples.csv missing 'subject' column"
    
    # Check query_inventory.csv
    query_csv = paths.query_inventory_csv
    assert query_csv.exists(), "query_inventory.csv not created"
    query_df = pd.read_csv(query_csv)
    assert len(query_df) >= 2, f"Expected >= 2 unique queries, got {len(query_df)}"
    
    # Check fallback_stage_candidates.csv
    candidates_csv = paths.fallback_stage_candidates_csv
    assert candidates_csv.exists(), f"candidates.csv not created at {candidates_csv}"
    candidates_df = pd.read_csv(candidates_csv)
    assert len(candidates_df) >= 2, f"Expected >= 2 candidates, got {len(candidates_df)}"
    assert "mention_id" in candidates_df.columns, "candidates.csv missing 'mention_id' column"
    assert "candidate_id" in candidates_df.columns, "candidates.csv missing 'candidate_id' column"
    
    # === Phase 5: Verify determinism (re-run produces identical outputs) ===
    # Reset handler progress to zero
    handler_registry_path = paths.wikidata_dir / "eventhandler.csv"
    if handler_registry_path.exists():
        handler_registry_path.unlink()
    
    # Delete all projection files
    for csv in [instances_csv, classes_csv, triples_csv, query_csv, candidates_csv]:
        if csv.exists():
            csv.unlink()
    
    # Re-run handlers
    results2 = run_handlers(repo_root, batch_size=10)
    
    # Re-read outputs
    instances_df2 = pd.read_csv(instances_csv)
    classes_df2 = pd.read_csv(classes_csv)
    triples_df2 = pd.read_csv(triples_csv)
    query_df2 = pd.read_csv(query_csv)
    candidates_df2 = pd.read_csv(candidates_csv)
    
    # Verify outputs are identical (determinism test)
    pd.testing.assert_frame_equal(instances_df, instances_df2, check_dtype=False)
    pd.testing.assert_frame_equal(classes_df, classes_df2, check_dtype=False)
    pd.testing.assert_frame_equal(triples_df, triples_df2, check_dtype=False)
    pd.testing.assert_frame_equal(query_df, query_df2, check_dtype=False)
    pd.testing.assert_frame_equal(candidates_df, candidates_df2, check_dtype=False)
    
    # Verify handler registry was written correctly
    assert handler_registry_path.exists(), "eventhandler.csv not created by orchestrator"
    registry_df = pd.read_csv(handler_registry_path)
    assert "handler_name" in registry_df.columns
    assert "last_processed_sequence" in registry_df.columns
    
    # All handlers should have processed at least one event
    for handler_name in ["InstancesHandler", "ClassesHandler", "TripleHandler", 
                          "QueryInventoryHandler", "CandidatesHandler", "BackoffLearningHandler"]:
        assert handler_name in registry_df["handler_name"].values, \
            f"Handler {handler_name} not in registry"
        last_seq = registry_df[registry_df["handler_name"] == handler_name]["last_processed_sequence"].values[0]
        assert last_seq > 0, f"Handler {handler_name} has no progress recorded"


def test_handler_pipeline_with_zero_candidates(tmp_path: Path) -> None:
    """Test handler pipeline handles gracefully when there are no candidate_matched events."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    
    # Only emit one query event, no candidates
    write_query_event(
        repo_root,
        endpoint="wikidata_api",
        normalized_query="entity:Q1",
        source_step="entity_fetch",
        status="success",
        key="Q1",
        payload={
            "entities": {
                "Q1": {
                    "id": "Q1",
                    "type": "item",
                    "labels": {"en": {"language": "en", "value": "Entity"}},
                    "descriptions": {},
                    "aliases": {},
                    "claims": {}
                }
            }
        },
        http_status=200,
        error=None,
    )
    
    # Run orchestrator
    results = run_handlers(repo_root, batch_size=10)
    
    # Verify all outputs are created (even if candidates is empty)
    paths = build_artifact_paths(repo_root)
    for filename, path in [
        ("instances.csv", paths.instances_csv),
        ("classes.csv", paths.classes_csv),
        ("triples.csv", paths.triples_csv),
        ("query_inventory.csv", paths.query_inventory_csv),
        ("fallback_stage_candidates.csv", paths.fallback_stage_candidates_csv),
    ]:
        assert path.exists(), f"{filename} not created at {path}"
        df = pd.read_csv(path)
        # candidates can be empty, others should have at least the test data
        if filename == "fallback_stage_candidates.csv":
            assert df.empty, f"Expected empty {filename}"
        elif filename == "instances.csv":
            assert len(df) >= 1, f"Expected at least 1 instance"
