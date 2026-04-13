from __future__ import annotations

from pathlib import Path

import pandas as pd

from process.candidate_generation.wikidata.handlers.relevancy_handler import RelevancyHandler


def test_relevancy_handler_materializes_monotonic_projection(tmp_path: Path) -> None:
    handler = RelevancyHandler(tmp_path)

    events = [
        {
            "sequence_num": 10,
            "event_type": "relevance_assigned",
            "timestamp_utc": "2026-04-13T10:00:00Z",
            "payload": {
                "entity_qid": "Q1",
                "relevant": True,
                "assignment_type": "seed",
                "relevant_seed_source": "listed_broadcasting_program",
                "is_core_class_instance": True,
            },
        },
        {
            "sequence_num": 11,
            "event_type": "relevance_assigned",
            "timestamp_utc": "2026-04-13T10:00:01Z",
            "payload": {
                "entity_qid": "Q2",
                "relevant": True,
                "assignment_type": "inherited",
                "relevance_inherited_from_qid": "Q1",
                "relevance_inherited_via_property_qid": "P179",
                "relevance_inherited_via_direction": "outlink",
                "is_core_class_instance": True,
            },
        },
        {
            "sequence_num": 12,
            "event_type": "relevance_assigned",
            "timestamp_utc": "2026-04-13T10:00:02Z",
            "payload": {
                "entity_qid": "Q2",
                "relevant": False,
                "assignment_type": "inherited",
            },
        },
    ]

    handler.process_batch(events)

    output_path = tmp_path / "relevancy.csv"
    handler.materialize(output_path)

    frame = pd.read_csv(output_path)
    assert set(frame["qid"]) == {"Q1", "Q2"}

    row_q2 = frame[frame["qid"] == "Q2"].iloc[0].to_dict()
    assert str(row_q2["relevant"]).strip().lower() in {"1", "true"}
    assert str(row_q2["relevance_inherited_from_qid"]) == "Q1"
    assert str(row_q2["relevance_inherited_via_property_qid"]) == "P179"
