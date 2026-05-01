"""
Meta-analysis: Data completeness and Wikidata reconciliation coverage.

TASK-B24 (simplified): For each scope (per show + combined), track:
1. Per-episode Wikidata reconciliation: which episodes have matched Wikidata entities
2. Completeness: episodes with full vs partial reconciliation
3. Coverage statistics: reconciliation rates and trends
"""

import pandas as pd
from pathlib import Path


def compute_wikidata_coverage(reconciled_df: pd.DataFrame, episode_meta_df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute per-episode Wikidata reconciliation coverage.
    
    Returns DataFrame with columns: episode_url, matched_persons, matched_persons_pct, show_id
    """
    if reconciled_df.empty:
        return pd.DataFrame()
    
    # Per-episode: count matched vs total mentions
    df = reconciled_df.copy()
    df["entity_class"] = df.get("entity_class", "unknown")
    df["has_wikidata"] = (df.get("wikidata_id", "") != "") & (df["wikidata_id"].notna())
    
    episode_stats = (
        df.groupby("fernsehserien_de_id")
        .agg({
            "alignment_unit_id": "count",  # total mentions
            "has_wikidata": "sum"  # matched mentions
        })
        .reset_index()
    )
    episode_stats.columns = ["episode_url", "total_mentions", "matched_persons"]
    episode_stats["coverage_pct"] = (
        episode_stats["matched_persons"] / episode_stats["total_mentions"] * 100
    ).round(1)
    
    # Join episode metadata for show info
    if "fernsehserien_de_id" in episode_meta_df.columns and "episode_url" in episode_meta_df.columns:
        episode_stats = episode_stats.merge(
            episode_meta_df[["episode_url", "fernsehserien_de_id", "premiere_date"]],
            left_on="episode_url",
            right_on="episode_url",
            how="left"
        )
        episode_stats.rename(columns={"fernsehserien_de_id": "show_id"}, inplace=True)
    
    return episode_stats.sort_values("episode_url").reset_index(drop=True)


def compute_coverage_statistics(reconciled_df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate Wikidata coverage statistics.
    Returns summary: total mentions, matched, coverage rate.
    """
    if reconciled_df.empty:
        return pd.DataFrame()
    
    df = reconciled_df.copy()
    df["has_wikidata"] = (df.get("wikidata_id", "") != "") & (df["wikidata_id"].notna())
    
    total_mentions = len(df)
    matched_count = df["has_wikidata"].sum()
    coverage_pct = (matched_count / max(total_mentions, 1) * 100)
    
    stats_rows = [
        {"metric": "Total Mentions Processed", "count": total_mentions, "pct": 100.0},
        {"metric": "Matched to Wikidata", "count": int(matched_count), "pct": coverage_pct},
        {"metric": "Unmatched", "count": int(total_mentions - matched_count), "pct": 100 - coverage_pct},
    ]
    
    return pd.DataFrame(stats_rows)


def compute_per_show_coverage(reconciled_df: pd.DataFrame, episode_meta_df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute Wikidata coverage per broadcasting program.
    
    Returns DataFrame: show_id, total_episodes, episodes_with_coverage, avg_coverage_pct
    """
    if reconciled_df.empty or "fernsehserien_de_id" not in reconciled_df.columns:
        return pd.DataFrame()
    
    df = reconciled_df.copy()
    df["has_wikidata"] = (df.get("wikidata_id", "") != "") & (df["wikidata_id"].notna())
    
    # Per-show statistics
    show_stats = (
        df.groupby("fernsehserien_de_id")
        .agg({
            "alignment_unit_id": "count",
            "has_wikidata": "sum"
        })
        .reset_index()
    )
    show_stats.columns = ["show_id", "total_mentions", "matched_mentions"]
    show_stats["coverage_pct"] = (
        show_stats["matched_mentions"] / show_stats["total_mentions"] * 100
    ).round(1)
    
    # Count episodes per show
    episodes_per_show = episode_meta_df.groupby("fernsehserien_de_id").size().reset_index(name="total_episodes")
    show_stats = show_stats.merge(episodes_per_show, left_on="show_id", right_on="fernsehserien_de_id", how="left")
    show_stats.drop(columns=["fernsehserien_de_id"], inplace=True, errors="ignore")
    
    return show_stats.sort_values("coverage_pct", ascending=False).reset_index(drop=True)
