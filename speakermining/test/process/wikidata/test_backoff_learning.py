from __future__ import annotations

# pyright: reportMissingImports=false

import json
from pathlib import Path

from process.candidate_generation.wikidata.backoff_learning import (
    AdaptiveBackoffController,
    append_backoff_learning_row,
    recommend_query_delay_from_history,
)


def _write_notebook_events(path: Path, events: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(event, ensure_ascii=False) for event in events]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_recommend_query_delay_warns_for_backoff_prone_delay(tmp_path: Path) -> None:
    log_path = tmp_path / "data" / "logs" / "notebooks" / "notebook_21_candidate_generation_wikidata.events.jsonl"
    events = []
    for _ in range(30):
        events.append(
            {
                "event_type": "network_call_started",
                "phase": "stage_a_graph_expansion",
                "rate_limit": {"query_delay_seconds_configured": 0.25},
            }
        )
    for _ in range(4):
        events.append(
            {
                "event_type": "network_backoff_applied",
                "phase": "stage_a_graph_expansion",
                "rate_limit": {"query_delay_seconds_configured": 0.25},
            }
        )
    _write_notebook_events(log_path, events)

    guidance = recommend_query_delay_from_history(tmp_path, configured_delay_seconds=0.25, min_samples=20)

    assert guidance["known_backoff_prone"] is True
    assert float(guidance["recommended_delay_seconds"]) > 0.25
    assert int(guidance["samples"]) >= 30


def test_adaptive_controller_adjusts_after_three_windows() -> None:
    controller = AdaptiveBackoffController(
        Path("."),
        phase="stage_a_graph_expansion",
        interval_seconds=60,
        pattern_heartbeats=3,
        increase_factor=0.05,
        decrease_factor=0.01,
        enabled=True,
    )

    controller._backoff_windows.extend([True, True, True])
    adjustment = controller.decide_adjustment(current_delay_seconds=0.25)
    assert adjustment is not None
    assert adjustment["action"] == "increase"
    assert float(adjustment["new_delay_seconds"]) > 0.25


def test_append_backoff_learning_row_writes_csv(tmp_path: Path) -> None:
    append_backoff_learning_row(
        tmp_path,
        phase="stage_a_graph_expansion",
        action="increase",
        configured_delay_seconds=0.25,
        new_delay_seconds=0.2625,
        window_calls=25,
        window_backoffs=2,
        reason="backoff observed in last 3 heartbeats",
    )

    csv_path = tmp_path / "data" / "20_candidate_generation" / "wikidata" / "backoff_delay_learning.csv"
    text = csv_path.read_text(encoding="utf-8")
    assert "configured_delay_seconds" in text
    assert "stage_a_graph_expansion" in text
    assert "increase" in text
