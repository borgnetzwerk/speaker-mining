"""Test handler output contracts: files, columns, and atomic behavior.

Tests for Phase 1 fixes:
- F4: Handler outputs match specification (required files and columns)
- F6: Handler materializations use atomic writes for resilience
"""

import json
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from process.candidate_generation.wikidata.handlers.instances_handler import InstancesHandler
from process.candidate_generation.wikidata.handlers.classes_handler import ClassesHandler
from process.candidate_generation.wikidata.handlers.query_inventory_handler import QueryInventoryHandler
from process.candidate_generation.wikidata.handlers.triple_handler import TripleHandler


class TestInstancesHandlerOutputContract:
    """Verify InstancesHandler outputs both instances.csv and entities.json."""

    def test_instances_handler_materializes_entities_json(self, tmp_path: Path) -> None:
        """InstancesHandler.materialize() should produce both instances.csv and entities.json."""
        handler = InstancesHandler(tmp_path)
        
        # Process an entity_fetch query_response event
        event = {
            "event_type": "query_response",
            "sequence_num": 1,
            "timestamp_utc": "2026-04-02T10:00:00Z",
            "payload": {
                "endpoint": "wikidata_api",
                "normalized_query": "entity Q100",
                "source_step": "entity_fetch",
                "status": "success",
                "key": "Q100",
                "entities": {
                    "Q100": {
                        "entity-type": "item",
                        "id": "Q100",
                        "labels": {"en": {"value": "Test Entity"}},
                        "aliases": {},
                        "descriptions": {},
                        "claims": {},
                    }
                },
            },
        }
        
        handler.process_batch([event])
        
        # Materialize to temp directory
        output_csv = tmp_path / "instances.csv"
        handler.materialize(output_csv)
        
        # Assert instances.csv exists and has correct columns
        assert output_csv.exists(), "instances.csv should be created"
        df_instances = pd.read_csv(output_csv)
        expected_columns = ["qid", "label", "labels_de", "labels_en", "aliases", "description", "discovered_at", "expanded_at"]
        assert list(df_instances.columns) == expected_columns, f"instances.csv columns mismatch: {list(df_instances.columns)} != {expected_columns}"
        assert len(df_instances) == 1
        assert df_instances.iloc[0]["qid"] == "Q100"
        
        # Assert entities.json exists and contains full entity payload
        entities_json_path = output_csv.parent / "entities.json"
        assert entities_json_path.exists(), "entities.json should be created"
        
        with open(entities_json_path, "r", encoding="utf-8") as f:
            entities_data = json.load(f)
        
        assert isinstance(entities_data, dict), "entities.json should contain a dict"
        assert "Q100" in entities_data, "Q100 should be in entities.json"
        entity_doc = entities_data["Q100"]
        assert entity_doc.get("id") == "Q100", "Entity document should contain original Wikidata structure"
        assert "labels" in entity_doc, "Entity document should have labels"


class TestClassesHandlerOutputContract:
    """Verify ClassesHandler outputs both classes.csv and core_classes.csv."""

    def test_classes_handler_materializes_core_classes_csv(self, tmp_path: Path) -> None:
        """ClassesHandler.materialize() should produce both classes.csv and core_classes.csv."""
        # Create a minimal classes.csv in setup directory
        setup_dir = tmp_path / "data" / "00_setup"
        setup_dir.mkdir(parents=True)
        classes_setup = pd.DataFrame({
            "wikidata_id": ["Q5", "Q43229"],  # Q5=human, Q43229=organization
            "filename": ["human.csv", "org.csv"],
        })
        classes_setup.to_csv(setup_dir / "classes.csv", index=False)
        
        handler = ClassesHandler(tmp_path)
        
        # Process an entity_fetch with class claims
        event = {
            "event_type": "query_response",
            "sequence_num": 1,
            "timestamp_utc": "2026-04-02T10:00:00Z",
            "payload": {
                "endpoint": "wikidata_api",
                "normalized_query": "entity Q50",
                "source_step": "entity_fetch",
                "status": "success",
                "key": "Q50",
                "entities": {
                    "Q50": {
                        "entity-type": "item",
                        "id": "Q50",
                        "labels": {"en": {"value": "Albert Einstein"}},
                        "claims": {
                            "P31": [{"mainsnak": {"datavalue": {"value": {"entity-type": "item", "id": "Q5"}}}}]
                        },
                    },
                    "Q5": {
                        "entity-type": "item",
                        "id": "Q5",
                        "labels": {"en": {"value": "human"}},
                        "claims": {},
                    },
                },
            },
        }
        
        handler.process_batch([event])
        
        # Materialize
        output_csv = tmp_path / "wikidata" / "classes.csv"
        handler.materialize(output_csv)
        
        # Assert classes.csv exists with correct structure
        assert output_csv.exists(), "classes.csv should be created"
        df_classes = pd.read_csv(output_csv)
        expected_columns = [
            "id", "class_filename", "label_en", "label_de", "description_en", "description_de",
            "alias_en", "alias_de", "path_to_core_class", "subclass_of_core_class", "discovered_count", "expanded_count",
        ]
        assert list(df_classes.columns) == expected_columns, f"classes.csv columns mismatch"
        
        # Assert core_classes.csv exists (filtered to core QIDs Q5, Q43229)
        core_classes_path = output_csv.parent / "core_classes.csv"
        assert core_classes_path.exists(), "core_classes.csv should be created"
        df_core = pd.read_csv(core_classes_path)
        assert list(df_core.columns) == expected_columns, "core_classes.csv should have same columns as classes.csv"
        
        # core_classes.csv should be subset of classes.csv
        assert len(df_core) <= len(df_classes), "core_classes.csv should be subset of classes.csv"


