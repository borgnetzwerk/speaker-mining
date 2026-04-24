from __future__ import annotations

# pyright: reportMissingImports=false

import pandas as pd
import pytest

from process.entity_deduplication.person_deduplication import build_person_clusters
from process.entity_deduplication.contracts import (
    CONFIDENCE_AUTHORITATIVE,
    CONFIDENCE_HIGH,
    CONFIDENCE_LOW,
    STRATEGY_MANUAL_RECONCILIATION,
    STRATEGY_SINGLETON,
    STRATEGY_WIKIDATA_QID,
)


def _aligned(rows: list[dict]) -> pd.DataFrame:
    defaults = {
        "alignment_unit_id": "",
        "canonical_label": "",
        "wikidata_id": "",
        "match_tier": "unresolved",
        "entity_class": "person",
        "mention_id": "",
        "open_refine_name": "",
    }
    return pd.DataFrame([{**defaults, **r} for r in rows])


def _recon(rows: list[dict]) -> pd.DataFrame:
    defaults = {
        "alignment_unit_id": "",
        "wikibase_id": "",
        "wikidata_id": "",
        "fernsehserien_de_id": "",
        "mention_id": "",
        "canonical_label": "",
    }
    return pd.DataFrame([{**defaults, **r} for r in rows])


class TestManualReconciliationAbsent:
    def test_no_recon_df_falls_through_to_automated(self) -> None:
        aligned = _aligned([
            {"alignment_unit_id": "au_1", "canonical_label": "Karl Müller", "wikidata_id": "Q123"},
            {"alignment_unit_id": "au_2", "canonical_label": "Karl Müller", "wikidata_id": "Q123"},
        ])
        persons, members = build_person_clusters(aligned, reconciliation_df=None)
        assert len(persons) == 1
        assert persons.iloc[0]["cluster_strategy"] == STRATEGY_WIKIDATA_QID
        assert persons.iloc[0]["cluster_confidence"] == CONFIDENCE_HIGH


class TestManualReconciliationTierA:
    def test_wikidata_id_groups_into_authoritative_cluster(self) -> None:
        aligned = _aligned([
            {"alignment_unit_id": "au_1", "canonical_label": "Anna Schmidt"},
            {"alignment_unit_id": "au_2", "canonical_label": "Anna Schmidt"},
        ])
        recon = _recon([
            {"alignment_unit_id": "au_1", "wikidata_id": "Q999", "canonical_label": "Anna Schmidt"},
            {"alignment_unit_id": "au_2", "wikidata_id": "Q999", "canonical_label": "Anna Schmidt"},
        ])
        persons, members = build_person_clusters(aligned, recon)
        assert len(persons) == 1
        row = persons.iloc[0]
        assert row["cluster_strategy"] == STRATEGY_MANUAL_RECONCILIATION
        assert row["cluster_confidence"] == CONFIDENCE_AUTHORITATIVE
        assert row["wikidata_id"] == "Q999"
        assert int(row["cluster_size"]) == 2
        assert len(members) == 2

    def test_recon_canonical_label_overrides_aligned_label(self) -> None:
        aligned = _aligned([
            {"alignment_unit_id": "au_1", "canonical_label": "wrong label"},
        ])
        recon = _recon([
            {"alignment_unit_id": "au_1", "wikidata_id": "Q1", "canonical_label": "Correct Name"},
        ])
        persons, _ = build_person_clusters(aligned, recon)
        assert persons.iloc[0]["canonical_label"] == "Correct Name"

    def test_two_separate_wikidata_ids_produce_two_clusters(self) -> None:
        aligned = _aligned([
            {"alignment_unit_id": "au_1"},
            {"alignment_unit_id": "au_2"},
        ])
        recon = _recon([
            {"alignment_unit_id": "au_1", "wikidata_id": "Q1"},
            {"alignment_unit_id": "au_2", "wikidata_id": "Q2"},
        ])
        persons, _ = build_person_clusters(aligned, recon)
        assert len(persons) == 2
        assert set(persons["cluster_strategy"]) == {STRATEGY_MANUAL_RECONCILIATION}
        assert set(persons["wikidata_id"]) == {"Q1", "Q2"}


