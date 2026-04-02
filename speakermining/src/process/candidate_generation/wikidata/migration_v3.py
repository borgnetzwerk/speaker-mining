"""
Phase 3.1: Migrate v2 raw_queries JSON events to v3 JSONL eventstore format.

This module reads all v2 JSON event files from raw_queries/ directory,
converts them to v3 event format, and appends them to the v3 eventstore
while maintaining continuous sequence numbering.

v2 Format:
  - Location: data/20_candidate_generation/wikidata/raw_queries/
  - Format: Individual JSON files per event
  - Schema: event_version='v2', event_type='query_response', timestamp_utc, payload, etc.

v3 Format (target):
    - Location: data/20_candidate_generation/wikidata/chunks/{chunk_file}
  - Format: JSONL (one JSON object per line)
  - Schema: sequence_num, event_version='v3', event_type, timestamp_utc, recorded_at, payload
"""

import json
import os
import glob
from pathlib import Path
from datetime import datetime
from typing import Iterator, Dict, Any

from .event_writer import EventStore


def count_raw_queries_files(raw_queries_dir: str) -> int:
    """Count total JSON files in raw_queries directory."""
    pattern = os.path.join(raw_queries_dir, "*.json")
    files = glob.glob(pattern)
    return len(files)


def iterate_raw_queries_files(raw_queries_dir: str) -> Iterator[tuple[str, Dict[str, Any]]]:
    """
    Iterate over all v2 raw_queries JSON files in sorted order.
    
    Yields:
        Tuple of (filename, parsed_json_dict)
    """
    pattern = os.path.join(raw_queries_dir, "*.json")
    files = sorted(glob.glob(pattern))  # Sort by filename for determinism
    
    for filepath in files:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                filename = os.path.basename(filepath)
                yield filename, data
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error reading {filepath}: {e}")
            continue


def convert_v2_to_v3_event(v2_event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert a single v2 event to v3 format for EventStore.
    
    Note: EventStore will add sequence_num, event_version='v3', recorded_at
    
    Args:
        v2_event: Parsed v2 JSON event dict
        
    Returns:
        v3 event dict with:
        - event_type: converted from v2
        - timestamp_utc: preserved from v2
        - payload: v2 data wrapped
    """
    v2_payload = v2_event.get("payload", {})
    normalized_query = v2_event.get("normalized_query")
    endpoint = v2_event.get("endpoint")
    query_hash = v2_event.get("query_hash")
    if not query_hash and endpoint and normalized_query:
        import hashlib

        query_hash = hashlib.md5(f"{endpoint}|{normalized_query}".encode("utf-8")).hexdigest()
    
    v3_event = {
        "event_type": v2_event.get("event_type", "query_response"),
        "timestamp_utc": v2_event.get("timestamp_utc"),
        "payload": {
            "endpoint": endpoint,
            "normalized_query": normalized_query,
            "query_hash": query_hash,
            "source_step": v2_event.get("source_step"),
            "status": v2_event.get("status"),
            "key": v2_event.get("key"),
            "http_status": v2_event.get("http_status"),
            "error": v2_event.get("error"),
            "response_data": v2_payload,  # Nest the actual query response
        }
    }
    
    return v3_event


def migrate_v2_to_v3(
    raw_queries_dir: str,
    repo_root: str,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Migrate all v2 raw_queries JSON files to v3 JSONL eventstore.
    
    Args:
        raw_queries_dir: Path to raw_queries/ directory with v2 JSON files
        repo_root: Path to repository root (for EventStore to find chunks/)
        dry_run: If True, don't write files, just report what would happen
        
    Returns:
        Dict with migration statistics:
        {
            'total_migrated': int,
            'starting_sequence_num': int,
            'ending_sequence_num': int,
            'chunk_file': str,
            'elapsed_seconds': float,
            'errors': []
        }
    """
    start_time = datetime.utcnow()
    
    # Initialize event store (this finds the current sequence number)
    event_store = None
    if not dry_run:
        event_store = EventStore(Path(repo_root))
    
    stats = {
        'total_migrated': 0,
        'starting_sequence_num': event_store._next_sequence_num if event_store else 1,
        'ending_sequence_num': (event_store._next_sequence_num if event_store else 1) - 1,
        'chunk_file': None,
        'elapsed_seconds': 0.0,
        'errors': []
    }
    
    # Iterate over all v2 files in order
    for filename, v2_event in iterate_raw_queries_files(raw_queries_dir):
        try:
            # Convert v2 format to v3
            # Note: EventStore will add sequence_num, event_version='v3', recorded_at
            v3_event = convert_v2_to_v3_event(v2_event)
            
            # Append to eventstore
            if not dry_run and event_store:
                seq_num = event_store.append_event(v3_event)
                stats['chunk_file'] = str(event_store.active_chunk_path)
            
            stats['total_migrated'] += 1
            if event_store:
                stats['ending_sequence_num'] = event_store._next_sequence_num - 1
            
        except Exception as e:
            stats['errors'].append({
                'filename': filename,
                'error': str(e),
            })
            print(f"Error migrating {filename}: {e}")
    
    elapsed = (datetime.utcnow() - start_time).total_seconds()
    stats['elapsed_seconds'] = elapsed
    
    return stats


def main():
    """CLI entry point for v2 to v3 migration."""
    from pathlib import Path
    
    # Resolve workspace root
    workspace_root = Path(__file__).resolve().parents[6]
    raw_queries_dir = workspace_root / "data" / "20_candidate_generation" / "wikidata" / "raw_queries"
    
    print(f"Phase 3.1: Migrate v2 raw_queries to v3 JSONL eventstore")
    print(f"  Raw queries input:  {raw_queries_dir}")
    print(f"  Repo root:          {workspace_root}")
    print()
    
    # Count files first
    total_files = count_raw_queries_files(str(raw_queries_dir))
    print(f"Found {total_files} v2 JSON files to migrate")
    print()
    
    # Do dry run first to report
    print("Running dry-run to verify conversion...")
    dry_stats = migrate_v2_to_v3(str(raw_queries_dir), str(workspace_root), dry_run=True)
    print(f"  Would migrate: {dry_stats['total_migrated']} events")
    print(f"  Sequence range: {dry_stats['starting_sequence_num']} - {dry_stats['ending_sequence_num']}")
    if dry_stats['errors']:
        print(f"  Errors during dry-run: {len(dry_stats['errors'])}")
        for err in dry_stats['errors'][:5]:
            print(f"    - {err['filename']}: {err['error']}")
    print()
    
    # Ask for confirmation
    response = input("Proceed with actual migration? (yes/no) ").strip().lower()
    if response != 'yes':
        print("Migration cancelled.")
        return
    
    # Do actual migration
    print("Starting actual migration...")
    stats = migrate_v2_to_v3(str(raw_queries_dir), str(workspace_root), dry_run=False)
    print()
    print(f"Migration complete!")
    print(f"  Migrated: {stats['total_migrated']} events")
    print(f"  Sequence range: {stats['starting_sequence_num']} - {stats['ending_sequence_num']}")
    print(f"  Output chunk: {stats['chunk_file']}")
    print(f"  Elapsed time: {stats['elapsed_seconds']:.2f}s")
    
    if stats['errors']:
        print(f"  Errors: {len(stats['errors'])}")
        for err in stats['errors'][:10]:
            print(f"    - {err['filename']}: {err['error']}")


if __name__ == '__main__':
    main()
