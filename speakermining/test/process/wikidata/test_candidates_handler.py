from __future__ import annotations

# pyright: reportMissingImports=false

from pathlib import Path

import pandas as pd

from process.candidate_generation.wikidata.handlers.candidates_handler import CandidatesHandler


def test_candidates_handler_stub_writes_empty_csv(tmp_path: Path) -> None:
    handler = CandidatesHandler(tmp_path)
    out = tmp_path / "candidates.csv"
    handler.materialize(out)
    df = pd.read_csv(out)
    assert list(df.columns) == ["mention_id", "mention_type", "mention_label", "candidate_id", "candidate_label", "source", "context"]
    assert df.empty


def test_candidates_handler_accepts_candidate_matched_events(tmp_path: Path) -> None:
    handler = CandidatesHandler(tmp_path)
    handler.process_batch(
        [
            {
                "sequence_num": 1,
                "event_type": "candidate_matched",
                "mention_id": "m1",
                "mention_type": "person",
                "mention_label": "John Doe",
                "candidate_id": "Q1",
                "candidate_label": "John Doe (person)",
                "source": "fallback_string",
                "context": "context1",
            },
            {
                "sequence_num": 2,
                "event_type": "candidate_matched",
                "mention_id": "m2",
                "mention_type": "person",
                "mention_label": "Jane Smith",
                "candidate_id": "Q2",
                "candidate_label": "Jane Smith",
                "source": "fallback_string",
                "context": "context2",
            },
        ]
    )

    out = tmp_path / "candidates.csv"
    handler.materialize(out)
    df = pd.read_csv(out)
    assert len(df) == 2
    assert set(df['mention_id']) == {'m1', 'm2'}
    assert set(df['candidate_id']) == {'Q1', 'Q2'}


def test_candidates_handler_sequence_tracking(tmp_path: Path) -> None:
    handler = CandidatesHandler(tmp_path)
    handler.process_batch([{"sequence_num": 11, "event_type": "query_response", "payload": {}}])
    assert handler.last_processed_sequence() == 11