class TestManualReconciliationTierB:
    def test_wikibase_id_groups_without_wikidata_id(self) -> None:
        aligned = _aligned([
            {"alignment_unit_id": "au_1", "canonical_label": "Max Muster"},
            {"alignment_unit_id": "au_2", "canonical_label": "Max Muster"},
        ])
        recon = _recon([
            {"alignment_unit_id": "au_1", "wikibase_id": "WB_42", "canonical_label": "Max Muster"},
            {"alignment_unit_id": "au_2", "wikibase_id": "WB_42", "canonical_label": "Max Muster"},
        ])
        persons, members = build_person_clusters(aligned, recon)
        assert len(persons) == 1
        assert persons.iloc[0]["cluster_strategy"] == STRATEGY_MANUAL_RECONCILIATION
        assert persons.iloc[0]["cluster_confidence"] == CONFIDENCE_AUTHORITATIVE
        assert len(members) == 2


class TestManualReconciliationTierC:
    def test_singleton_without_external_id_is_authoritative(self) -> None:
        aligned = _aligned([{"alignment_unit_id": "au_1", "canonical_label": "Lone Person"}])
        recon = _recon([{"alignment_unit_id": "au_1", "canonical_label": "Lone Person"}])
        persons, _ = build_person_clusters(aligned, recon)
        assert len(persons) == 1
        assert persons.iloc[0]["cluster_strategy"] == STRATEGY_MANUAL_RECONCILIATION
        assert persons.iloc[0]["cluster_confidence"] == CONFIDENCE_AUTHORITATIVE


class TestManualReconciliationSupersedes:
    def test_recon_row_not_reprocessed_by_automated_strategies(self) -> None:
        # au_1 is in recon → manual_reconciliation. au_2 is not → automated.
        aligned = _aligned([
            {"alignment_unit_id": "au_1", "canonical_label": "Same Name", "wikidata_id": "Q5"},
            {"alignment_unit_id": "au_2", "canonical_label": "Same Name", "wikidata_id": "Q5"},
        ])
        # Only au_1 is in the reconciliation CSV (with a different QID override)
        recon = _recon([
            {"alignment_unit_id": "au_1", "wikidata_id": "Q999", "canonical_label": "Same Name"},
        ])
        persons, members = build_person_clusters(aligned, recon)
        strategies = set(persons["cluster_strategy"])
        # au_1 → manual_reconciliation (Q999), au_2 → wikidata_qid_match (Q5) as singleton or cluster
        assert STRATEGY_MANUAL_RECONCILIATION in strategies
        # au_1 should NOT appear in the automated wikidata_qid_match cluster
        manual_members = members[members["canonical_entity_id"].isin(
            persons[persons["cluster_strategy"] == STRATEGY_MANUAL_RECONCILIATION]["canonical_entity_id"]
        )]
        assert set(manual_members["alignment_unit_id"]) == {"au_1"}

    def test_recon_row_with_alignment_unit_not_in_aligned_is_skipped(self) -> None:
        aligned = _aligned([{"alignment_unit_id": "au_real"}])
        recon = _recon([
            {"alignment_unit_id": "au_ghost", "wikidata_id": "Q1"},
            {"alignment_unit_id": "au_real", "wikidata_id": "Q2"},
        ])
        persons, _ = build_person_clusters(aligned, recon)
        # Only au_real should produce a cluster
        assert len(persons) == 1
        assert persons.iloc[0]["cluster_strategy"] == STRATEGY_MANUAL_RECONCILIATION

    def test_duplicate_alignment_unit_in_recon_is_deduplicated(self) -> None:
        aligned = _aligned([{"alignment_unit_id": "au_1", "canonical_label": "Person"}])
        recon = _recon([
            {"alignment_unit_id": "au_1", "wikidata_id": "Q1"},
            {"alignment_unit_id": "au_1", "wikidata_id": "Q1"},  # duplicate
        ])
        persons, _ = build_person_clusters(aligned, recon)
        assert len(persons) == 1
