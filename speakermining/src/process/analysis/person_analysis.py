"""
Person-specific analysis: Top guests, per-show statistics, person profiles.

TASK-B22: Generate person-level insights:
1. REQ-PER01: Top guests stacked bar (segments = broadcasting program)
2. REQ-PER02: Top guests per individual show
3. REQ-PER03: Individuals within category stacked bar (property value subdivisions)
"""

import math

import pandas as pd
from pathlib import Path


def compute_top_guests_by_show(
    guest_df: pd.DataFrame,
    episode_meta_df: pd.DataFrame,
    appearance_df: pd.DataFrame,
    top_n: int = 20
) -> dict:
    """
    Compute per-show top guest rankings.
    
    Returns dict[show_id -> DataFrame(guest_qid, label, appearance_count, rank)]
    """
    if appearance_df.empty or "show_id" not in appearance_df.columns:
        return {}
    
    per_show = {}
    for show_id in appearance_df["show_id"].unique():
        if not show_id or pd.isna(show_id):
            continue
        
        show_guests = (
            appearance_df[appearance_df["show_id"] == show_id]
            .groupby(["canonical_entity_id", "canonical_label", "wikidata_id"])
            .size()
            .reset_index(name="appearance_count")
            .sort_values("appearance_count", ascending=False)
            .head(top_n)
            .reset_index(drop=True)
        )
        show_guests["rank"] = show_guests.index + 1
        show_guests["show_id"] = show_id
        per_show[show_id] = show_guests
    
    return per_show


def compute_guest_specialization(
    appearance_df: pd.DataFrame,
    min_appearances: int = 3
) -> pd.DataFrame:
    """
    Identify guests specialized to specific shows (high concentration on one program).
    
    Returns DataFrame with columns: guest_qid, label, primary_show, specialization_pct, total_appearances
    """
    if appearance_df.empty or "show_id" not in appearance_df.columns:
        return pd.DataFrame()
    
    # Per-guest, per-show appearance count
    guest_show_counts = (
        appearance_df
        .groupby(["canonical_entity_id", "canonical_label", "wikidata_id", "show_id"])
        .size()
        .reset_index(name="show_appearances")
    )
    
    # Total appearances per guest
    guest_totals = guest_show_counts.groupby(["canonical_entity_id", "canonical_label", "wikidata_id"])["show_appearances"].sum().reset_index()
    guest_totals.columns = ["canonical_entity_id", "canonical_label", "wikidata_id", "total_appearances"]
    
    # Filter by minimum appearances
    guest_totals = guest_totals[guest_totals["total_appearances"] >= min_appearances]
    
    # Join back and find dominant show
    guest_show_counts = guest_show_counts.merge(guest_totals, on=["canonical_entity_id", "canonical_label", "wikidata_id"])
    guest_show_counts["show_pct"] = (guest_show_counts["show_appearances"] / guest_show_counts["total_appearances"] * 100).round(1)
    
    # Primary show (highest appearance count)
    primary = (
        guest_show_counts
        .sort_values("show_appearances", ascending=False)
        .groupby(["canonical_entity_id", "canonical_label", "wikidata_id"])
        .first()
        .reset_index()
    )
    primary.columns = ["canonical_entity_id", "canonical_label", "wikidata_id", "primary_show", "primary_show_appearances", "total_appearances", "specialization_pct"]
    
    return primary.sort_values("specialization_pct", ascending=False).reset_index(drop=True)


