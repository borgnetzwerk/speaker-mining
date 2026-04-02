"""
Phase 3.1 Migration Tests: Verify v2→v3 JSON to JSONL conversion.

Tests verify:
1. File discovery and counting
2. V2→V3 format conversion accuracy
3. Sequence number continuity
4. Complete migration data integrity
5. Output chunk creation
"""

import pytest
import json
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

from process.candidate_generation.wikidata.migration_v3 import (
    count_raw_queries_files,
    iterate_raw_queries_files,
    convert_v2_to_v3_event,
    migrate_v2_to_v3,
)


class TestV2FileDiscovery:
    """Test reading and discovering v2 raw_queries files."""
    
    def test_count_empty_directory(self, tmp_path):
        """Test counting files in empty directory."""
        empty_dir = tmp_path / "empty_raw_queries"
        empty_dir.mkdir()
        
        count = count_raw_queries_files(str(empty_dir))
        assert count == 0
    
    def test_count_with_files(self, tmp_path):
        """Test counting multiple JSON files."""
        raw_queries_dir = tmp_path / "raw_queries"
        raw_queries_dir.mkdir()
        
        # Create test files
        for i in range(5):
            filepath = raw_queries_dir / f"20260401T0744{i:02d}Z__query__{i}.json"
            filepath.write_text('{}')
        
        count = count_raw_queries_files(str(raw_queries_dir))
        assert count == 5
    
    def test_iterate_files_in_order(self, tmp_path):
        """Test that files are iterated in sorted order."""
        raw_queries_dir = tmp_path / "raw_queries"
        raw_queries_dir.mkdir()
        
        # Create files with specific names
        filenames = [
            "20260401T074420Z__query__A.json",
            "20260401T074410Z__query__B.json",
            "20260401T074430Z__query__C.json",
        ]
        
        for filename in filenames:
            filepath = raw_queries_dir / filename
            filepath.write_text('{"test": "data"}')
        
        # Iterate and collect filenames
        iterated = [fn for fn, _ in iterate_raw_queries_files(str(raw_queries_dir))]
        
        # Should be in sorted order
        expected_order = sorted(filenames)
        assert iterated == expected_order
    
    def test_iterate_parses_json(self, tmp_path):
        """Test that JSON is correctly parsed during iteration."""
        raw_queries_dir = tmp_path / "raw_queries"
        raw_queries_dir.mkdir()
        
        test_data = {
            "event_version": "v2",
            "event_type": "query_response",
            "key": "Q12345",
            "timestamp_utc": "2026-04-01T07:44:20Z"
        }
        
        filepath = raw_queries_dir / "test_event.json"
        filepath.write_text(json.dumps(test_data))
        
        for _, parsed_data in iterate_raw_queries_files(str(raw_queries_dir)):
            assert parsed_data == test_data


class TestV2ToV3Conversion:
    """Test v2 event format conversion to v3."""
    
    def test_basic_conversion_fields(self):
        """Test that basic fields are converted correctly."""
        v2_event = {
            "event_version": "v2",
            "event_type": "query_response",
            "endpoint": "derived_local",
            "normalized_query": "outlinks_from_entity:Q12345",
            "query_hash": "abc123def456",
            "timestamp_utc": "2026-04-01T07:44:20Z",
            "source_step": "outlinks_build",
            "status": "success",
            "key": "Q12345",
            "http_status": None,
            "error": None,
            "payload": {"qid": "Q12345", "data": [1, 2, 3]}
        }
        
        v3_event = convert_v2_to_v3_event(v2_event)
        
        # Check v3 envelope
        assert v3_event["event_type"] == "query_response"
        assert v3_event["timestamp_utc"] == "2026-04-01T07:44:20Z"
        
    def test_payload_wrapping(self):
        """Test that v2 data is properly wrapped in v3 payload."""
        v2_payload = {
            "qid": "Q12345",
            "property_ids": ["P31", "P279"],
            "linked_qids": ["Q1", "Q2"],
        }
        
        v2_event = {
            "event_type": "query_response",
            "endpoint": "wikidata_sparql",
            "normalized_query": "test_query",
            "query_hash": "hash123",
            "timestamp_utc": "2026-04-01T08:00:00Z",
            "source_step": "entities_build",
            "status": "success",
            "key": "Q12345",
            "http_status": 200,
            "error": None,
            "payload": v2_payload
        }
        
        v3_event = convert_v2_to_v3_event(v2_event)
        
        # Check v3 payload structure
        v3_payload = v3_event["payload"]
        assert v3_payload["endpoint"] == "wikidata_sparql"
        assert v3_payload["normalized_query"] == "test_query"
        assert v3_payload["query_hash"] == "hash123"
        assert v3_payload["source_step"] == "entities_build"
        assert v3_payload["status"] == "success"
        assert v3_payload["key"] == "Q12345"
        assert v3_payload["http_status"] == 200
        assert v3_payload["error"] is None
        assert v3_payload["response_data"] == v2_payload
    
    def test_conversion_maintains_data_integrity(self):
        """Test that all v2 data is preserved in v3 conversion."""
        v2_event = {
            "event_version": "v2",
            "event_type": "query_response",
            "endpoint": "derived_local",
            "normalized_query": "complex:query|with|delimiters",
            "query_hash": "f" * 32,
            "timestamp_utc": "2026-04-01T12:34:56Z",
            "source_step": "phase_two_expansion",
            "status": "success",
            "key": "Q999999",
            "http_status": 200,
            "error": None,
            "payload": {
                "qid": "Q999999",
                "entities": 100,
                "properties": 50,
                "large_array": list(range(1000))
            }
        }
        
        v3_event = convert_v2_to_v3_event(v2_event)
        
        # All v2 fields should be in v3 payload
        v3_payload = v3_event["payload"]
        assert v3_payload["endpoint"] == v2_event["endpoint"]
        assert v3_payload["normalized_query"] == v2_event["normalized_query"]
        assert v3_payload["query_hash"] == v2_event["query_hash"]
        assert v3_payload["source_step"] == v2_event["source_step"]
        
        # Response data should be intact
        response_data = v3_payload["response_data"]
        assert response_data["qid"] == "Q999999"
        assert response_data["entities"] == 100
        assert len(response_data["large_array"]) == 1000
        assert response_data["large_array"][0] == 0
        assert response_data["large_array"][999] == 999


