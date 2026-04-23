from __future__ import annotations

import hashlib

import pandas as pd

from process.candidate_generation.person import normalize_name_for_matching

from .contracts import (
    CONFIDENCE_HIGH,
    CONFIDENCE_LOW,
    CONFIDENCE_MEDIUM,
    DEDUP_CLUSTER_MEMBERS_COLUMNS,
    DEDUP_PERSONS_COLUMNS,
    STRATEGY_NORMALIZED_NAME,
    STRATEGY_SINGLETON,
    STRATEGY_WIKIDATA_QID,
)

_MATCH_TIER_RANK = {"exact": 0, "high": 1, "medium": 2, "unresolved": 3}


def _make_canonical_entity_id(representative_alignment_unit_id: str) -> str:
    digest = hashlib.sha1(representative_alignment_unit_id.encode()).hexdigest()[:12]
    return f"ce_{digest}"


def _best_representative_idx(group: pd.DataFrame) -> object:
    has_wikidata = group["wikidata_id"].str.strip() != ""
    candidates = group[has_wikidata] if has_wikidata.any() else group
    tier_rank = candidates["match_tier"].map(lambda t: _MATCH_TIER_RANK.get(t, 99))
    return tier_rank.idxmin()


def _build_member_rows(group: pd.DataFrame, canonical_entity_id: str, cluster_key: str, rep_idx: object) -> list[dict]:
    rows = []
    for idx, row in group.iterrows():
        rows.append({
            "canonical_entity_id": canonical_entity_id,
            "alignment_unit_id": row["alignment_unit_id"],
            "mention_id": row.get("mention_id", ""),
            "canonical_label": row["canonical_label"],
            "wikidata_id": row["wikidata_id"],
            "match_tier": row["match_tier"],
            "cluster_key": cluster_key,
            "is_representative": "true" if idx == rep_idx else "false",
        })
    return rows


def build_person_clusters(aligned_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Cluster aligned person rows into canonical entities.

    Strategy 1 (high confidence): rows sharing a non-empty wikidata_id are the same entity.
    Strategy 2 (medium confidence): remaining rows sharing the same normalize_name_for_matching
    key are likely the same entity.
    Strategy 3 (singleton): rows that match no other row.

    Returns (dedup_persons_df, dedup_cluster_members_df).
    Normalization is applied symmetrically to all canonical_labels being compared (TODO-016).
    """
    clustered_ids: set[str] = set()
    cluster_rows: list[dict] = []
    member_rows: list[dict] = []

    # Strategy 1: group by wikidata_id
    wd_mask = aligned_df["wikidata_id"].str.strip() != ""
    for wikidata_id, group in aligned_df[wd_mask].groupby("wikidata_id", sort=False):
        rep_idx = _best_representative_idx(group)
        rep_row = group.loc[rep_idx]
        cluster_key = normalize_name_for_matching(rep_row["canonical_label"])
        canonical_entity_id = _make_canonical_entity_id(rep_row["alignment_unit_id"])

        cluster_rows.append({
            "canonical_entity_id": canonical_entity_id,
            "entity_class": rep_row.get("entity_class", "person"),
            "cluster_size": len(group),
            "cluster_strategy": STRATEGY_WIKIDATA_QID,
            "cluster_confidence": CONFIDENCE_HIGH,
            "wikidata_id": wikidata_id,
            "canonical_label": rep_row["canonical_label"],
            "open_refine_name": rep_row.get("open_refine_name", ""),
            "cluster_key": cluster_key,
            "evidence_summary": f"Shared Wikidata QID {wikidata_id} across {len(group)} alignment units",
            "representative_alignment_unit_id": rep_row["alignment_unit_id"],
        })
        member_rows.extend(_build_member_rows(group, canonical_entity_id, cluster_key, rep_idx))
        clustered_ids.update(group["alignment_unit_id"].tolist())

    # Strategy 2 + 3: normalize remaining rows and group by key
    remaining = aligned_df[~aligned_df["alignment_unit_id"].isin(clustered_ids)].copy()
    remaining["_cluster_key"] = remaining["canonical_label"].apply(normalize_name_for_matching)

    # Rows with empty cluster key are not comparable — treat as singletons with unique key
    empty_key_mask = remaining["_cluster_key"].str.strip() == ""
    for _, row in remaining[empty_key_mask].iterrows():
        unique_key = f"_unlabeled_{row['alignment_unit_id']}"
        remaining.loc[row.name, "_cluster_key"] = unique_key

    for cluster_key, group in remaining.groupby("_cluster_key", sort=False):
        rep_idx = _best_representative_idx(group)
        rep_row = group.loc[rep_idx]
        canonical_entity_id = _make_canonical_entity_id(rep_row["alignment_unit_id"])
        is_singleton = len(group) == 1

        strategy = STRATEGY_SINGLETON if is_singleton else STRATEGY_NORMALIZED_NAME
        confidence = CONFIDENCE_LOW if is_singleton else CONFIDENCE_MEDIUM
        evidence = (
            "Single alignment unit — no cluster partner found"
            if is_singleton
            else f"Normalized name key '{cluster_key}' matches {len(group)} alignment units"
        )

        cluster_rows.append({
            "canonical_entity_id": canonical_entity_id,
            "entity_class": rep_row.get("entity_class", "person"),
            "cluster_size": len(group),
            "cluster_strategy": strategy,
            "cluster_confidence": confidence,
            "wikidata_id": rep_row["wikidata_id"],
            "canonical_label": rep_row["canonical_label"],
            "open_refine_name": rep_row.get("open_refine_name", ""),
            "cluster_key": cluster_key,
            "evidence_summary": evidence,
            "representative_alignment_unit_id": rep_row["alignment_unit_id"],
        })
        member_rows.extend(_build_member_rows(group, canonical_entity_id, cluster_key, rep_idx))

    dedup_persons = pd.DataFrame(cluster_rows, columns=DEDUP_PERSONS_COLUMNS)
    dedup_members = pd.DataFrame(member_rows, columns=DEDUP_CLUSTER_MEMBERS_COLUMNS)
    return dedup_persons, dedup_members
