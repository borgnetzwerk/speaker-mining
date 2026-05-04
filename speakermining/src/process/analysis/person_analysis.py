"""
Person-specific analysis: Top guests, per-show statistics, person profiles.

TASK-B22: Generate person-level insights:
1. REQ-PER01: Top guests stacked bar (segments = broadcasting program)
2. REQ-PER02: Top guests per individual show
3. REQ-PER03: Individuals within category stacked bar (property value subdivisions)
"""

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