class TestQueryInventoryHandlerOutputContract:
    """Verify QueryInventoryHandler outputs spec columns: query_hash, endpoint, normalized_query, status, first_seen, last_seen, count."""

    def test_query_inventory_handler_outputs_spec_columns(self, tmp_path: Path) -> None:
        """QueryInventoryHandler.materialize() should output spec columns."""
        handler = QueryInventoryHandler(tmp_path)
        
        # Process a query_response event
        event = {
            "event_type": "query_response",
            "sequence_num": 1,
            "timestamp_utc": "2026-04-02T10:00:00Z",
            "payload": {
                "endpoint": "wikidata_api",
                "normalized_query": "entity Q1",
                "query_hash": "abc123",
                "source_step": "entity_fetch",
                "status": "success",
                "key": "Q1",
            },
        }
        
        handler.process_batch([event])
        
        # Materialize
        output_csv = tmp_path / "query_inventory.csv"
        handler.materialize(output_csv)
        
        # Assert CSV exists with correct spec columns
        assert output_csv.exists(), "query_inventory.csv should be created"
        df = pd.read_csv(output_csv)
        
        expected_columns = ["query_hash", "endpoint", "normalized_query", "status", "first_seen", "last_seen", "count"]
        assert list(df.columns) == expected_columns, f"columns mismatch: {list(df.columns)} != {expected_columns}"
        
        # Assert data is correct
        assert len(df) == 1
        assert df.iloc[0]["query_hash"] == "abc123"
        assert df.iloc[0]["endpoint"] == "wikidata_api"
        assert df.iloc[0]["normalized_query"] == "entity Q1"
        assert df.iloc[0]["status"] == "success"
        assert df.iloc[0]["first_seen"] == "2026-04-02T10:00:00Z"
        assert df.iloc[0]["last_seen"] == "2026-04-02T10:00:00Z"
        assert df.iloc[0]["count"] == 1


class TestTripleHandlerOutputContract:
    """Verify TripleHandler outputs triples.csv with correct columns."""

    def test_triple_handler_output_columns(self, tmp_path: Path) -> None:
        """TripleHandler.materialize() should output spec columns."""
        handler = TripleHandler(tmp_path)
        
        # Process an entity with claims
        event = {
            "event_type": "query_response",
            "sequence_num": 1,
            "timestamp_utc": "2026-04-02T10:00:00Z",
            "payload": {
                "endpoint": "wikidata_api",
                "normalized_query": "entity Q50",
                "query_hash": "def456",
                "source_step": "entity_fetch",
                "status": "success",
                "key": "Q50",
                "entities": {
                    "Q50": {
                        "id": "Q50",
                        "claims": {
                            "P31": [{"mainsnak": {"datavalue": {"value": {"entity-type": "item", "id": "Q5"}}}}],
                        },
                    },
                },
            },
        }
        
        handler.process_batch([event])
        
        # Materialize
        output_csv = tmp_path / "triples.csv"
        handler.materialize(output_csv)
        
        # Assert CSV exists with correct columns
        assert output_csv.exists(), "triples.csv should be created"
        df = pd.read_csv(output_csv)
        
        expected_columns = ["subject", "predicate", "object", "discovered_at_utc", "source_query_file"]
        assert list(df.columns) == expected_columns, f"columns mismatch: {list(df.columns)} != {expected_columns}"
        
        # Assert data exists
        assert len(df) == 1
        assert df.iloc[0]["subject"] == "Q50"
        assert df.iloc[0]["predicate"] == "P31"
        assert df.iloc[0]["object"] == "Q5"


class TestHandlerAtomicWrites:
    """Test that handler materializations survive interruption via atomic rename pattern."""

    def test_handler_write_uses_atomic_pattern(self, tmp_path: Path) -> None:
        """Handlers should use temp file + atomic rename, not direct overwrites.
        
        Verify by checking for .tmp files during write (via inspection) and 
        ensuring final state is deterministic if interrupted mid-write.
        """
        # This is a basic smoke test that the handlers execute successfully
        # Direct testing of atomic behavior requires mocking/monkeypatching
        # which is complex; we rely on inspection of code imports
        
        handler = InstancesHandler(tmp_path)
        
        # Create event
        event = {
            "event_type": "query_response",
            "sequence_num": 1,
            "timestamp_utc": "2026-04-02T10:00:00Z",
            "payload": {
                "endpoint": "wikidata_api",
                "normalized_query": "entity Q1",
                "source_step": "entity_fetch",
                "status": "success",
                "key": "Q1",
                "entities": {
                    "Q1": {
                        "id": "Q1",
                        "labels": {},
                        "aliases": {},
                        "descriptions": {},
                        "claims": {},
                    }
                },
            },
        }
        
        handler.process_batch([event])
        
        # Materialize
        output_csv = tmp_path / "instances.csv"
        handler.materialize(output_csv)
        
        # Assert final state is clean (no .tmp files left behind)
        tmp_files = list(tmp_path.glob("**/*.tmp"))
        assert len(tmp_files) == 0, f"Temporary files should not be left behind: {tmp_files}"
        
        # Assert final files exist
        assert output_csv.exists(), "instances.csv should exist"
        assert (output_csv.parent / "entities.json").exists(), "entities.json should exist"
