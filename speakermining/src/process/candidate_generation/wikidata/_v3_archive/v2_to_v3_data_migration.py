"""Disabled legacy v2->v3 migration entrypoint.

Clean-slate rework policy retires pre-rework migration/import workflows.
This module remains only to provide an explicit failure mode if invoked.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

def run_v2_to_v3_data_migration(
    repo_root: Path,
    *,
    dry_run: bool = False,
) -> Dict[str, Any]:
    _ = (repo_root, dry_run)
    raise RuntimeError(
        "v2_to_v3_data_migration is disabled under clean-slate rework policy. "
        "Pre-rework imports are not supported."
    )


def main() -> None:
    repo_root = Path(__file__).resolve().parents[6]
    try:
        run_v2_to_v3_data_migration(repo_root, dry_run=True)
    except RuntimeError as exc:
        raise SystemExit(str(exc))


if __name__ == "__main__":
    main()
