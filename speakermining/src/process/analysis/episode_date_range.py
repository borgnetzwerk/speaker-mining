"""
Identify the oldest and newest episodes in the occurrence matrix.

Usage (from repo root):
    python documentation/ToDo/2026-05-15_Speaker_Mining_Paper/review/code/episode_date_range.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve()
while not (REPO / "speakermining").exists():
    REPO = REPO.parent

_src = REPO / "speakermining" / "src"
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from process.analysis.meta_statistics import compute_meta_statistics  # noqa: E402

OUT_JSON = Path(__file__).parent / "results_episode_date_range.json"


def main() -> None:
    print("=" * 72)
    print("  Speaker Mining — Occurrence Matrix Episode Date Range")
    print("=" * 72)

    stats = compute_meta_statistics(REPO)
    ep = stats[stats["stat_group"] == "episode_universe"].set_index("stat_key")["value"]

    result = {
        "oldest_date":           ep.get("episode_universe_oldest_date"),
        "newest_date":           ep.get("episode_universe_newest_date"),
        "n_episodes_with_date":  ep.get("episode_universe_n_with_date"),
        "n_episodes_total":      ep.get("episode_universe_total"),
    }

    # Also pull the notes field for episode id / show info
    ep_notes = stats[stats["stat_group"] == "episode_universe"].set_index("stat_key")["notes"]
    result["oldest_notes"] = ep_notes.get("episode_universe_oldest_date", "")
    result["newest_notes"] = ep_notes.get("episode_universe_newest_date", "")

    print(f"\n  Oldest: {result['oldest_date']}  ({result['oldest_notes']})")
    print(f"  Newest: {result['newest_date']}  ({result['newest_notes']})")
    print(f"\n  Episodes with parsed date: {result['n_episodes_with_date']} / {result['n_episodes_total']}")

    OUT_JSON.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    print(f"\n  Results written to: {OUT_JSON}")
    print("\nDone.")


if __name__ == "__main__":
    main()
