"""
R1-2  Gender Gap Trend Analysis — long-running component.

Outsourced from statistical_tests.py. The exhaustive monthly split search
can run for several minutes; keeping it separate avoids slowing down the
quick analyses in statistical_tests.py.

Usage (from repo root):
    python documentation/ToDo/2026-05-15_Speaker_Mining_Paper/review/code/gender_trend_analysis.py
"""
from __future__ import annotations

import json
import sys
from datetime import date as Date
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

# ── Import shared infrastructure from statistical_tests (same directory) ──────
_HERE = Path(__file__).parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from statistical_tests import (  # noqa: E402
    REPO, DATA,
    DEDUP_PERSONS_CSV, ALIGNED_EPISODES_CSV, GENDER_MATRIX_CSV,
    load_person_properties_from_cache,
    load_episode_premiere_years,
    load_episode_premiere_dates,
    _h, _sep,
)

OUT_DIR  = _HERE
OUT_JSON = OUT_DIR / "results_gender_trend.json"

# ──────────────────────────────────────────────────────────────────────────────
# Per-show data directories
# ──────────────────────────────────────────────────────────────────────────────

PER_SHOW_DIRS: dict[str, str] = {
    "caren_miosga":                  "Caren Miosga",
    "hart_aber_fair":                "Hart aber fair",
    "internationaler_fruehschoppen": "Int. Frühschoppen",
    "maischberger_ard":              "Maischberger",
    "markus_lanz":                   "Markus Lanz",
    "maybrit_illner":                "Maybrit Illner",
    "precht":                        "Precht",
    "presseclub":                    "Presseclub",
    "scobel":                        "scobel",
    "startalk":                      "StarTalk",
}


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def build_person_gender_map(
    person_props: pd.DataFrame,
    dedup_persons: pd.DataFrame,
) -> pd.Series:
    """Returns Series: canonical_entity_id → gender_label."""
    dedup = dedup_persons[dedup_persons["entity_class"] == "person"].copy()
    merged = dedup.merge(
        person_props[["qid", "gender_label"]].rename(columns={"qid": "wikidata_id"}),
        on="wikidata_id",
        how="left",
    )
    return merged.set_index("canonical_entity_id")["gender_label"]


def detect_tipping_point(
    yr_df: pd.DataFrame,
) -> tuple[int | None, dict, list[dict]]:
    """
    Exhaustive split search over all candidate years.  For each split year Y,
    compare pre-Y and Y+ annual male shares via Mann-Whitney U.  The year that
    yields the most significant separation (lowest p-value) is the tipping point.

    Returns (best_year, best_stats_dict, all_candidate_stats).
    """
    years  = yr_df["year"].values
    y_min, y_max = int(years.min()), int(years.max())

    candidates: list[dict] = []
    for split_year in range(y_min + 3, y_max):
        pre  = yr_df[yr_df["year"] < split_year]["male_share"].values
        post = yr_df[yr_df["year"] >= split_year]["male_share"].values
        if len(pre) < 3 or len(post) < 2:
            continue
        u_stat, p = stats.mannwhitneyu(pre, post, alternative="two-sided")

        sp_post_stat: float | None = None
        post_years = yr_df[yr_df["year"] >= split_year]["year"].values.astype(float)
        if len(post_years) >= 3:
            sp_post_stat = float(stats.spearmanr(post_years, post).statistic)

        candidates.append({
            "split_year":   split_year,
            "n_pre":        len(pre),
            "n_post":       len(post),
            "pre_mean":     float(pre.mean()),
            "post_mean":    float(post.mean()),
            "U":            float(u_stat),
            "p":            float(p),
            "post_spearman": sp_post_stat,
        })

    if not candidates:
        return None, {}, []

    best = min(candidates, key=lambda x: x["p"])
    return best["split_year"], best, candidates


