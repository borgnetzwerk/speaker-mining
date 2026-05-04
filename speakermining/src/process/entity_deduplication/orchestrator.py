from __future__ import annotations

import json
from datetime import datetime, timezone

import pandas as pd

from process.io_guardrails import atomic_write_csv, atomic_write_text

from .contracts import INPUT_FILES, OUTPUT_DIR, OUTPUT_FILES
from .person_deduplication import build_person_clusters


def run_phase32() -> dict:
    """Run Phase 32 entity deduplication for persons.

    Reads aligned_persons.csv from Phase 31 and clusters rows into canonical
    entities. The authoritative reconciliation summary at
    data/31_entity_disambiguation/manual/reconciled_data_summary.csv is applied
    as the highest-confidence tier before any automated strategy runs.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    aligned_persons = pd.read_csv(INPUT_FILES["aligned_persons"], dtype=str).fillna("")

    reconciliation_path = INPUT_FILES["reconciliation_csv"]
    reconciliation_df = None
    if reconciliation_path.exists():
        reconciliation_df = pd.read_csv(reconciliation_path, dtype=str).fillna("")

    dedup_persons, dedup_members = build_person_clusters(aligned_persons, reconciliation_df)
    unresolved_persons = dedup_persons[dedup_persons["wikidata_id"].astype(str).str.strip() == ""].copy()

    atomic_write_csv(OUTPUT_FILES["dedup_persons"], dedup_persons)
    atomic_write_csv(OUTPUT_FILES["dedup_persons_unresolved"], unresolved_persons)
    atomic_write_csv(OUTPUT_FILES["dedup_cluster_members"], dedup_members)

    strategy_counts = dedup_persons["cluster_strategy"].value_counts().to_dict()
    confidence_counts = dedup_persons["cluster_confidence"].value_counts().to_dict()
    n_input = len(aligned_persons)
    n_entities = len(dedup_persons)
    n_unresolved = len(unresolved_persons)

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "phase": "32_entity_deduplication",
        "input_alignment_units": n_input,
        "canonical_entities": n_entities,
        "unresolved_entities": n_unresolved,
        "reduction_ratio": round(1 - n_entities / max(n_input, 1), 4),
        "strategy_counts": strategy_counts,
        "confidence_counts": confidence_counts,
        "manual_reconciliation_used": reconciliation_df is not None,
        "manual_reconciliation_path": str(reconciliation_path),
    }

    atomic_write_text(OUTPUT_FILES["dedup_summary"], json.dumps(summary, indent=2, ensure_ascii=False))

    return summary
