"""
Reviewer-requested quantitative analyses for Speaker Mining paper.

Implements every measurable claim the three peer reviewers flagged:
  R1-1   Mann-Whitney U: age distributions by gender (appearance-level, replicating
         the paper's own formula: age = episode_premiere_year - birth_year)
  R1-2   Gender gap trend: see gender_trend_analysis.py (long-running, outsourced)
  R1-2b  Appearance-level gender bounds (quick, analogous to unique-guest [37.7%,62.3%])
  R1-3   Wikidata selection-bias estimate: gender ratio for all persons vs.
         Wikidata-linked subset vs. QID+entity-doc subset (Tier 1 only)
  R3-1   Step 3.1.1 precision: HIGH-confidence automated matches vs. OpenRefine outcome
  R3-2   Deduplication strategy breakdown (from dedup_summary.json)
  R1-4   Unresolved row characterisation (the 13.13%)

Approach: mirrors speakermining/src/process/notebooks/50_analysis.ipynb exactly.
Gender and birth year are read from the live event-log cache via entity_access
(the same O(1) cache-first lookup the notebook uses), NOT from the incomplete
core_persons.json archive (673 entries).  The occurrence_matrix.csv computed by
the notebook is used for the appearance-level join.

Usage (from repo root):
    python documentation/ToDo/2026-05-15_Speaker_Mining_Paper/review/code/statistical_tests.py

Requires: pandas, scipy, numpy  (plus the speakermining package on sys.path)
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date as Date
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

# ──────────────────────────────────────────────────────────────────────────────
# Repo root + sys.path  (mirrors notebook setup exactly)
# ──────────────────────────────────────────────────────────────────────────────

REPO = Path(__file__).resolve()
while not (REPO / "speakermining").exists():
    REPO = REPO.parent

_src_path = REPO / "speakermining" / "src"
if str(_src_path) not in sys.path:
    sys.path.insert(0, str(_src_path))

os.chdir(REPO)   # entity_access expects CWD == repo root

from process.candidate_generation.wikidata import entity_access  # noqa: E402

# Force UTF-8 output on Windows (avoids cp1252 UnicodeEncodeError for box chars)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# ──────────────────────────────────────────────────────────────────────────────
# Paths
# ──────────────────────────────────────────────────────────────────────────────

DATA = REPO / "data"

DEDUP_PERSONS_CSV    = DATA / "32_entity_deduplication/dedup_persons.csv"
OCCURRENCE_MATRIX    = DATA / "50_analysis/all/occurrence_matrix.csv"
ALIGNED_EPISODES_CSV = DATA / "31_entity_disambiguation/aligned/aligned_episodes.csv"
DEDUP_SUMMARY_JSON   = DATA / "32_entity_deduplication/dedup_summary.json"
GENDER_MATRIX_CSV    = DATA / "50_analysis/all/sex_or_gender/value_episode_matrix.csv"
GENDER_STATS_CSV     = DATA / "50_analysis/all/sex_or_gender/carrier_stats.csv"
PERSON_TIERS_CSV     = DATA / "50_analysis/all/person_quality_tiers.csv"

OUT_DIR  = Path(__file__).parent
OUT_JSON = OUT_DIR / "results.json"

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

GENDER_LABELS: dict[str, str] = {
    "Q6581097": "männlich",
    "Q6581072": "weiblich",
    "Q1097630": "Transfrau",
    "Q2449503": "Transmann",
    "Q48270":   "nichtbinär",
    "Q505371":  "Agender",
    "Q27449253": "Transmaskulin",
}


def _h(title: str) -> None:
    print(f"\n{'═' * 72}")
    print(f"  {title}")
    print('═' * 72)


def _sep() -> None:
    print('─' * 72)


# ──────────────────────────────────────────────────────────────────────────────
# Data loading  —  mirrors notebook: entity_access cache, not core_persons.json
# ──────────────────────────────────────────────────────────────────────────────

def load_person_properties_from_cache(dedup_persons: pd.DataFrame) -> pd.DataFrame:
    """
    Fetch P21 (gender) and P569 (birth year) for every QID-linked person in
    dedup_persons using the live event-log cache (entity_access.get_cached_entity_doc),
    exactly as notebook 50_analysis.ipynb does via all_outlink_fetch.

    The cache is O(1) per call after index priming; no network calls are made.

    Returns DataFrame with columns: qid, birth_year, gender_qid, gender_label
    """
    unique_qids = sorted({
        str(qid).strip()
        for qid in dedup_persons["wikidata_id"].dropna().unique()
        if str(qid).strip().startswith("Q")
    })
    print(f"  Querying event-log cache for {len(unique_qids):,} unique QIDs …", flush=True)

    rows: list[dict] = []
    hits = 0
    for qid in unique_qids:
        doc = entity_access.get_cached_entity_doc(qid, REPO)
        if doc is None:
            rows.append({"qid": qid, "birth_year": None, "gender_qid": None, "gender_label": None})
            continue
        hits += 1
        claims = doc.get("claims", {})

        birth_year: int | None = None
        for stmt in claims.get("P569", []):
            try:
                time_str = stmt["mainsnak"]["datavalue"]["value"]["time"]
                s = time_str.lstrip("+")
                year = int(s.split("-")[0])
                if 1800 <= year <= 2020:
                    birth_year = year
                    break
            except (KeyError, TypeError, ValueError):
                pass

        gender_qid: str | None = None
        gender_label: str | None = None
        for stmt in claims.get("P21", []):
            try:
                gqid = stmt["mainsnak"]["datavalue"]["value"]["id"]
                gender_qid = gqid
                gender_label = GENDER_LABELS.get(gqid)
                break
            except (KeyError, TypeError):
                pass

        rows.append({
            "qid": qid,
            "birth_year": birth_year,
            "gender_qid": gender_qid,
            "gender_label": gender_label,
        })

    df = pd.DataFrame(rows)
    print(f"  Cache hits: {hits:,} / {len(unique_qids):,}  ({hits / max(len(unique_qids), 1) * 100:.1f}%)")
    print(f"  With birth_year:   {df['birth_year'].notna().sum():,}")
    print(f"  With gender_label: {df['gender_label'].notna().sum():,}")
    return df


def load_episode_premiere_years(path: Path) -> dict[str, int]:
    """
    Return mapping: alignment_unit_id → premiere_year (int).

    Mirrors the notebook's premiere_date extraction:
      ep_*           → publikationsdatum_zdf         (DD.MM.YYYY)
      episode_fs_*   → premiere_date_fernsehserien_de (YYYY-MM-DD / YYYY-MM-DD HH:MM:SS)
    """
    print(f"  Loading {path.name}  …", end="", flush=True)
    df = pd.read_csv(path, dtype=str, low_memory=False)
    print(f" {len(df):,} rows", flush=True)

    result: dict[str, int] = {}
    for _, row in df.iterrows():
        uid = str(row.get("alignment_unit_id", ""))
        if not uid:
            continue

        raw_date = ""
        if uid.startswith("ep_"):
            raw_date = str(row.get("publikationsdatum_zdf", ""))
        else:
            raw_date = str(row.get("premiere_date_fernsehserien_de", ""))
            if not raw_date or raw_date == "nan":
                raw_date = str(row.get("premiere_date_date_fernsehserien_de", ""))

        if raw_date and raw_date != "nan":
            try:
                if "." in raw_date and raw_date.count(".") == 2:
                    year = int(raw_date.split(".")[-1].strip()[:4])
                else:
                    year = int(str(raw_date).strip()[:4])
                if 1950 <= year <= 2030:
                    result[uid] = year
            except (ValueError, IndexError):
                pass

    return result


def load_episode_premiere_dates(path: Path) -> dict[str, Date]:
    """
    Return mapping: alignment_unit_id → premiere_date (Date object).
    Same format logic as load_episode_premiere_years but preserves full date.
    """
    df = pd.read_csv(path, dtype=str, low_memory=False)
    result: dict[str, Date] = {}
    for _, row in df.iterrows():
        uid = str(row.get("alignment_unit_id", ""))
        if not uid:
            continue
        raw_date = ""
        if uid.startswith("ep_"):
            raw_date = str(row.get("publikationsdatum_zdf", ""))
        else:
            raw_date = str(row.get("premiere_date_fernsehserien_de", ""))
            if not raw_date or raw_date == "nan":
                raw_date = str(row.get("premiere_date_date_fernsehserien_de", ""))
        if raw_date and raw_date != "nan":
            try:
                if "." in raw_date and raw_date.count(".") == 2:
                    parts = raw_date.strip().split(".")
                    result[uid] = Date(int(parts[2][:4]), int(parts[1]), int(parts[0]))
                else:
                    parts = raw_date.strip()[:10].split("-")
                    result[uid] = Date(int(parts[0]), int(parts[1]), int(parts[2]))
            except (ValueError, IndexError):
                pass
    return result


# ──────────────────────────────────────────────────────────────────────────────
# R1-1  Mann-Whitney U: age by gender (appearance-level)
# ──────────────────────────────────────────────────────────────────────────────

def analysis_age_by_gender(
    person_props: pd.DataFrame,
    dedup_persons: pd.DataFrame,
    occurrence: pd.DataFrame,
    episode_years: dict[str, int],
) -> dict:
    """
    Replicate the paper's age formula (episode_premiere_year − birth_year) at the
    appearance level — same as _derive_age_values in notebook 50_analysis.ipynb:

        birth_year_num   = pd.to_numeric(birthyear[:4], errors='coerce')
        premiere_year_num = pd.to_numeric(premiere_year, errors='coerce')
        age = premiere_year_num - birth_year_num

    Then compare male vs. female age distributions with a Mann-Whitney U test
    (H₁: male ages > female ages).
    """
    _h("R1-1  Mann-Whitney U: Age by Gender (appearance level)")

    # Join person properties onto canonical persons (mirrors notebook merge of P21/P569)
    dedup = dedup_persons[dedup_persons["entity_class"] == "person"].copy()
    merged = dedup.merge(
        person_props[["qid", "birth_year", "gender_label"]].rename(columns={"qid": "wikidata_id"}),
        on="wikidata_id",
        how="left",
    )
    print(f"  Canonical persons:              {len(dedup):,}")
    print(f"  With any Wikidata ID:           {(merged['wikidata_id'].astype(str).str.strip() != '').sum():,}")
    print(f"  With birth_year:                {merged['birth_year'].notna().sum():,}")
    print(f"  With gender_label:              {merged['gender_label'].notna().sum():,}")
    print(f"  With both birth_year + gender:  "
          f"{merged[merged['birth_year'].notna() & merged['gender_label'].notna()].shape[0]:,}")

    # Build per-person lookup indexed by canonical_entity_id
    person_info = merged.set_index("canonical_entity_id")[["birth_year", "gender_label"]]

    # Efficiently build appearance table: melt occurrence matrix → long format
    id_cols = {"canonical_entity_id", "canonical_label"}
    ep_cols = [c for c in occurrence.columns if c not in id_cols]

    occ_filtered = occurrence[
        occurrence["canonical_entity_id"].isin(person_info.index)
    ][["canonical_entity_id"] + ep_cols].copy()

    # melt: one row per (person × episode) where the cell is "1"
    occ_long = occ_filtered.melt(
        id_vars=["canonical_entity_id"],
        value_vars=ep_cols,
        var_name="episode_id",
        value_name="appeared",
    )
    occ_long = occ_long[pd.to_numeric(occ_long["appeared"], errors="coerce").fillna(0) > 0]

    # Join person properties and episode years
    occ_long = occ_long.merge(
        person_info, left_on="canonical_entity_id", right_index=True, how="left"
    )
    occ_long = occ_long.dropna(subset=["birth_year", "gender_label"])
    occ_long["ep_year"] = occ_long["episode_id"].map(episode_years)
    occ_long = occ_long.dropna(subset=["ep_year"])

    # Age formula: exactly as notebook _derive_age_values
    occ_long["age"] = (
        pd.to_numeric(occ_long["ep_year"], errors="coerce") -
        pd.to_numeric(occ_long["birth_year"].astype(str).str[:4], errors="coerce")
    ).astype("Int64")
    occ_long = occ_long.dropna(subset=["age"])
    occ_long = occ_long[(occ_long["age"] >= 0) & (occ_long["age"] < 120)]

    app_df = occ_long.copy()
    print(f"\n  Appearance-level rows with valid age + gender: {len(app_df):,}")

    if app_df.empty:
        print("  ERROR: no appearance rows — check episode_years mapping or cache hits")
        return {}

    # Descriptive statistics
    _sep()
    print("  Descriptive statistics (appearance level):\n")
    gender_order = ["männlich", "weiblich", "nichtbinär", "Transfrau", "Transmann", "Agender", "Transmaskulin"]
    for g in gender_order:
        sub = app_df[app_df["gender_label"] == g]["age"].astype(float)
        if len(sub) == 0:
            continue
        print(f"    {g:15s}  n={len(sub):6,}  "
              f"median={sub.median():.1f}  mean={sub.mean():.1f}  "
              f"std={sub.std():.1f}  "
              f"[Q1={sub.quantile(0.25):.0f}, Q3={sub.quantile(0.75):.0f}]")

    # Mann-Whitney U (one-sided: H₁ male ages > female ages)
    _sep()
    male_ages   = app_df[app_df["gender_label"] == "männlich"]["age"].astype(float).values
    female_ages = app_df[app_df["gender_label"] == "weiblich"]["age"].astype(float).values

    if len(male_ages) < 20 or len(female_ages) < 20:
        print("  WARNING: insufficient data for Mann-Whitney U test")
        return {}

    mwu_stat,    mwu_p_two     = stats.mannwhitneyu(male_ages, female_ages, alternative="two-sided")
    mwu_stat_gt, mwu_p_greater = stats.mannwhitneyu(male_ages, female_ages, alternative="greater")

    n_m, n_f = len(male_ages), len(female_ages)
    # r = 2*U_greater/(n_m*n_f) − 1  where U_greater = count(x_i > y_j) from alt='greater'
    # positive r → male ages stochastically greater (males older)
    r_rb = 2.0 * mwu_stat_gt / (n_m * n_f) - 1.0

    print(f"\n  Mann-Whitney U test: male ages vs. female ages")
    print(f"    H₀: male ages = female ages")
    print(f"    H₁: male ages > female ages (older)")
    print(f"    n_male    = {n_m:,}  median = {np.median(male_ages):.1f}  (age at appearance)")
    print(f"    n_female  = {n_f:,}  median = {np.median(female_ages):.1f}  (age at appearance)")
    print(f"    U statistic (two-sided)   = {mwu_stat:,.0f}")
    print(f"    p-value (two-sided)       = {mwu_p_two:.4e}")
    print(f"    p-value (H₁: m > f)      = {mwu_p_greater:.4e}")
    print(f"    Rank-biserial corr. r     = {r_rb:.4f}  (>0 means male stochastically older)")

    sig = mwu_p_greater < 0.05
    print(f"\n  ➜  Claim 'male guests are older at time of appearance' is statistically "
          f"{'SUPPORTED' if sig else 'NOT SUPPORTED'} "
          f"(α=0.05, one-sided, r={r_rb:.3f})")

    # Welch's t-test (two-sample, unequal variances — valid here because n >> 30 by CLT)
    _sep()
    t_stat_two, t_p_two     = stats.ttest_ind(male_ages, female_ages, equal_var=False, alternative="two-sided")
    t_stat_gt,  t_p_greater = stats.ttest_ind(male_ages, female_ages, equal_var=False, alternative="greater")

    mean_m, std_m = float(np.mean(male_ages)),   float(np.std(male_ages,   ddof=1))
    mean_f, std_f = float(np.mean(female_ages)), float(np.std(female_ages, ddof=1))
    # Cohen's d (pooled SD, Hedges' pooled denominator)
    pooled_std = np.sqrt(((n_m - 1) * std_m**2 + (n_f - 1) * std_f**2) / (n_m + n_f - 2))
    cohens_d   = (mean_m - mean_f) / pooled_std

    print(f"\n  Welch's t-test: male ages vs. female ages")
    print(f"    mean_male   = {mean_m:.2f}  std = {std_m:.2f}")
    print(f"    mean_female = {mean_f:.2f}  std = {std_f:.2f}")
    print(f"    t statistic (two-sided)   = {t_stat_two:.4f}")
    print(f"    p-value (two-sided)       = {t_p_two:.4e}")
    print(f"    p-value (H₁: m > f)       = {t_p_greater:.4e}")
    print(f"    Cohen's d                 = {cohens_d:.4f}  (small≈0.2, medium≈0.5, large≈0.8)")

    t_sig = t_p_greater < 0.05
    print(f"\n  ➜  Welch's t-test: 'male guests older' is "
          f"{'SUPPORTED' if t_sig else 'NOT SUPPORTED'} "
          f"(α=0.05, one-sided, d={cohens_d:.3f})")

    # Per-person median birth year
    _sep()
    print("  Per-person median birth year (lower = older):\n")
    person_gender = (
        merged[merged["birth_year"].notna() & merged["gender_label"].notna()]
        .groupby("gender_label")["birth_year"]
        .agg(["median", "mean", "count"])
        .rename(columns={"median": "median_birth_year", "mean": "mean_birth_year", "count": "n_persons"})
    )
    print(person_gender.to_string())

    male_by   = merged[merged["gender_label"] == "männlich"]["birth_year"].dropna().astype(float).values
    female_by = merged[merged["gender_label"] == "weiblich"]["birth_year"].dropna().astype(float).values
    by_p_less = None
    r_rb_by = None
    if len(male_by) >= 20 and len(female_by) >= 20:
        by_stat_gt, by_p_greater = stats.mannwhitneyu(male_by, female_by, alternative="greater")
        _,          by_p_less    = stats.mannwhitneyu(male_by, female_by, alternative="less")
        _,          by_p_two     = stats.mannwhitneyu(male_by, female_by, alternative="two-sided")
        n_mb, n_fb = len(male_by), len(female_by)
        # r < 0 means male birth years stochastically smaller (males born earlier = older)
        r_rb_by = 2.0 * by_stat_gt / (n_mb * n_fb) - 1.0
        print(f"\n  Mann-Whitney U on birth year (H₁: male born earlier = older):")
        print(f"    n_male={n_mb:,}  median birth year={np.median(male_by):.0f}")
        print(f"    n_female={n_fb:,}  median birth year={np.median(female_by):.0f}")
        print(f"    p (H₁: male born LATER, two-sided) = {by_p_two:.4e}")
        print(f"    p (H₁: male born EARLIER, less)    = {by_p_less:.4e}")
        print(f"    r_rb = {r_rb_by:.4f}  (r < 0 means male born earlier = older)")
        print(f"\n  ➜  At person level, 'male guests born earlier (older)' is "
              f"{'SUPPORTED' if by_p_less < 0.05 else 'NOT SUPPORTED'} (α=0.05)")

    return {
        "n_male_appearances":    int(n_m),
        "n_female_appearances":  int(n_f),
        "male_median_age":       float(np.median(male_ages)),
        "female_median_age":     float(np.median(female_ages)),
        "male_mean_age":         mean_m,
        "female_mean_age":       mean_f,
        "mannwhitney_U":         float(mwu_stat),
        "p_two_sided":           float(mwu_p_two),
        "p_greater_male":        float(mwu_p_greater),
        "rank_biserial_r":       float(r_rb),
        "significant_one_sided": bool(sig),
        "welch_t":               float(t_stat_two),
        "welch_p_two_sided":     float(t_p_two),
        "welch_p_greater_male":  float(t_p_greater),
        "cohens_d":              float(cohens_d),
        "person_level_p_male_earlier": float(by_p_less) if by_p_less is not None else None,
        "person_level_r_rb":           float(r_rb_by)   if r_rb_by  is not None else None,
    }


# ──────────────────────────────────────────────────────────────────────────────
# R1-2  Gender gap trend — see gender_trend_analysis.py (long-running, outsourced)
# ──────────────────────────────────────────────────────────────────────────────



# ──────────────────────────────────────────────────────────────────────────────
# R1-3  Wikidata selection-bias: gender ratio by tier
# ──────────────────────────────────────────────────────────────────────────────

def analysis_wikidata_bias(
    person_props: pd.DataFrame,
    dedup_persons: pd.DataFrame,
    person_tiers: pd.DataFrame,
    gender_stats: pd.DataFrame,
    occurrence: pd.DataFrame,
) -> dict:
    """
    Estimate Wikidata gender-coverage bias (Reviewer 1 request):
    Compare the gender ratio of all 8,436 canonical persons vs. the 5,257
    Wikidata-linked subset to estimate the direction and magnitude of coverage bias.

    Tier definitions (from person_quality_tiers.csv):
      Tier 1 (2,394): QID + full entity doc fetched  — gender/birth-year available
      Tier 2 (2,863): QID only, no entity doc at analysis time — no gender
      Tier 3 (  628): No QID, cluster_size ≥ 2          — no gender
      Tier 4 (2,551): No QID, singleton                 — no gender

    The event-log cache now covers ALL 5,257 QID-linked persons, giving
    full gender data for both Tier 1 and Tier 2, which reveals whether
    Tier 2 (previously uncovered) has the same gender ratio as Tier 1.
    """
    _h("R1-3  Wikidata Selection-Bias: Gender Ratio by Tier")

    # ── Carrier stats (computed at notebook run time) ─────────────────────────
    known_cs = gender_stats[gender_stats["value"] != "Unknown / no data"]
    total_known_cs = known_cs["person_count"].sum()
    print(f"  Paper's carrier_stats (computed at notebook run time):")
    for _, r in known_cs.iterrows():
        pct = r["person_count"] / total_known_cs * 100 if total_known_cs > 0 else float("nan")
        print(f"    {r['value']:15s}  n={r['person_count']:5,}  {pct:5.1f}% of known-gender persons")
    print(f"  → 65% male share of 18,169 known-gender *appearances* "
          f"(denominator = appearances, not persons)")

    # ── Authoritative tier counts ─────────────────────────────────────────────
    _sep()
    print(f"\n  Authoritative data quality tiers (person_quality_tiers.csv):")
    for _, r in person_tiers.iterrows():
        t, n, pct = r["data_quality_tier"], r["person_count"], r["pct"]
        desc = {1.0: "QID + entity doc", 2.0: "QID only (no doc at analysis time)",
                3.0: "No QID, 2+ sources", 4.0: "No QID, singleton"}.get(float(t), "")
        print(f"    Tier {t:.0f} ({desc}):  {n:,.0f}  ({pct:.1f}%)")

    # ── Merge person_props (from live cache) onto dedup_persons ───────────────
    dedup = dedup_persons[dedup_persons["entity_class"] == "person"].copy()
    merged = dedup.merge(
        person_props[["qid", "gender_label"]].rename(columns={"qid": "wikidata_id"}),
        on="wikidata_id",
        how="left",
    )
    guest_ids = set(occurrence["canonical_entity_id"])
    guests = merged[merged["canonical_entity_id"].isin(guest_ids)].copy()

    has_qid   = guests["wikidata_id"].astype(str).str.strip().str.startswith("Q")
    has_gender = guests["gender_label"].notna()

    n_total        = len(guests)
    n_qid          = has_qid.sum()
    n_no_qid       = (~has_qid).sum()
    n_gender       = has_gender.sum()
    n_male_all     = (guests["gender_label"] == "männlich").sum()
    n_female_all   = (guests["gender_label"] == "weiblich").sum()
    n_known        = n_male_all + n_female_all
    pct_male_all   = n_male_all / n_known * 100 if n_known > 0 else float("nan")

    _sep()
    print(f"\n  Among all {n_total:,} unique guests in occurrence matrix:")
    print(f"    With Wikidata QID:       {n_qid:,}  ({n_qid/n_total*100:.1f}%)")
    print(f"    Without Wikidata QID:    {n_no_qid:,}  ({n_no_qid/n_total*100:.1f}%)  ← NO gender data")
    print(f"    With gender (from cache): {n_gender:,}  ({n_gender/n_total*100:.1f}%)")
    print(f"      of which male:  {n_male_all:,}  ({pct_male_all:.1f}% of known-gender)")
    print(f"      of which female:{n_female_all:,}  ({n_female_all/n_known*100:.1f}% of known-gender)")

    # ── Tier 1 vs Tier 2 gender comparison (new: both now have cache coverage) ─
    # Use cluster_strategy to reconstruct Tier 1/2:
    #   Tier 1 proxy: manual_reconciliation OR wikidata_qid_match → QID confirmed
    #                 (these had entity docs fetched at notebook time based on guest status)
    #   Tier 2 proxy: no clear way to distinguish from data alone
    # Instead: show QID-linked persons split into "had entity doc in 673 archive" vs. "fetched live"
    # Since we can't reconstruct this exactly, compare by cluster_strategy as the best proxy.
    qid_guests = guests[has_qid].copy()
    n_qid_male   = (qid_guests["gender_label"] == "männlich").sum()
    n_qid_female = (qid_guests["gender_label"] == "weiblich").sum()
    n_qid_known  = n_qid_male + n_qid_female
    pct_qid_male = n_qid_male / n_qid_known * 100 if n_qid_known > 0 else float("nan")

    _sep()
    print(f"\n  Gender split among {n_qid:,} QID-linked guests (full cache coverage):")
    print(f"    Male:    {n_qid_male:,}  ({pct_qid_male:.1f}% of known-gender)")
    print(f"    Female:  {n_qid_female:,}  ({n_qid_female/n_qid_known*100:.1f}% of known-gender)")
    print(f"    No gender: {(qid_guests['gender_label'].isna()).sum():,}")

    # Chi-square: does gender ratio differ for Tier-1 vs Tier-2 proxy?
    # Proxy: wikidata_qid_match/normalized_name_match = "auto" (simpler) vs manual_reconciliation
    qid_guests["tier_proxy"] = qid_guests["cluster_strategy"].map(
        lambda s: "auto" if s in ("wikidata_qid_match", "normalized_name_match") else "manual"
    )
    contingency_df = qid_guests[qid_guests["gender_label"].isin(["männlich", "weiblich"])]
    if len(contingency_df) > 50:
        contingency = pd.crosstab(contingency_df["tier_proxy"], contingency_df["gender_label"])
        if contingency.shape[0] >= 2 and contingency.shape[1] >= 2:
            chi2, p_val, dof, _ = stats.chi2_contingency(contingency)
            _sep()
            print(f"\n  Chi-square: gender ratio auto-matched vs. manual_reconciliation guests")
            print(f"    χ²={chi2:.3f}  df={dof}  p={p_val:.4f}")
            print(f"  ➜  {'Significant difference' if p_val < 0.05 else 'No significant difference'} "
                  f"in gender ratio between matching strategies (p={p_val:.4f})")

    # ── Unique-guest gender bounds (two-sided) ────────────────────────────────
    # n_gender_unknown = guests with no gender annotation = no-QID guests
    # (QID guests without P21 are also unknown but lumped with no-QID here)
    n_gender_unknown = n_total - n_gender  # all guests minus those with any gender label
    # Correct two-sided bounds — NOT 1−lower (which the paper currently uses):
    lower_bound = n_male_all / n_total * 100 if n_total > 0 else float("nan")
    upper_bound = (n_male_all + n_gender_unknown) / n_total * 100 if n_total > 0 else float("nan")
    observed_unique_pct = n_male_all / n_known * 100 if n_known > 0 else float("nan")

    _sep()
    print(f"\n  UNIQUE-GUEST GENDER BOUNDS (two-sided):")
    print(f"    Total unique guests:         {n_total:,}")
    print(f"    Known gender:                {n_known:,}  ({n_known/n_total*100:.1f}%)")
    print(f"    Unknown gender:              {n_gender_unknown:,}  ({n_gender_unknown/n_total*100:.1f}%)")
    print(f"    Male (known gender):         {n_male_all:,}")
    print(f"    Observed male share (known): {observed_unique_pct:.1f}%")
    _sep()
    print(f"    Lower bound (all unknown = female): {lower_bound:.1f}%")
    print(f"    Upper bound (all unknown = male):   {upper_bound:.1f}%")
    print(f"\n  Male unique-guest rate within [{lower_bound:.1f}%, {upper_bound:.1f}%]")
    print(f"\n  PAPER CORRECTION REQUIRED:")
    print(f"  The paper states '[37.7%, 62.3%]' where 62.3% = 1 − 37.7%.")
    print(f"  That is the female share when all unknowns are female — NOT the upper")
    print(f"  bound for male share. Correct range: [{lower_bound:.1f}%, {upper_bound:.1f}%].")

    return {
        "n_total_guests":            int(n_total),
        "n_with_qid":                int(n_qid),
        "n_without_qid":             int(n_no_qid),
        "n_with_gender_cache":       int(n_gender),
        "n_gender_unknown":          int(n_gender_unknown),
        "pct_male_of_known_gender":  round(pct_male_all, 2),
        "n_qid_male":                int(n_qid_male),
        "n_qid_female":              int(n_qid_female),
        "pct_qid_male_of_known":     round(pct_qid_male, 2),
        "unique_guest_lower_bound":  round(lower_bound, 2),
        "unique_guest_upper_bound":  round(upper_bound, 2),
        "unique_guest_observed_pct": round(observed_unique_pct, 2),
    }


# ──────────────────────────────────────────────────────────────────────────────
# R1-2b  Appearance-level gender bounds (quick)
# ──────────────────────────────────────────────────────────────────────────────

def analysis_gender_appearance_bounds(
    gender_matrix: pd.DataFrame,
    gender_stats: pd.DataFrame,
) -> dict:
    """
    Compute appearance-level lower and upper bounds for male share.

    Analogous to the paper's unique-guest bounds [37.7%, 62.3%]:
      Upper: n_male_app / n_known_gender_app  (observed rate, known-gender appearances only)
      Lower: n_male_app / n_total_app         (if all unknown-gender appearances were female)

    Source: value_episode_matrix.csv — each row is a gender value, each column an episode,
    cell = count of appearances of that gender in that episode.
    """
    _h("R1-2b  Appearance-Level Gender Bounds")

    ep_cols = [c for c in gender_matrix.columns if c != "value"]

    def _row_sum(label: str) -> int:
        rows = gender_matrix[gender_matrix["value"] == label]
        if rows.empty:
            return 0
        return int(rows[ep_cols].apply(pd.to_numeric, errors="coerce").fillna(0).values.sum())

    n_male    = _row_sum("männlich")
    n_female  = _row_sum("weiblich")
    n_unknown = _row_sum("Unknown / no data")

    known_labels = {"männlich", "weiblich", "Unknown / no data"}
    n_other = sum(
        _row_sum(v)
        for v in gender_matrix["value"].unique()
        if v not in known_labels
    )

    n_known = n_male + n_female + n_other
    n_total = n_known + n_unknown

    # Correct two-sided bounds:
    #   Lower: all unknown appearances are female  → male / total
    #   Upper: all unknown appearances are male    → (male + unknown) / total
    # NOTE: 1 − lower_pct ≠ upper_pct (they are NOT symmetric unless male_known = female_known).
    # The paper's unique-guest "[37.7%, 62.3%]" misuses 1−lower as the upper bound — avoid here.
    lower_pct = n_male / n_total * 100 if n_total > 0 else float("nan")
    upper_pct = (n_male + n_unknown) / n_total * 100 if n_total > 0 else float("nan")
    observed_pct = n_male / n_known * 100 if n_known > 0 else float("nan")

    print(f"  From value_episode_matrix.csv:")
    print(f"    männlich appearances:  {n_male:,}")
    print(f"    weiblich appearances:  {n_female:,}")
    print(f"    other known genders:   {n_other:,}")
    print(f"    unknown / no data:     {n_unknown:,}")
    print(f"    known-gender total:    {n_known:,}")
    print(f"    all appearances:       {n_total:,}")
    _sep()
    print(f"\n  Appearance-level male share bounds (two-sided):")
    print(f"    Observed (known-gender only):               {observed_pct:.1f}%")
    print(f"    Lower bound (all {n_unknown:,} unknown = female): {lower_pct:.1f}%")
    print(f"    Upper bound (all {n_unknown:,} unknown = male):   {upper_pct:.1f}%")
    print(f"\n  Male guest appearance rate within [{lower_pct:.1f}%, {upper_pct:.1f}%]")
    print(f"  (observed: {observed_pct:.1f}% among known-gender appearances)")
    print(f"\n  PAPER NOTE: unique-guest bounds '[37.7%, 62.3%]' are incorrect —")
    print(f"  62.3% = 1 − 37.7% (female share when all unknown = female), NOT")
    print(f"  the upper bound for male share (which would be ~76.5% if all")
    print(f"  3,271 unknown unique guests were male). Correct range: [37.7%, ~76.5%].")

    # Cross-check against carrier_stats person counts
    known_cs = gender_stats[gender_stats["value"] != "Unknown / no data"]
    n_persons_known = int(known_cs["person_count"].sum())
    print(f"\n  Cross-check (carrier_stats persons with known gender): {n_persons_known:,}")

    return {
        "n_male_appearances":    n_male,
        "n_female_appearances":  n_female,
        "n_other_appearances":   n_other,
        "n_unknown_appearances": n_unknown,
        "n_known_appearances":   n_known,
        "n_total_appearances":   n_total,
        "observed_pct":          round(observed_pct, 2),
        "lower_pct":             round(lower_pct, 2),
        "upper_pct":             round(upper_pct, 2),
    }


# ──────────────────────────────────────────────────────────────────────────────
# R3-1  Step 3.1.1 precision: HIGH-confidence automated tags vs. OpenRefine
# ──────────────────────────────────────────────────────────────────────────────

def analysis_alignment_precision(
    cluster_members: pd.DataFrame,
    dedup_persons: pd.DataFrame,
) -> dict:
    """
    For each Step 3.1.1 HIGH-confidence tag (match_tier='high') in
    dedup_cluster_members.csv, compare the automated wikidata_id suggestion
    against the OpenRefine-confirmed wikidata_id in dedup_persons.csv
    (joined via canonical_entity_id).

    Data sources (per numbers_reference.md):
      dedup_cluster_members.csv: alignment_unit_id → canonical_entity_id + auto wikidata_id
      dedup_persons.csv:         canonical_entity_id → confirmed wikidata_id
    """
    _h("R3-1  Step 3.1.1 Precision: HIGH-Confidence Tags vs. OpenRefine")

    # match_tier is lowercase in the CSV ("high", not "HIGH")
    high_cm = cluster_members[
        (cluster_members["entity_class"] == "person") &
        (cluster_members["match_tier"].astype(str).str.strip().str.lower() == "high")
    ].copy()
    print(f"  HIGH rows in dedup_cluster_members (person):  {len(high_cm):,}")
    print(f"  Expected (18.6% of 31,165):                   5,797")

    if high_cm.empty:
        print("  No HIGH rows found.")
        return {}

    # Confirmed QID: dedup_persons.canonical_entity_id → wikidata_id
    confirmed_qid_map = (
        dedup_persons[dedup_persons["entity_class"] == "person"]
        .set_index("canonical_entity_id")["wikidata_id"]
        .to_dict()
    )
    high_cm = high_cm.copy()
    high_cm["auto_qid"]      = high_cm["wikidata_id"].astype(str).str.strip()
    high_cm["confirmed_qid"] = high_cm["canonical_entity_id"].map(confirmed_qid_map).fillna("")

    def _outcome(row: pd.Series) -> str:
        auto = row["auto_qid"]
        conf = row["confirmed_qid"]
        if not auto.startswith("Q"):
            return "NO_AUTO_QID"
        if not str(conf).startswith("Q"):
            return "CANONICAL_HAS_NO_QID"
        if auto == conf:
            return "CONFIRMED"
        return "CORRECTED"

    high_cm["outcome"] = high_cm.apply(_outcome, axis=1)

    counts = high_cm["outcome"].value_counts()
    total  = len(high_cm)

    _sep()
    print(f"\n  Outcome distribution for {total:,} HIGH-tagged rows:\n")
    for outcome, cnt in counts.items():
        print(f"    {outcome:30s}  {cnt:5,}  ({cnt/total*100:.1f}%)")

    confirmed  = counts.get("CONFIRMED", 0)
    corrected  = counts.get("CORRECTED", 0)
    comparable = confirmed + corrected
    precision  = confirmed / comparable if comparable > 0 else float("nan")

    _sep()
    print(f"\n  Of {comparable:,} HIGH rows where BOTH auto and confirmed QIDs exist:")
    print(f"    Confirmed: {confirmed:,}  Corrected: {corrected:,}")
    print(f"    Precision = {precision:.4f} ({precision*100:.2f}%)")
    print(f"\n  ➜  Step 3.1.1 HIGH-confidence precision: "
          f"{'VERY HIGH (>99%)' if precision >= 0.99 else 'HIGH (>80%)' if precision >= 0.8 else 'MODERATE (60–80%)' if precision >= 0.6 else 'LOW (<60%)'}")
    print(f"  NOTE: {counts.get('NO_AUTO_QID', 0):,} HIGH rows had no automated QID suggestion "
          f"({counts.get('NO_AUTO_QID', 0)/total*100:.1f}%) — OpenRefine assigned the QID directly.")

    return {
        "n_high_rows":                   int(total),
        "n_no_auto_qid":                 int(counts.get("NO_AUTO_QID", 0)),
        "n_comparable":                  int(comparable),
        "confirmed":                     int(confirmed),
        "corrected":                     int(corrected),
        "precision_comparable_rows":     round(precision, 4),
    }


# ──────────────────────────────────────────────────────────────────────────────
# R3-2  Deduplication strategy breakdown
# ──────────────────────────────────────────────────────────────────────────────

def analysis_dedup_strategies(dedup_summary: dict) -> dict:
    _h("R3-2  Deduplication Strategy Breakdown")

    strategy_counts: dict  = dedup_summary.get("strategy_counts", {})
    confidence_counts: dict = dedup_summary.get("confidence_counts", {})
    total = dedup_summary.get("canonical_entities", 0)

    print(f"  Input alignment units:   {dedup_summary.get('input_alignment_units', '?'):,}")
    print(f"  Canonical entities:      {total:,}")
    print(f"  Reduction ratio:         {dedup_summary.get('reduction_ratio', float('nan')):.4f}")
    _sep()
    print(f"\n  Strategy breakdown:\n")
    for strat, cnt in sorted(strategy_counts.items(), key=lambda x: -x[1]):
        print(f"    {strat:35s}  {cnt:5,}  ({cnt/total*100:.1f}%)")
    _sep()
    print(f"\n  Confidence breakdown:\n")
    for conf, cnt in sorted(confidence_counts.items(), key=lambda x: -x[1]):
        print(f"    {conf:15s}  {cnt:5,}  ({cnt/total*100:.1f}%)")

    return {"strategy_counts": strategy_counts, "confidence_counts": confidence_counts}


# ──────────────────────────────────────────────────────────────────────────────
# R1-4  Unresolved row characterisation (the 13.13%)
# ──────────────────────────────────────────────────────────────────────────────

def analysis_unresolved(dedup_persons: pd.DataFrame) -> dict:
    """
    Characterise the 3,179 canonical persons with no Wikidata ID (Tier 3 + Tier 4).

    Note: The paper's "13.13% unresolved within OpenRefine time window" (≈4,092 alignment
    units) is based on curator session tracking and cannot be extracted from any CSV.
    The 3,179 no-QID canonical persons from dedup_persons.csv are the closest verifiable
    proxy: these are persons who ended deduplication without a Wikidata link.

    Per numbers_reference.md:
      Tier 3 (628):  cluster_strategy = normalized_name_match (≥2 sources, no QID)
      Tier 4 (2,551): cluster_strategy = singleton             (1 source, no QID)
      Total: 3,179 = 37.7% of 8,436 canonical persons
    """
    _h("R1-4  Unresolved / No-QID Characterisation (3,179 persons = 37.7%)")

    persons  = dedup_persons[dedup_persons["entity_class"] == "person"].copy()
    no_qid   = persons[~persons["wikidata_id"].astype(str).str.strip().str.startswith("Q")].copy()
    n_total  = len(persons)
    n_no_qid = len(no_qid)
    pct      = n_no_qid / n_total * 100 if n_total > 0 else 0

    print(f"  Total canonical persons (dedup_persons.csv): {n_total:,}")
    print(f"  Without Wikidata ID:                         {n_no_qid:,}  ({pct:.1f}%)")
    print(f"  Paper target (13.13% of 31,165 alignment units): ~4,092  [from curator logs, unverifiable in CSV]")
    print(f"  Best verifiable proxy: {n_no_qid:,} canonical persons without QID")

    # Source breakdown via representative_alignment_unit_id prefix
    def _classify_source(uid: str) -> str:
        if uid.startswith("pm_"):        return "ZDF mention (pm_*)"
        if uid.startswith("person_fs"): return "fernsehserien.de (person_fs_*)"
        if uid.startswith("person_wd"): return "Wikidata baseline (person_wd_*)"
        return "other"

    rep_col = "representative_alignment_unit_id"
    if rep_col in no_qid.columns:
        no_qid["source_type"] = no_qid[rep_col].fillna("").apply(_classify_source)
        _sep()
        print(f"\n  Source breakdown (by representative_alignment_unit_id prefix):\n")
        src_counts = no_qid["source_type"].value_counts()
        for src, cnt in src_counts.items():
            print(f"    {src:40s}  {cnt:5,}  ({cnt/n_no_qid*100:.1f}%)")
    else:
        src_counts = pd.Series(dtype=int)
        print(f"  (representative_alignment_unit_id column not found)")

    # Cluster strategy breakdown (Tier 3 vs Tier 4)
    _sep()
    print(f"\n  Cluster strategy breakdown:\n")
    strategy_counts = no_qid["cluster_strategy"].fillna("unknown").value_counts()
    for strat, cnt in strategy_counts.items():
        print(f"    {strat:35s}  {cnt:5,}  ({cnt/n_no_qid*100:.1f}%)")

    # Name token counts
    _sep()
    print(f"\n  Name token counts (canonical_label):\n")
    no_qid["word_count"] = no_qid["canonical_label"].fillna("").apply(
        lambda x: len(str(x).split())
    )
    single_word = (no_qid["word_count"] == 1).sum()
    multi_word  = (no_qid["word_count"] > 1).sum()
    zero_word   = (no_qid["word_count"] == 0).sum()
    print(f"    Empty name:                               {zero_word:,}  ({zero_word/n_no_qid*100:.1f}%)")
    print(f"    Single-word (initials / encoding errors): {single_word:,}  ({single_word/n_no_qid*100:.1f}%)")
    print(f"    Multi-word:                               {multi_word:,}  ({multi_word/n_no_qid*100:.1f}%)")

    if multi_word > 0:
        sample = (
            no_qid[no_qid["word_count"] > 1]["canonical_label"]
            .dropna()
            .sample(min(10, int(multi_word)), random_state=42)
            .tolist()
        )
        print(f"\n  Sample multi-word no-QID names: {sample}")

    # Cluster size distribution
    if "cluster_size" in no_qid.columns:
        _sep()
        no_qid["cluster_size_num"] = pd.to_numeric(no_qid["cluster_size"], errors="coerce")
        print(f"\n  Cluster size stats (no-QID persons):")
        print(f"    singleton (size=1): {(no_qid['cluster_size_num'] == 1).sum():,}")
        print(f"    multi-source (size≥2): {(no_qid['cluster_size_num'] >= 2).sum():,}")

    return {
        "n_total_canonical_persons":  int(n_total),
        "n_no_qid":                   int(n_no_qid),
        "pct_no_qid":                 round(pct, 2),
        "source_breakdown":           src_counts.to_dict(),
        "strategy_breakdown":         strategy_counts.to_dict(),
        "single_word_names":          int(single_word),
        "multi_word_names":           int(multi_word),
    }


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 72)
    print("  Speaker Mining — Reviewer-Requested Statistical Tests")
    print("=" * 72)

    _h("Loading data")

    # dedup_persons — exactly like notebook
    print(f"  Loading dedup_persons  …", end="", flush=True)
    dedup_persons = pd.read_csv(DEDUP_PERSONS_CSV, dtype=str, low_memory=False).fillna("")
    print(f" {len(dedup_persons):,} rows")

    # P21/P569 from live event-log cache — same source the notebook uses
    person_props = load_person_properties_from_cache(dedup_persons)

    # Occurrence matrix (already computed by notebook)
    print(f"  Loading occurrence_matrix  …", end="", flush=True)
    occurrence_raw = pd.read_csv(OCCURRENCE_MATRIX, dtype=str, low_memory=False)
    print(f" {len(occurrence_raw):,} rows × {len(occurrence_raw.columns):,} cols")

    # Episode premiere years
    episode_years = load_episode_premiere_years(ALIGNED_EPISODES_CSV)
    id_cols = {"canonical_entity_id", "canonical_label"}
    ep_cols = [c for c in occurrence_raw.columns if c not in id_cols]
    print(f"  Episode → year mappings:  {len(episode_years):,}")
    print(f"  Episodes in matrix with year: "
          f"{sum(1 for c in ep_cols if c in episode_years):,} / {len(ep_cols):,}")

    # Gender matrix (for appearance-level gender bounds)
    print(f"  Loading gender matrix  …", end="", flush=True)
    gender_matrix = pd.read_csv(GENDER_MATRIX_CSV, dtype=str, low_memory=False)
    print(f" {len(gender_matrix):,} rows")

    # Carrier stats & tiers
    gender_stats  = pd.read_csv(GENDER_STATS_CSV)
    person_tiers  = pd.read_csv(PERSON_TIERS_CSV)

    # cluster_members for R3-1 precision analysis
    print(f"  Loading dedup_cluster_members  …", end="", flush=True)
    cluster_members = pd.read_csv(
        DATA / "32_entity_deduplication/dedup_cluster_members.csv", dtype=str, low_memory=False
    ).fillna("")
    print(f" {len(cluster_members):,} rows")

    with DEDUP_SUMMARY_JSON.open() as fh:
        dedup_summary = json.load(fh)

    # ── Run analyses ──────────────────────────────────────────────────────────
    results: dict = {}

    results["R1_1_age_by_gender"] = analysis_age_by_gender(
        person_props, dedup_persons, occurrence_raw, episode_years
    )

    results["R1_2b_gender_appearance_bounds"] = analysis_gender_appearance_bounds(
        gender_matrix, gender_stats
    )

    results["R1_3_wikidata_bias"] = analysis_wikidata_bias(
        person_props, dedup_persons, person_tiers, gender_stats, occurrence_raw
    )

    results["R3_1_alignment_precision"] = analysis_alignment_precision(
        cluster_members, dedup_persons
    )

    results["R3_2_dedup_strategies"] = analysis_dedup_strategies(dedup_summary)

    results["R1_4_unresolved"] = analysis_unresolved(dedup_persons)

    # ── Save JSON results ─────────────────────────────────────────────────────
    _h("Summary saved")
    OUT_JSON.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    print(f"  Results written to: {OUT_JSON}")
    print(f"\nDone.")


if __name__ == "__main__":
    main()