def compute_show_annual_gender(
    occ_path: Path,
    gender_map: pd.Series,
    episode_years: dict[str, int],
) -> pd.DataFrame | None:
    """
    For one show's occurrence matrix, return a DataFrame
    [year, male, female, male_share] aggregated per year.
    """
    if not occ_path.exists():
        return None
    occ = pd.read_csv(occ_path, dtype=str, low_memory=False)
    id_cols  = {"canonical_entity_id", "canonical_label"}
    ep_cols  = [c for c in occ.columns if c not in id_cols]

    occ_f = occ[occ["canonical_entity_id"].isin(gender_map.index)][
        ["canonical_entity_id"] + ep_cols
    ].copy()
    occ_long = occ_f.melt(
        id_vars=["canonical_entity_id"], value_vars=ep_cols,
        var_name="episode_id", value_name="appeared",
    )
    occ_long = occ_long[pd.to_numeric(occ_long["appeared"], errors="coerce").fillna(0) > 0]
    occ_long["gender"] = occ_long["canonical_entity_id"].map(gender_map)
    occ_long = occ_long.dropna(subset=["gender"])
    occ_long["year"] = occ_long["episode_id"].map(episode_years)
    occ_long = occ_long.dropna(subset=["year"])
    occ_long["year"] = occ_long["year"].astype(int)

    rows = []
    for year, grp in occ_long.groupby("year"):
        m = (grp["gender"] == "männlich").sum()
        f = (grp["gender"] == "weiblich").sum()
        if m + f > 0:
            rows.append({"year": year, "male": int(m), "female": int(f),
                         "male_share": m / (m + f) * 100})
    return pd.DataFrame(rows).sort_values("year") if rows else None


def detect_tipping_point_monthly(
    gender_matrix: pd.DataFrame,
    episode_dates: dict[str, Date],
) -> dict:
    """
    Episode-level tipping point detection at monthly granularity.

    1. Build episode-level male/female counts with actual premiere dates.
    2. Aggregate to monthly male share (~200 data points).
    3. Exhaustive Mann-Whitney split search across all month boundaries.
    4. Cross-validate with CUSUM (O(n), visual sanity check).
    """
    ep_cols    = [c for c in gender_matrix.columns if c != "value"]
    male_row   = gender_matrix[gender_matrix["value"] == "männlich"].squeeze()
    female_row = gender_matrix[gender_matrix["value"] == "weiblich"].squeeze()

    rows = []
    for ep_col in ep_cols:
        d = episode_dates.get(ep_col)
        if d is None:
            continue
        m = float(male_row.get(ep_col, 0) or 0)
        f = float(female_row.get(ep_col, 0) or 0)
        if m + f > 0:
            rows.append({"date": d, "ym": (d.year, d.month),
                         "male": int(m), "female": int(f)})

    ep_df = pd.DataFrame(rows)
    print(f"  Episodes with known gender + date: {len(ep_df):,}")

    mo_df = (
        ep_df.groupby("ym")
        .agg(male=("male", "sum"), female=("female", "sum"))
        .reset_index()
        .sort_values("ym")
    )
    mo_df["male_share"] = mo_df["male"] / (mo_df["male"] + mo_df["female"]) * 100
    print(f"  Months with data: {len(mo_df):,}")

    # CUSUM changepoint (O(n)) — marks where cumulative deviation from the mean peaks
    global_mean = mo_df["male_share"].mean()
    mo_df["cusum"] = (mo_df["male_share"] - global_mean).cumsum()
    cusum_idx   = mo_df["cusum"].abs().idxmax()
    cusum_ym    = mo_df.loc[cusum_idx, "ym"]
    cusum_str   = f"{cusum_ym[0]}-{cusum_ym[1]:02d}"
    print(f"  CUSUM changepoint: {cusum_str}")

    # Exhaustive split search — require >=12 months pre, >=24 months post.
    # Criterion for plateau start:
    #   1. Significant level shift:  Mann-Whitney p < 0.05
    #   2. Flat post-period:         post-split Spearman p > 0.10 (trend not significant)
    # Among all splits satisfying both, take the EARLIEST (first month the plateau holds).
    candidates: list[dict] = []
    n = len(mo_df)
    for i in range(12, n - 24):
        pre  = mo_df["male_share"].iloc[:i].values
        post = mo_df["male_share"].iloc[i:].values
        u_stat, mw_p = stats.mannwhitneyu(pre, post, alternative="two-sided")

        post_time             = np.arange(len(post), dtype=float)
        sp_res                = stats.spearmanr(post_time, post)
        sp_post_rho           = float(sp_res.statistic)
        sp_post_p             = float(sp_res.pvalue)

        ym = mo_df["ym"].iloc[i]
        candidates.append({
            "year": ym[0], "month": ym[1],
            "month_str":     f"{ym[0]}-{ym[1]:02d}",
            "n_pre":         len(pre),
            "n_post":        len(post),
            "pre_mean":      float(pre.mean()),
            "post_mean":     float(post.mean()),
            "U":             float(u_stat),
            "mw_p":          float(mw_p),
            "post_spearman": sp_post_rho,
            "post_sp_p":     sp_post_p,
        })

    if not candidates:
        return {}

    _sep()
    print(f"\n  Split search (>=12 pre months, >=24 post months), sorted by date:\n")
    print(f"  {'Month':>9}  {'PreMean':>8}  {'PostMean':>9}  {'MWp':>8}  {'PostRho':>8}  {'PostRhop':>9}")
    _sep()

    plateau_candidates = [
        c for c in candidates if c["mw_p"] < 0.05 and c["post_sp_p"] > 0.10
    ]
    plateau_best = min(plateau_candidates, key=lambda x: (x["year"], x["month"])) \
        if plateau_candidates else min(candidates, key=lambda x: abs(x["post_spearman"]))
    plateau_ids = {c["month_str"] for c in plateau_candidates}

    for c in candidates:
        if c["month_str"] == plateau_best["month_str"]:
            marker = "  < PLATEAU START"
        elif c["month_str"] in plateau_ids:
            marker = "  (plateau)"
        else:
            marker = ""
        print(f"  {c['month_str']:>9}  {c['pre_mean']:>7.1f}%  {c['post_mean']:>8.1f}%  "
              f"{c['mw_p']:>8.4f}  {c['post_spearman']:>+8.3f}  {c['post_sp_p']:>9.4f}{marker}")

    print(f"\n  Plateau start (monthly): {plateau_best['month_str']}"
          f"  (pre: {plateau_best['pre_mean']:.1f}%, post: {plateau_best['post_mean']:.1f}%,"
          f"  post rho={plateau_best['post_spearman']:+.3f} [p={plateau_best['post_sp_p']:.3f}],"
          f"  MW p={plateau_best['mw_p']:.4f})")
    print(f"  CUSUM cross-check:       {cusum_str}")

    return {
        "cusum_month":         cusum_str,
        "plateau_month":       plateau_best["month_str"],
        "plateau_month_year":  plateau_best["year"],
        "plateau_month_num":   plateau_best["month"],
        "pre_mean_pct":        round(plateau_best["pre_mean"],  2),
        "post_mean_pct":       round(plateau_best["post_mean"], 2),
        "mw_p":                plateau_best["mw_p"],
        "post_spearman":       plateau_best["post_spearman"],
        "post_spearman_p":     plateau_best["post_sp_p"],
        "n_plateau_candidates": len(plateau_candidates),
    }