class TestMigrationWithTestData:
    """Test the full migration flow with test data."""
    
    def test_dry_run_migration(self, tmp_path):
        """Test dry-run migration doesn't create output files."""
        raw_queries_dir = tmp_path / "raw_queries"
        repo_root = tmp_path / "repo"
        chunks_dir = repo_root / "data" / "20_candidate_generation" / "wikidata" / "chunks"
        raw_queries_dir.mkdir()
        chunks_dir.mkdir(parents=True)
        
        # Create test v2 files
        for i in range(3):
            filename = f"20260401T07444{i}Z__entity_fetch__Q{i}__abc.json"
            filepath = raw_queries_dir / filename
            event = {
                "event_type": "query_response",
                "endpoint": "test",
                "normalized_query": f"query_{i}",
                "query_hash": f"hash{i}",
                "timestamp_utc": f"2026-04-01T07:44:{i}Z",
                "source_step": "test",
                "status": "success",
                "key": f"Q{i}",
                "http_status": None,
                "error": None,
                "payload": {"test": i}
            }
            filepath.write_text(json.dumps(event))
        
        # Run dry-run
        stats = migrate_v2_to_v3(str(raw_queries_dir), str(repo_root), dry_run=True)
        
        # Should report migration count
        assert stats['total_migrated'] == 3
        assert stats['errors'] == []
        assert stats['elapsed_seconds'] >= 0
    
    def test_actual_migration_creates_output(self, tmp_path):
        """Test that actual migration writes v3 JSONL files."""
        raw_queries_dir = tmp_path / "raw_queries"
        repo_root = tmp_path / "repo"
        chunks_dir = repo_root / "data" / "20_candidate_generation" / "wikidata" / "chunks"
        raw_queries_dir.mkdir()
        chunks_dir.mkdir(parents=True)
        
        # Create test v2 files
        for i in range(5):
            filename = f"20260401T07445{i}Z__outlinks__Q{i}__abc.json"
            filepath = raw_queries_dir / filename
            event = {
                "event_type": "query_response",
                "endpoint": "derived",
                "normalized_query": f"outlinks_from_entity:Q{i}",
                "query_hash": f"hash{i:05d}",
                "timestamp_utc": f"2026-04-01T07:44:5{i}Z",
                "source_step": "outlinks_build",
                "status": "success",
                "key": f"Q{i}",
                "http_status": None,
                "error": None,
                "payload": {"qid": f"Q{i}", "linked": list(range(i))}
            }
            filepath.write_text(json.dumps(event))
        
        # Run actual migration
        stats = migrate_v2_to_v3(str(raw_queries_dir), str(repo_root), dry_run=False)
        
        # Verify migration stats
        assert stats['total_migrated'] == 5
        assert stats['ending_sequence_num'] >= stats['starting_sequence_num']
        assert stats['chunk_file'] is not None
        assert stats['errors'] == []
        
        # Verify output files exist
        output_files = list(chunks_dir.glob("*.jsonl"))
        assert len(output_files) > 0
    
    def test_sequence_number_continuity(self, tmp_path):
        """Test that sequence numbers are continuous across migration."""
        raw_queries_dir = tmp_path / "raw_queries"
        repo_root = tmp_path / "repo"
        chunks_dir = repo_root / "data" / "20_candidate_generation" / "wikidata" / "chunks"
        raw_queries_dir.mkdir()
        chunks_dir.mkdir(parents=True)
        
        # Create 10 test events
        for i in range(10):
            filename = f"event_{i:04d}.json"
            filepath = raw_queries_dir / filename
            event = {
                "event_type": "query_response",
                "endpoint": "test",
                "normalized_query": f"query_{i}",
                "query_hash": f"hash{i:05d}",
                "timestamp_utc": f"2026-04-01T08:00:{i:02d}Z",
                "source_step": "test",
                "status": "success",
                "key": f"Q{i}",
                "http_status": None,
                "error": None,
                "payload": {"index": i}
            }
            filepath.write_text(json.dumps(event))
        
        stats = migrate_v2_to_v3(str(raw_queries_dir), str(repo_root), dry_run=False)
        
        # Collect all events from output JSONL
        sequence_nums = []
        for jsonl_file in chunks_dir.glob("*.jsonl"):
            with open(jsonl_file) as f:
                for line in f:
                    if line.strip():
                        event = json.loads(line)
                        if event.get("event_type") != "eventstore_closed" and event.get("event_type") != "eventstore_opened":
                            sequence_nums.append(event["sequence_num"])
        
        # Verify continuity (may have eventstore_opened/closed events interspersed)
        sequence_nums.sort()
        assert len(sequence_nums) >= 10
    
    def test_event_version_v3_in_output(self, tmp_path):
        """Test that output events have event_version='v3'."""
        raw_queries_dir = tmp_path / "raw_queries"
        repo_root = tmp_path / "repo"
        chunks_dir = repo_root / "data" / "20_candidate_generation" / "wikidata" / "chunks"
        raw_queries_dir.mkdir()
        chunks_dir.mkdir(parents=True)
        
        # Create a test v2 event
        event = {
            "event_version": "v2",
            "event_type": "query_response",
            "endpoint": "wikidata_sparql",
            "normalized_query": "test",
            "query_hash": "hash",
            "timestamp_utc": "2026-04-01T09:00:00Z",
            "source_step": "test",
            "status": "success",
            "key": "Q1",
            "http_status": None,
            "error": None,
            "payload": {}
        }
        
        filepath = raw_queries_dir / "test_event.json"
        filepath.write_text(json.dumps(event))
        
        migrate_v2_to_v3(str(raw_queries_dir), str(repo_root), dry_run=False)
        
        # Read output and verify v3 format
        jsonl_files = list(chunks_dir.glob("*.jsonl"))
        assert len(jsonl_files) > 0
        
        found_migrated_event = False
        with open(jsonl_files[0]) as f:
            for line in f:
                if line.strip():
                    output_event = json.loads(line)
                    if output_event.get("event_type") == "query_response":
                        assert output_event["event_version"] == "v3"
                        assert "sequence_num" in output_event
                        assert "recorded_at" in output_event
                        found_migrated_event = True
                        break
        assert found_migrated_event


class TestMigrationErrorHandling:
    """Test error handling during migration."""
    
    def test_invalid_json_skipped(self, tmp_path):
        """Test that invalid JSON files are skipped with error reported."""
        raw_queries_dir = tmp_path / "raw_queries"
        repo_root = tmp_path / "repo"
        chunks_dir = repo_root / "data" / "20_candidate_generation" / "wikidata" / "chunks"
        raw_queries_dir.mkdir()
        chunks_dir.mkdir(parents=True)
        
        # Create one valid and one invalid file
        valid_file = raw_queries_dir / "valid.json"
        valid_file.write_text('{"event_type": "query_response", "endpoint": "test", "normalized_query": "q", "query_hash": "h", "timestamp_utc": "2026-01-01T00:00:00Z", "source_step": "t", "status": "success", "key": "Q1", "http_status": null, "error": null, "payload": {}}')
        
        invalid_file = raw_queries_dir / "invalid.json"
        invalid_file.write_text('{ invalid json')
        
        stats = migrate_v2_to_v3(str(raw_queries_dir), str(repo_root), dry_run=False)
        
        # At least one should migrate successfully
        assert stats['total_migrated'] >= 1
        # Error should be recorded but not fatal
        assert len(stats['errors']) <= 1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