def compute_person_relevance(
    guest_catalogue: pd.DataFrame,
    episode_appearances: pd.DataFrame,
    core_persons: dict | None = None,
    total_shows: int | None = None,
) -> pd.DataFrame:
    """Compute per-guest claim count, show diversity, and relevance score.

    Relevance score formula (documented in analysis config):
        relevance_score = appearance_count × log(1 + claim_count) × show_diversity

    where:
        claim_count    = number of Wikidata property claims (0 for non-Wikidata persons)
        show_diversity = unique shows guest appeared in / total configured shows

    Args:
        guest_catalogue: Person catalogue filtered to role == "guest".
            Required columns: canonical_entity_id, wikidata_id, canonical_label,
            appearance_count.
        episode_appearances: Episode-level appearances frame.
            Required columns: canonical_entity_id, show_id, role.
        core_persons: Wikidata entity cache {qid: entity_doc}. Used for claim_count.
            Pass None to skip claim counting (claim_count will be 0).
        total_shows: Denominator for show_diversity. If None, derived from
            episode_appearances show_id cardinality.

    Returns:
        DataFrame with columns: canonical_entity_id, canonical_label, wikidata_id,
        appearance_count, claim_count, show_diversity, relevance_score.
        Sorted descending by relevance_score.
    """
    if guest_catalogue is None or guest_catalogue.empty:
        return pd.DataFrame()

    df = guest_catalogue.copy()
    df["wikidata_id"] = df["wikidata_id"].fillna("").astype(str).str.strip()
    df["appearance_count"] = pd.to_numeric(df.get("appearance_count", 0), errors="coerce").fillna(0).astype(int)

    # Claim count from Wikidata entity docs
    if core_persons:
        def _claim_count(qid: str) -> int:
            doc = core_persons.get(qid)
            if not doc:
                return 0
            return len(doc.get("claims", {}))
        df["claim_count"] = df["wikidata_id"].map(_claim_count)
    else:
        df["claim_count"] = 0

    # Show diversity: unique shows / total shows
    if episode_appearances is not None and not episode_appearances.empty and "show_id" in episode_appearances.columns:
        guest_ep = episode_appearances[episode_appearances.get("role", pd.Series(dtype=str)) == "guest"] if "role" in episode_appearances.columns else episode_appearances
        n_total_shows = total_shows or max(int(guest_ep["show_id"].nunique()), 1)
        show_per_guest = (
            guest_ep.groupby("canonical_entity_id")["show_id"]
            .nunique()
            .reset_index(name="unique_shows")
        )
        df = df.merge(show_per_guest, on="canonical_entity_id", how="left")
        df["unique_shows"] = df["unique_shows"].fillna(1).astype(int)
        df["show_diversity"] = (df["unique_shows"] / n_total_shows).round(4)
    else:
        df["show_diversity"] = 1.0

    df["relevance_score"] = (
        df["appearance_count"]
        * df["claim_count"].apply(lambda c: math.log1p(c))
        * df["show_diversity"]
    ).round(4)

    keep_cols = [
        "canonical_entity_id", "canonical_label", "wikidata_id",
        "appearance_count", "claim_count", "show_diversity", "relevance_score",
    ]
    keep_cols = [c for c in keep_cols if c in df.columns]
    return (
        df[keep_cols]
        .sort_values("relevance_score", ascending=False)
        .reset_index(drop=True)
    )


def compute_guest_property_profile(
    guest_qid: str,
    property_values_dict: dict,
    catalogue_df: pd.DataFrame
) -> pd.DataFrame:
    """
    For a single guest, extract their property profile across all configured properties.
    
    Args:
        guest_qid: Wikidata QID of guest
        property_values_dict: Dict[property_pid -> DataFrame with value_label, appearance_count]
        catalogue_df: Guest metadata
    
    Returns DataFrame with columns: property_label, value_label, appearance_count
    """
    profile_rows = []
    
    for prop_pid, df in property_values_dict.items():
        if df.empty or "guest_qid" not in df.columns:
            continue
        
        guest_rows = df[df["guest_qid"] == guest_qid]
        if guest_rows.empty:
            continue
        
        for _, row in guest_rows.iterrows():
            profile_rows.append({
                "property_id": prop_pid,
                "value": row.get("value", row.get("value_label", row.get("value_qid", ""))),
                "appearance_count": row.get("appearance_count", 1),
            })
    
    if not profile_rows:
        return pd.DataFrame()
    
    return pd.DataFrame(profile_rows).sort_values("appearance_count", ascending=False).reset_index(drop=True)