# ──────────────────────────────────────────────────────────────────────────────
# R1-2  Gender gap trend: data-driven tipping point + per-show breakdown
# ──────────────────────────────────────────────────────────────────────────────

def analysis_gender_trend(
    gender_matrix: pd.DataFrame,
    episode_years: dict[str, int],
    gender_map: pd.Series,
    episode_dates: dict[str, Date],
) -> dict:
    """
    Compute yearly male share of appearances (known gender only).
    Uses an exhaustive split search to detect the tipping year data-driven
    (instead of hardcoding 2022), then reports per-show Spearman trends and
    pre/post-tipping-point means.
    """
    _h("R1-2  Gender Gap Trend: Data-Driven Tipping Point")

    ep_cols    = [c for c in gender_matrix.columns if c != "value"]
    ep_to_year = {c: episode_years.get(c) for c in ep_cols}

    male_row   = gender_matrix[gender_matrix["value"] == "männlich"].squeeze()
    female_row = gender_matrix[gender_matrix["value"] == "weiblich"].squeeze()

    if isinstance(male_row, pd.DataFrame) or isinstance(female_row, pd.DataFrame):
        print("  ERROR: multiple rows for männlich or weiblich")
        return {}

    rows = []
    for ep_col in ep_cols:
        yr = ep_to_year.get(ep_col)
        if not yr:
            continue
        m = male_row.get(ep_col, 0)
        f = female_row.get(ep_col, 0)
        if pd.isna(m): m = 0
        if pd.isna(f): f = 0
        rows.append({"year": yr, "male": int(m), "female": int(f)})

    ep_df  = pd.DataFrame(rows)
    yr_df  = ep_df.groupby("year")[["male", "female"]].sum().reset_index()
    yr_df  = yr_df[yr_df["male"] + yr_df["female"] > 0].copy()
    yr_df["male_share"] = yr_df["male"] / (yr_df["male"] + yr_df["female"]) * 100
    yr_df  = yr_df.sort_values("year")

    print(f"\n  Annual male share (%):\n")
    print(f"  {'Year':>6}  {'Male':>6}  {'Female':>6}  {'MaleShare%':>10}")
    _sep()
    for _, r in yr_df.iterrows():
        print(f"  {int(r['year']):>6}  {int(r['male']):>6}  {int(r['female']):>6}  {r['male_share']:>10.1f}")

    # ── Data-driven tipping point ─────────────────────────────────────────────
    _sep()
    print("\n  Exhaustive split search (best separation = lowest Mann-Whitney p):\n")
    print(f"  {'Year':>6}  {'PreMean':>8}  {'PostMean':>9}  {'U':>7}  {'p':>10}  {'PostRho':>8}")
    _sep()

    tipping_year, tipping_stats, all_candidates = detect_tipping_point(yr_df)

    for c in all_candidates:
        marker   = "  < BEST" if c["split_year"] == tipping_year else ""
        post_rho = f"{c['post_spearman']:+.3f}" if c["post_spearman"] is not None else "    n/a"
        print(f"  {c['split_year']:>6}  {c['pre_mean']:>7.1f}%  {c['post_mean']:>8.1f}%  "
              f"{c['U']:>7.0f}  {c['p']:>10.4f}  {post_rho:>8}{marker}")

    split_y     = tipping_year or 2022
    pre_period  = yr_df[yr_df["year"] < split_y]["male_share"].values
    post_period = yr_df[yr_df["year"] >= split_y]["male_share"].values
    full_years  = yr_df["year"].values.astype(float)

    _sep()
    if len(pre_period) > 0:
        print(f"    Pre-{split_y}  (n={len(pre_period):2d} yrs): mean={pre_period.mean():.1f}%  std={pre_period.std():.1f}%")
    if len(post_period) > 0:
        print(f"    {split_y}+    (n={len(post_period):2d} yrs): mean={post_period.mean():.1f}%  std={post_period.std():.1f}%")

    mwu_result: dict = {}
    if len(pre_period) >= 3 and len(post_period) >= 2:
        mwu_stat, mwu_p = stats.mannwhitneyu(pre_period, post_period, alternative="two-sided")
        print(f"\n  Mann-Whitney U (pre-{split_y} vs. {split_y}+):  U={mwu_stat:.0f}  p={mwu_p:.4f}")
        mwu_result = {"U": float(mwu_stat), "p_two_sided": float(mwu_p)}

    spearman_full = stats.spearmanr(full_years, yr_df["male_share"].values)
    print(f"\n  Spearman rho (full {int(yr_df['year'].min())}--{int(yr_df['year'].max())}): "
          f"rho={spearman_full.statistic:.4f}  p={spearman_full.pvalue:.4e}")

    pre_years = yr_df[yr_df["year"] < split_y]["year"].values.astype(float)
    if len(pre_years) >= 3:
        sp_pre = stats.spearmanr(pre_years, yr_df[yr_df["year"] < split_y]["male_share"].values)
        print(f"  Spearman rho (pre-{split_y}): rho={sp_pre.statistic:.4f}  p={sp_pre.pvalue:.4e}"
              f"  ({'decreasing' if sp_pre.statistic < 0 else 'increasing'})")

    post_years  = yr_df[yr_df["year"] >= split_y]["year"].values.astype(float)
    sp_post_stat = None
    if len(post_years) >= 2:
        sp_post      = stats.spearmanr(post_years, yr_df[yr_df["year"] >= split_y]["male_share"].values)
        sp_post_stat = sp_post.statistic
        print(f"  Spearman rho ({split_y}+):    rho={sp_post.statistic:.4f}  p={sp_post.pvalue:.4e}"
              f"  ({'flat/plateau' if sp_post.statistic >= -0.3 else 'still declining'})")

    plateau = spearman_full.statistic < -0.2 and (sp_post_stat is None or sp_post_stat >= -0.3)
    plateau_conclusion = (
        "SUPPORTED -- trend reversal detected" if plateau
        else "WEAK / NOT SUPPORTED with available annual data"
    )
    print(f"\n  Plateau claim: {plateau_conclusion}")

    # ── Per-show breakdown ────────────────────────────────────────────────────
    _h(f"R1-2  Per-Show Gender Trends (tipping point: {split_y})")
    pre_hdr  = f"Pre-{split_y}%"
    post_hdr = f"{split_y}+%"
    print(f"  {'Show':30s}  {'Yrs':>4}  {'Rho':>7}  {'p':>7}  {pre_hdr:>10}  {post_hdr:>8}  {'Delta':>7}")
    _sep()

    show_results: list[dict] = []
    for folder, show_name in PER_SHOW_DIRS.items():
        occ_path = DATA / f"50_analysis/{folder}/occurrence_matrix.csv"
        show_yr  = compute_show_annual_gender(occ_path, gender_map, episode_years)
        if show_yr is None or len(show_yr) < 3:
            continue

        sp       = stats.spearmanr(show_yr["year"].values.astype(float), show_yr["male_share"].values)
        pre_s    = show_yr[show_yr["year"] < split_y]["male_share"].values
        post_s   = show_yr[show_yr["year"] >= split_y]["male_share"].values
        pre_mean  = float(pre_s.mean())  if len(pre_s)  > 0 else None
        post_mean = float(post_s.mean()) if len(post_s) > 0 else None
        delta     = (post_mean - pre_mean) if (pre_mean is not None and post_mean is not None) else None

        pre_str   = f"{pre_mean:8.1f}%" if pre_mean  is not None else "       ---"
        post_str  = f"{post_mean:6.1f}%" if post_mean is not None else "     ---"
        delta_str = f"{delta:+6.1f}" if delta is not None else "     ---"

        print(f"  {show_name:30s}  {len(show_yr):>4}  {sp.statistic:>+6.3f}  {sp.pvalue:>7.4f}"
              f"  {pre_str}  {post_str}  {delta_str}")

        show_results.append({
            "show":                   show_name,
            "n_years":                int(len(show_yr)),
            "spearman_rho":           round(float(sp.statistic), 3),
            "spearman_p":             round(float(sp.pvalue), 4),
            "pre_tipping_mean_pct":   round(pre_mean,  1) if pre_mean  is not None else None,
            "post_tipping_mean_pct":  round(post_mean, 1) if post_mean is not None else None,
            "delta_pct":              round(delta, 1)     if delta      is not None else None,
        })

    # ── Episode-level monthly tipping point ──────────────────────────────────
    _h("R1-2  Monthly-Granularity Tipping Point (episode-level dates)")
    monthly = detect_tipping_point_monthly(gender_matrix, episode_dates)

    return {
        "tipping_year":                    tipping_year,
        "tipping_stats":                   tipping_stats,
        "monthly_tipping":                 monthly,
        "pre_tipping_mean_male_share_pct": float(pre_period.mean())  if len(pre_period)  > 0 else None,
        "post_tipping_mean_male_share_pct":float(post_period.mean()) if len(post_period) > 0 else None,
        "spearman_full_rho":               float(spearman_full.statistic),
        "spearman_full_p":                 float(spearman_full.pvalue),
        "mannwhitney_periods":             mwu_result,
        "plateau_conclusion":              plateau_conclusion,
        "per_show":                        show_results,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 72)
    print("  Speaker Mining — R1-2 Gender Gap Trend Analysis (long-running)")
    print("=" * 72)

    _h("Loading data")

    print(f"  Loading dedup_persons  ...", end="", flush=True)
    dedup_persons = pd.read_csv(DEDUP_PERSONS_CSV, dtype=str, low_memory=False).fillna("")
    print(f" {len(dedup_persons):,} rows")

    person_props  = load_person_properties_from_cache(dedup_persons)
    episode_years = load_episode_premiere_years(ALIGNED_EPISODES_CSV)

    print(f"  Loading episode premiere dates  ...", end="", flush=True)
    episode_dates = load_episode_premiere_dates(ALIGNED_EPISODES_CSV)
    print(f" {len(episode_dates):,} episodes with full dates")

    print(f"  Loading gender matrix  ...", end="", flush=True)
    gender_matrix = pd.read_csv(GENDER_MATRIX_CSV, dtype=str, low_memory=False)
    print(f" {len(gender_matrix):,} rows")

    gender_map = build_person_gender_map(person_props, dedup_persons)

    result = analysis_gender_trend(gender_matrix, episode_years, gender_map, episode_dates)

    OUT_JSON.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    print(f"\n  Results written to: {OUT_JSON}")
    print(f"\nDone.")


if __name__ == "__main__":
    main()
