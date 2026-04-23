from __future__ import annotations

import json
from datetime import datetime, timezone

import pandas as pd

from process.io_guardrails import atomic_write_csv, atomic_write_text

from .contracts import INPUT_FILES, OUTPUT_DIR, OUTPUT_FILES
from .person_deduplication import build_person_clusters


def run_phase32() -> dict:
    """Run Phase 32 entity deduplication for persons.

    Reads aligned_persons.csv from Phase 31, clusters rows into canonical
    entities using wikidata_id (high confidence) and normalized name key
    (medium confidence), and writes dedup_persons.csv + dedup_cluster_members.csv.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    aligned_persons = pd.read_csv(INPUT_FILES["aligned_persons"], dtype=str).fillna("")

    dedup_persons, dedup_members = build_person_clusters(aligned_persons)

    atomic_write_csv(OUTPUT_FILES["dedup_persons"], dedup_persons)
    atomic_write_csv(OUTPUT_FILES["dedup_cluster_members"], dedup_members)

    strategy_counts = dedup_persons["cluster_strategy"].value_counts().to_dict()
    confidence_counts = dedup_persons["cluster_confidence"].value_counts().to_dict()
    n_input = len(aligned_persons)
    n_entities = len(dedup_persons)

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "phase": "32_entity_deduplication",
        "input_alignment_units": n_input,
        "canonical_entities": n_entities,
        "reduction_ratio": round(1 - n_entities / max(n_input, 1), 4),
        "strategy_counts": strategy_counts,
        "confidence_counts": confidence_counts,
    }

    atomic_write_text(OUTPUT_FILES["dedup_summary"], json.dumps(summary, indent=2, ensure_ascii=False))

    return summary
