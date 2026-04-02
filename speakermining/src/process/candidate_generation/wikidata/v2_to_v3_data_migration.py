"""One-time v2 to v3 data migration entrypoint.

This module preserves the Phase 3.1 migration logic that was previously run from
notebook code. It is intentionally kept as an explicit, manual operation:

- We do not expect to run it again in normal operations.
- It is retained for disaster-recovery or historical re-import scenarios.
- Re-running on a non-empty eventstore appends additional migrated events.

Use this module only when you intentionally want to import legacy v2 raw query
JSON files from data/20_candidate_generation/wikidata/raw_queries into the v3
JSONL chunk eventstore.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from .migration_v3 import count_raw_queries_files, migrate_v2_to_v3


def run_v2_to_v3_data_migration(
    repo_root: Path,
    *,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Run the preserved v2->v3 data migration.

    Args:
        repo_root: Repository root.
        dry_run: If True, compute stats without writing events.

    Returns:
        Migration statistics returned by migrate_v2_to_v3.
    """
    raw_queries_dir = repo_root / "data" / "20_candidate_generation" / "wikidata" / "raw_queries"
    return migrate_v2_to_v3(str(raw_queries_dir), str(repo_root), dry_run=dry_run)


def main() -> None:
    """CLI entrypoint for one-time migration execution."""
    repo_root = Path(__file__).resolve().parents[6]
    raw_queries_dir = repo_root / "data" / "20_candidate_generation" / "wikidata" / "raw_queries"

    print("[v2_to_v3_data_migration] Preserved one-time migration module")
    print(f"  Repo root: {repo_root}")
    print(f"  Raw queries dir: {raw_queries_dir}")

    total = count_raw_queries_files(str(raw_queries_dir))
    print(f"  Legacy v2 JSON files found: {total}")

    print("\nRunning dry-run first...")
    dry_stats = run_v2_to_v3_data_migration(repo_root, dry_run=True)
    print(f"  Would migrate: {dry_stats['total_migrated']} events")
    print(
        "  Sequence range (estimated): "
        f"{dry_stats['starting_sequence_num']} - {dry_stats['ending_sequence_num']}"
    )

    response = input("\nProceed with actual migration append? (yes/no) ").strip().lower()
    if response != "yes":
        print("Migration cancelled.")
        return

    print("\nRunning actual migration...")
    stats = run_v2_to_v3_data_migration(repo_root, dry_run=False)
    print("Migration complete.")
    print(f"  Migrated: {stats['total_migrated']} events")
    print(f"  Sequence range: {stats['starting_sequence_num']} - {stats['ending_sequence_num']}")
    print(f"  Chunk file: {stats['chunk_file']}")
    print(f"  Elapsed: {stats['elapsed_seconds']:.2f}s")

    if stats.get("errors"):
        print(f"  Errors: {len(stats['errors'])}")
        for err in stats["errors"][:10]:
            print(f"    - {err['filename']}: {err['error']}")


if __name__ == "__main__":
    main()
