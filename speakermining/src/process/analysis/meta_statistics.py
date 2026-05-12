"""
Meta-statistics: Compute a single canonical CSV of dataset-level counts.

Run from speakermining/src/:
    cd speakermining/src && python -m process.analysis.meta_statistics

Output: data/50_analysis/all/meta_statistics.csv

Reads only stable raw/phase-output files; does not require the notebook to
have been re-run. The one exception is person_quality_tiers.csv, which is
produced by notebook cell 11b and requires the full Wikidata cache.

Stat groups:
    corpus_zdf          ZDF Archive episode universe
    corpus_fs           Fernsehserien.de episode universe
    shows               In-scope broadcasting programs
    episode_universe    Aligned episode universe (occurrence matrix columns)
    persons_pipeline    Deduplication pipeline person counts
    guest_appearances   Guest-level appearance counts
    roles_excluded      Moderators and staff excluded from guest analysis
    quality_tiers       Per-tier Wikidata reconciliation quality
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _row(group: str, key: str, label: str, value: int | float, notes: str = "") -> dict:
    return {
        "stat_group": group,
        "stat_key": key,
        "stat_label": label,
        "value": value,
        "notes": notes,
    }


def _count_matrix_rows(csv_path: Path) -> int:
    """Count data rows in a wide matrix CSV without loading it fully."""
    with csv_path.open(encoding="utf-8") as fh:
        total = sum(1 for _ in fh)
    return max(0, total - 1)  # subtract header


def _count_occurrence_episodes(csv_path: Path) -> tuple[int, int, int]:
    """
    Return (n_zdf_episodes, n_fs_episodes, n_total_episodes) from occurrence matrix.
    Columns prefixed 'ep_' are ZDF; 'episode_fs_' / 'episode_wd_' are FS/Wikidata.
    """
    header = pd.read_csv(csv_path, nrows=0)
    cols = list(header.columns)
    zdf = sum(1 for c in cols if c.startswith("ep_"))
    fs  = sum(1 for c in cols if c.startswith("episode_fs_") or c.startswith("episode_wd_"))
    return zdf, fs, zdf + fs


def _count_occurrence_appearances(csv_path: Path, episode_cols: list[str]) -> int:
    """Sum all 1s in the episode columns of the occurrence matrix (chunked)."""
    total = 0
    for chunk in pd.read_csv(csv_path, chunksize=300, usecols=episode_cols):
        total += int(chunk.fillna(0).values.sum())
    return total


# ---------------------------------------------------------------------------
# Main computation
# ---------------------------------------------------------------------------

def compute_meta_statistics(repo_root: Path) -> pd.DataFrame:
    """
    Compute all meta-statistics and return as a tidy DataFrame.

    Args:
        repo_root: Absolute path to the repository root (the directory that
                   contains 'data/' and 'speakermining/').
    Returns:
        DataFrame with columns: stat_group, stat_key, stat_label, value, notes.
    """
    rows: list[dict] = []
    R = repo_root  # shorthand

    # ------------------------------------------------------------------
    # 1. ZDF corpus (Phase 1 outputs)
    # ------------------------------------------------------------------
    G = "corpus_zdf"
    zdf_ep = pd.read_csv(R / "data/10_mention_detection/episodes.csv", dtype=str).fillna("")
    zdf_no_mentions = pd.read_csv(
        R / "data/10_mention_detection/episodes_without_person_mentions.csv", dtype=str
    )
    zdf_dates = pd.to_datetime(
        zdf_ep["publikationsdatum"], format="%d.%m.%Y", errors="coerce"
    ).dropna()

    rows.append(_row(G, "zdf_episodes_total",
                     "ZDF episodes (total)",
                     len(zdf_ep),
                     "Source: data/10_mention_detection/episodes.csv"))
    rows.append(_row(G, "zdf_year_min",
                     "ZDF corpus start year",
                     int(zdf_dates.dt.year.min())))
    rows.append(_row(G, "zdf_year_max",
                     "ZDF corpus end year",
                     int(zdf_dates.dt.year.max())))
    rows.append(_row(G, "zdf_episodes_no_person_mentions",
                     "ZDF episodes without person mentions",
                     len(zdf_no_mentions),
                     "Source: episodes_without_person_mentions.csv"))

    # ZDF person mention alignment units (pm_* rows in cluster_members)
    cluster = pd.read_csv(
        R / "data/32_entity_deduplication/dedup_cluster_members.csv", dtype=str
    ).fillna("")
    n_zdf_mentions = int((cluster["alignment_unit_id"].str.startswith("pm_")).sum())
    rows.append(_row(G, "zdf_person_mention_rows",
                     "ZDF person mention rows (alignment units)",
                     n_zdf_mentions,
                     "pm_* rows in dedup_cluster_members.csv"))

    # ------------------------------------------------------------------
    # 2. Fernsehserien.de corpus (Phase 2c outputs)
    # ------------------------------------------------------------------
    G = "corpus_fernsehserien"
    FS_META_PATH = R / "data/20_candidate_generation/fernsehserien_de/projections/episode_metadata_normalized.csv"
    FS_GUEST_PATH = R / "data/20_candidate_generation/fernsehserien_de/projections/episode_guests_normalized.csv"

    fs_meta  = pd.read_csv(FS_META_PATH, dtype=str).fillna("")
    fs_guest = pd.read_csv(FS_GUEST_PATH, dtype=str).fillna("")

    fs_all_ep_urls   = set(fs_meta["episode_url"].unique())
    fs_ep_with_entry = set(fs_guest["episode_url"].unique())
    MODERATOR_ROLES  = {"Moderation", "Moderator"}
    fs_ep_with_mod   = set(
        fs_guest[fs_guest["guest_role"].isin(MODERATOR_ROLES)]["episode_url"].unique()
    )

    rows.append(_row(G, "fs_episodes_total",
                     "Fernsehserien.de episodes (total)",
                     len(fs_all_ep_urls),
                     "Unique episode_url values in episode_metadata_normalized.csv"))
    rows.append(_row(G, "fs_episodes_no_guest_entry",
                     "FS episodes without any guest/crew entry",
                     len(fs_all_ep_urls - fs_ep_with_entry),
                     "Episodes with no row in episode_guests_normalized.csv"))
    rows.append(_row(G, "fs_episodes_no_moderator",
                     "FS episodes without a moderator entry",
                     len(fs_all_ep_urls - fs_ep_with_mod),
                     "Episodes where no guest row has role Moderation/Moderator"))
    rows.append(_row(G, "fs_guest_rows_total",
                     "FS raw guest/crew entry rows (all roles)",
                     len(fs_guest),
                     "Rows in episode_guests_normalized.csv"))
    rows.append(_row(G, "fs_guest_rows_gast",
                     'FS raw "Gast" role rows',
                     int((fs_guest["guest_role"] == "Gast").sum())))
    rows.append(_row(G, "fs_guest_rows_moderation",
                     'FS raw "Moderation" role rows',
                     int(fs_guest["guest_role"].isin(MODERATOR_ROLES).sum())))

    # ------------------------------------------------------------------
    # 3. In-scope shows
    # ------------------------------------------------------------------
    G = "shows"
    bp = pd.read_csv(R / "data/00_setup/broadcasting_programs.csv", dtype=str).fillna("")
    in_scope = bp[
        bp["fernsehserien_de_id"].notna()
        & (bp["fernsehserien_de_id"] != "")
        & (bp["fernsehserien_de_id"] != "NONE")
    ]
    rows.append(_row(G, "shows_in_scope",
                     "In-scope broadcasting programs",
                     len(in_scope),
                     "Shows with a valid fernsehserien_de_id in broadcasting_programs.csv"))

    # ------------------------------------------------------------------
    # 4. Episode universe (occurrence matrix column analysis)
    # ------------------------------------------------------------------
    G = "episode_universe"
    OCC_PATH = R / "data/50_analysis/all/occurrence_matrix.csv"
    n_zdf_ep, n_fs_ep, n_total_ep = _count_occurrence_episodes(OCC_PATH)

    # Wikidata episode breakdown from aligned_episodes (not occurrence matrix)
    AE_PATH = R / "data/31_entity_disambiguation/aligned/aligned_episodes.csv"
    ae = pd.read_csv(AE_PATH, dtype=str).fillna("")
    n_wd_matched_to_fs = int(
        (ae["match_strategy"] == "date_and_series_wikidata").sum()
    )
    n_wd_only = int(ae["alignment_unit_id"].str.startswith("episode_wd_").sum())

    rows.append(_row(G, "episode_universe_total",
                     "Total episodes in analysis universe",
                     n_total_ep,
                     "Occurrence matrix episode columns (ep_* + episode_fs_*)"))
    rows.append(_row(G, "episode_universe_zdf",
                     "ZDF episodes in analysis universe",
                     n_zdf_ep,
                     "ep_* columns in occurrence_matrix.csv"))
    rows.append(_row(G, "episode_universe_fs",
                     "FS/aligned episodes in analysis universe",
                     n_fs_ep,
                     "episode_fs_* columns; includes Wikidata-matched FS episodes"))
    rows.append(_row(G, "episode_universe_wd_merged_into_fs",
                     "Wikidata episodes merged into FS columns",
                     n_wd_matched_to_fs,
                     "aligned via date_and_series_wikidata; stored as episode_fs_* in occurrence matrix"))
    rows.append(_row(G, "episode_universe_wd_only_no_guest_data",
                     "Wikidata-only episodes excluded (no guest data)",
                     n_wd_only,
                     "episode_wd_* in aligned_episodes; no FS/ZDF guest rows exist for them"))

    # ------------------------------------------------------------------
    # 5. Person pipeline (Phase 32 outputs)
    # ------------------------------------------------------------------
    G = "persons_pipeline"
    dedup = pd.read_csv(
        R / "data/32_entity_deduplication/dedup_persons.csv", dtype=str
    ).fillna("")

    n_total_persons  = len(dedup)
    n_with_wikidata  = int((dedup["wikidata_id"] != "").sum())
    n_without_wiki   = n_total_persons - n_with_wikidata
    pct_wikidata     = round(n_with_wikidata / max(n_total_persons, 1) * 100, 1)

    n_cluster_total = len(cluster)
    n_fs_mentions   = int((cluster["alignment_unit_id"].str.startswith("person_fs_")).sum())

    rows.append(_row(G, "alignment_units_total",
                     "Phase 31/32 alignment units (all sources)",
                     n_cluster_total,
                     "Rows in dedup_cluster_members.csv"))
    rows.append(_row(G, "alignment_units_zdf",
                     "Alignment units from ZDF (pm_*)",
                     n_zdf_mentions))
    rows.append(_row(G, "alignment_units_fs",
                     "Alignment units from Fernsehserien.de (person_fs_*)",
                     n_fs_mentions))
    rows.append(_row(G, "canonical_persons_total",
                     "Phase 32 canonical persons (all roles)",
                     n_total_persons,
                     "Rows in dedup_persons.csv"))
    rows.append(_row(G, "canonical_persons_with_wikidata",
                     "Canonical persons with a Wikidata ID",
                     n_with_wikidata))
    rows.append(_row(G, "canonical_persons_without_wikidata",
                     "Canonical persons without a Wikidata ID",
                     n_without_wiki))
    rows.append(_row(G, "canonical_persons_wikidata_pct",
                     "Wikidata reconciliation rate (%)",
                     pct_wikidata))

    # ------------------------------------------------------------------
    # 6. Guest appearances (occurrence matrix)
    # ------------------------------------------------------------------
    G = "guest_appearances"
    occ_header = pd.read_csv(OCC_PATH, nrows=0)
    all_ep_cols = [
        c for c in occ_header.columns
        if c.startswith("ep_") or c.startswith("episode_fs_") or c.startswith("episode_wd_")
    ]
    n_canonical_guests = _count_matrix_rows(OCC_PATH)
    n_guest_ep_pairs   = _count_occurrence_appearances(OCC_PATH, all_ep_cols)

    rows.append(_row(G, "canonical_guests_in_matrix",
                     "Canonical guests in occurrence matrix",
                     n_canonical_guests,
                     "Data rows in occurrence_matrix.csv (guests only)"))
    rows.append(_row(G, "guest_episode_pairs_dedup",
                     "Unique (canonical guest, episode) appearance pairs",
                     n_guest_ep_pairs,
                     "Sum of all 1s in occurrence_matrix.csv"))
    rows.append(_row(G, "fs_raw_guest_appearance_rows",
                     "Raw FS guest appearance rows (Gast role only)",
                     int((fs_guest["guest_role"] == "Gast").sum()),
                     "Pre-deduplication; from episode_guests_normalized.csv"))

    # ------------------------------------------------------------------
    # 7. Excluded roles (moderators and staff)
    # ------------------------------------------------------------------
    G = "roles_excluded"
    MOD_PATH   = R / "data/50_analysis/all/moderator_occurrence_matrix.csv"
    STAFF_PATH = R / "data/50_analysis/all/staff_occurrence_matrix.csv"

    n_moderators = _count_matrix_rows(MOD_PATH) if MOD_PATH.exists() else 0
    n_staff      = _count_matrix_rows(STAFF_PATH) if STAFF_PATH.exists() else 0

    rows.append(_row(G, "moderators_excluded",
                     "Moderators excluded from guest analysis",
                     n_moderators,
                     "Data rows in moderator_occurrence_matrix.csv"))
    rows.append(_row(G, "staff_excluded",
                     "Staff excluded from guest analysis",
                     n_staff,
                     "Data rows in staff_occurrence_matrix.csv"))

    # ------------------------------------------------------------------
    # 8. Person quality tiers (requires notebook cell 11b output)
    # ------------------------------------------------------------------
    G = "quality_tiers"
    TIERS_PATH = R / "data/50_analysis/all/person_quality_tiers.csv"
    TIER_LABELS = {
        1: "Wikidata ID + entity doc in Wikidata cache (full property coverage)",
        2: "Wikidata ID present, no entity doc (Wikidata-mentioned only)",
        3: "No Wikidata ID, cluster_size >= 2 (disambiguated via two non-Wikidata sources)",
        4: "No Wikidata ID, cluster_size == 1 (single non-Wikidata source only)",
    }
    if TIERS_PATH.exists():
        tiers = pd.read_csv(TIERS_PATH, dtype=str).fillna("")
        for _, t_row in tiers.iterrows():
            tier_num = int(t_row["data_quality_tier"])
            count    = int(t_row["person_count"])
            pct      = float(t_row["pct"])
            rows.append(_row(G, f"tier_{tier_num}_count",
                             f"Tier {tier_num} person count",
                             count,
                             TIER_LABELS.get(tier_num, "")))
            rows.append(_row(G, f"tier_{tier_num}_pct",
                             f"Tier {tier_num} percentage",
                             pct))
    else:
        rows.append(_row(G, "quality_tiers_missing",
                         "person_quality_tiers.csv not found",
                         0,
                         "Run notebook cell 11b (TASK-F16) to generate this file"))

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    repo_root = Path(__file__).resolve().parents[4]  # speakermining/src/process/analysis → repo root
    out_path  = repo_root / "data/50_analysis/all/meta_statistics.csv"

    print("Computing meta-statistics …")
    stats = compute_meta_statistics(repo_root)
    stats.to_csv(out_path, index=False)

    # Pretty-print to stdout
    print(f"\nWrote {len(stats)} stats to {out_path.relative_to(repo_root)}\n")
    header = (
        f"{'stat_group':<22}  {'stat_key':<38}  {'stat_label':<46}  {'value':>10}"
    )
    print(header)
    print("-" * len(header))
    for _, row in stats.iterrows():
        print(
            f"{row['stat_group']:<22}  {row['stat_key']:<38}  {row['stat_label']:<46}  {row['value']:>10}"
        )


if __name__ == "__main__":
    main()
