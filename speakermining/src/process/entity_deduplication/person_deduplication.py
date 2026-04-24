from __future__ import annotations

import hashlib

import pandas as pd

from process.candidate_generation.person import normalize_name_for_matching

from .contracts import (
    CONFIDENCE_AUTHORITATIVE,
    CONFIDENCE_HIGH,
    CONFIDENCE_LOW,
    CONFIDENCE_MEDIUM,
    DEDUP_CLUSTER_MEMBERS_COLUMNS,
    DEDUP_PERSONS_COLUMNS,
    STRATEGY_MANUAL_RECONCILIATION,
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


def _apply_manual_reconciliation_tier(
    aligned_df: pd.DataFrame,
    reconciliation_df: pd.DataFrame,
) -> tuple[list[dict], list[dict], set[str]]:
    """Apply the manual OpenRefine reconciliation CSV as the highest-confidence tier.

    Groups alignment units by shared wikidata_id (tier A), then by shared
    wikibase_id (tier B), then treats remaining reconciled rows as authoritative
    singletons (tier C). Alignment unit IDs not present in reconciliation_df
    are left for automated strategies.

    Returns (cluster_rows, member_rows, clustered_ids).
    """
    cluster_rows: list[dict] = []
    member_rows: list[dict] = []
    clustered_ids: set[str] = set()

    valid_ids = set(aligned_df["alignment_unit_id"].tolist())
    recon = reconciliation_df[reconciliation_df["alignment_unit_id"].isin(valid_ids)].copy()
    recon = recon.drop_duplicates(subset=["alignment_unit_id"])
    if recon.empty:
        return cluster_rows, member_rows, clustered_ids

    def _emit(auid_list: list[str], wikidata_id: str, wikibase_id: str, label_override: str) -> None:
        group = aligned_df[aligned_df["alignment_unit_id"].isin(auid_list)]
        if group.empty:
            return
        rep_idx = _best_representative_idx(group)
        rep_row = group.loc[rep_idx]
        canonical_label = label_override.strip() if label_override.strip() else rep_row["canonical_label"]
        cluster_key = normalize_name_for_matching(canonical_label)
        canonical_entity_id = _make_canonical_entity_id(rep_row["alignment_unit_id"])
        n = len(group)

        if wikidata_id:
            evidence = f"Manual OpenRefine reconciliation: {n} alignment unit(s) → Wikidata {wikidata_id}"
        elif wikibase_id:
            evidence = f"Manual OpenRefine reconciliation: {n} alignment unit(s) → Wikibase {wikibase_id}"
        else:
            evidence = "Manual OpenRefine reconciliation: authoritative singleton (no external ID match)"

        cluster_rows.append({
            "canonical_entity_id": canonical_entity_id,
            "entity_class": rep_row.get("entity_class", "person"),
            "cluster_size": n,
            "cluster_strategy": STRATEGY_MANUAL_RECONCILIATION,
            "cluster_confidence": CONFIDENCE_AUTHORITATIVE,
            "wikidata_id": wikidata_id,
            "canonical_label": canonical_label,
            "open_refine_name": rep_row.get("open_refine_name", ""),
            "cluster_key": cluster_key,
            "evidence_summary": evidence,
            "representative_alignment_unit_id": rep_row["alignment_unit_id"],
        })
        member_rows.extend(_build_member_rows(group, canonical_entity_id, cluster_key, rep_idx))
        clustered_ids.update(group["alignment_unit_id"].tolist())

    # Tier A: group by wikidata_id
    wd_mask = recon["wikidata_id"].str.strip() != ""
    for wikidata_id, g in recon[wd_mask].groupby("wikidata_id", sort=False):
        label = next((r for r in g["canonical_label"] if r.strip()), "")
        _emit(g["alignment_unit_id"].tolist(), str(wikidata_id), "", label)

    # Tier B: group by wikibase_id (no wikidata_id)
    remaining = recon[~recon["alignment_unit_id"].isin(clustered_ids)]
    wb_mask = remaining["wikibase_id"].str.strip() != ""
    for wikibase_id, g in remaining[wb_mask].groupby("wikibase_id", sort=False):
        label = next((r for r in g["canonical_label"] if r.strip()), "")
        _emit(g["alignment_unit_id"].tolist(), "", str(wikibase_id), label)

    # Tier C: remaining reconciled rows — authoritative singletons
    remaining = recon[~recon["alignment_unit_id"].isin(clustered_ids)]
    for _, r in remaining.iterrows():
        _emit([r["alignment_unit_id"]], "", "", r["canonical_label"])

    return cluster_rows, member_rows, clustered_ids


def build_person_clusters(
    aligned_df: pd.DataFrame,
    reconciliation_df: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Cluster aligned person rows into canonical entities.

    Strategy 0 (authoritative): if reconciliation_df is provided, rows covered by the
    manual OpenRefine reconciliation CSV are processed first and supersede all automated
    strategies. Grouped by wikidata_id, then wikibase_id, then as singletons.
    Strategy 1 (high confidence): remaining rows sharing a non-empty wikidata_id.
    Strategy 2 (medium confidence): remaining rows sharing the same normalize_name_for_matching key.
    Strategy 3 (singleton): rows with no cluster partner.

    Returns (dedup_persons_df, dedup_cluster_members_df).
    Normalization is applied symmetrically to all canonical_labels being compared (TODO-016).
    """
    clustered_ids: set[str] = set()
    cluster_rows: list[dict] = []
    member_rows: list[dict] = []

    # Strategy 0: manual reconciliation (authoritative override)
    if reconciliation_df is not None:
        r_clusters, r_members, r_ids = _apply_manual_reconciliation_tier(aligned_df, reconciliation_df)
        cluster_rows.extend(r_clusters)
        member_rows.extend(r_members)
        clustered_ids.update(r_ids)

    # Strategy 1: group by wikidata_id (exclude rows already claimed by manual reconciliation)
    wd_candidates = aligned_df[~aligned_df["alignment_unit_id"].isin(clustered_ids)]
    wd_mask = wd_candidates["wikidata_id"].str.strip() != ""
    for wikidata_id, group in wd_candidates[wd_mask].groupby("wikidata_id", sort=False):
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
