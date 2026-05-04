"""Layer 2a/2b universal analysis statistics.

These helpers are intentionally generic so notebook orchestration can stay thin
while the aggregation logic lives in the analysis package.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


UNKNOWN_LABEL = "Unknown / no data"


def _clean_series(frame: pd.DataFrame, column: str) -> pd.Series:
    values = frame[column].fillna("").astype(str).str.strip()
    return values


def _ensure_numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    return pd.to_numeric(frame[column], errors="coerce").fillna(0)


def compute_carrier_stats(
    frame: pd.DataFrame,
    *,
    value_column: str,
    carrier_column: str = "canonical_entity_id",
    appearance_column: str = "appearance_count",
    unknown_label: str = UNKNOWN_LABEL,
) -> pd.DataFrame:
    """Aggregate a property-like table into carrier-based distribution stats.

    The function expects one row per carrier/value observation. It is generic
    enough for gender, occupation, party, age bins, and any other categorical
    property once the notebook has prepared the input frame.
    """

    if frame is None or frame.empty:
        return pd.DataFrame(columns=["value", "person_count", "appearance_count", "pct_by_person", "pct_by_appearance"])

    if value_column not in frame.columns:
        raise KeyError(f"Missing required value column: {value_column}")
    if carrier_column not in frame.columns:
        raise KeyError(f"Missing required carrier column: {carrier_column}")

    working = frame.copy()
    working["_value"] = _clean_series(working, value_column)
    working["_carrier"] = _clean_series(working, carrier_column)
    working["_appearance"] = _ensure_numeric(working, appearance_column)

    total_persons = working.loc[working["_carrier"] != "", "_carrier"].nunique()
    carriers_with_any_value = working.loc[working["_value"] != "", "_carrier"].nunique()
    empty_count = max(total_persons - carriers_with_any_value, 0)
    empty_appearances = int(working.loc[working["_value"] == "", "_appearance"].sum())

    valid = working[working["_value"] != ""].copy()
    if valid.empty:
        result = pd.DataFrame(columns=["value", "person_count", "appearance_count", "pct_by_person", "pct_by_appearance"])
    else:
        grouped = (
            valid.groupby("_value", dropna=False)
            .agg(
                person_count=("_carrier", "nunique"),
                appearance_count=("_appearance", "sum"),
            )
            .reset_index()
            .rename(columns={"_value": "value"})
        )
        result = grouped

    if empty_count > 0:
        unknown_row = pd.DataFrame([
            {
                "value": unknown_label,
                "person_count": int(empty_count),
                "appearance_count": int(empty_appearances),
            }
        ])
        result = pd.concat([result, unknown_row], ignore_index=True)

    result["person_count"] = result["person_count"].fillna(0).astype(int)
    result["appearance_count"] = result["appearance_count"].fillna(0).astype(int)

    total_persons = max(int(total_persons), 1)
    total_appearances = max(int(working["_appearance"].sum()), 1)
    result["pct_by_person"] = (result["person_count"] / total_persons * 100).round(2)
    result["pct_by_appearance"] = (result["appearance_count"] / total_appearances * 100).round(2)
    result = result.sort_values(["person_count", "appearance_count", "value"], ascending=[False, False, True]).reset_index(drop=True)
    return result


def compute_episode_appearance_stats(
    frame: pd.DataFrame,
    *,
    value_column: str,
    episode_column: str = "episode_id",
    carrier_column: str = "canonical_entity_id",
) -> pd.DataFrame:
    """Aggregate a property-like table into per-value episode appearance stats."""

    if frame is None or frame.empty:
        return pd.DataFrame(columns=["value", "min_per_episode", "max_per_episode", "mean_per_episode", "std_dev_per_episode", "median_per_episode", "pct_without_value", "total_appearances", "unique_persons"])

    required = {value_column, episode_column, carrier_column}
    missing = required.difference(frame.columns)
    if missing:
        raise KeyError(f"Missing required columns: {sorted(missing)}")

    working = frame.copy()
    working["_value"] = _clean_series(working, value_column)
    working["_episode"] = _clean_series(working, episode_column)
    working["_carrier"] = _clean_series(working, carrier_column)
    valid = working[working["_value"] != ""].copy()

    if valid.empty:
        return pd.DataFrame(columns=["value", "min_per_episode", "max_per_episode", "mean_per_episode", "std_dev_per_episode", "median_per_episode", "pct_without_value", "total_appearances", "unique_persons"])

    all_episodes = sorted(e for e in working["_episode"].unique() if e != "")
    total_episodes = max(len(all_episodes), 1)
    total_persons = max(working["_carrier"].nunique(), 1)

    rows = []
    for value, subset in valid.groupby("_value", dropna=False):
        # Reindex onto all episodes so zeros are preserved for downstream diagnostics.
        per_episode = subset.groupby("_episode").size().reindex(all_episodes, fill_value=0)
        episodes_with_value = int((per_episode > 0).sum())
        rows.append(
            {
                "value": value,
                "min_per_episode": int(per_episode.min()),
                "max_per_episode": int(per_episode.max()),
                "mean_per_episode": round(float(per_episode.mean()), 2),
                "std_dev_per_episode": round(float(per_episode.std(ddof=0) if len(per_episode) > 1 else 0.0), 2),
                "median_per_episode": round(float(per_episode.median()), 2),
                "pct_without_value": round((1 - (episodes_with_value / total_episodes)) * 100, 2),
                "total_appearances": int(len(subset)),
                "unique_persons": int(subset["_carrier"].nunique()),
            }
        )

    result = pd.DataFrame(rows)
    return result.sort_values(["total_appearances", "unique_persons", "value"], ascending=[False, False, True]).reset_index(drop=True)


def expand_property_values_to_appearances(
    appearance_frame: pd.DataFrame,
    property_values: pd.DataFrame,
    *,
    carrier_column: str = "guest_qid",
    carrier_id_column: str = "canonical_entity_id",
    episode_column: str = "episode_id",
    label_column: str = "guest_label",
    value_column: str = "value",
    appearance_column: str = "appearance_count",
) -> pd.DataFrame:
    """Expand carrier-level property values to one row per appearance.

    The base frame must contain one row per carrier x episode appearance. The
    returned frame keeps that grain, sets ``appearance_count`` to 1 for every
    row, and preserves carriers without values so downstream stats can emit an
    unknown bucket without inflating counts.
    """

    if appearance_frame is None or appearance_frame.empty:
        return pd.DataFrame(
            columns=[carrier_id_column, carrier_column, label_column, episode_column, value_column, appearance_column]
        )

    required_columns = {carrier_id_column, carrier_column, episode_column}
    missing = required_columns.difference(appearance_frame.columns)
    if missing:
        raise KeyError(f"Missing required appearance columns: {sorted(missing)}")

    base = appearance_frame.copy()
    base[carrier_id_column] = _clean_series(base, carrier_id_column)
    base[carrier_column] = _clean_series(base, carrier_column)
    base[episode_column] = _clean_series(base, episode_column)
    if label_column in base.columns:
        base[label_column] = _clean_series(base, label_column)
    else:
        base[label_column] = ""
    base[appearance_column] = 1

    working = property_values.copy() if property_values is not None else pd.DataFrame()
    if working.empty:
        base[value_column] = ""
        return base[[carrier_id_column, carrier_column, label_column, episode_column, value_column, appearance_column]].copy()

    if carrier_column not in working.columns:
        if carrier_id_column in working.columns:
            working[carrier_column] = working[carrier_id_column]
        else:
            working[carrier_column] = ""

    working[carrier_column] = _clean_series(working, carrier_column)

    if value_column not in working.columns:
        if "value_label" in working.columns or "value_qid" in working.columns:
            value_label = _clean_series(working, "value_label") if "value_label" in working.columns else pd.Series("", index=working.index)
            value_qid = _clean_series(working, "value_qid") if "value_qid" in working.columns else pd.Series("", index=working.index)
            working[value_column] = value_label.where(value_label != "", value_qid)
        elif "value_year" in working.columns:
            working[value_column] = working["value_year"]
        elif "value_amount" in working.columns:
            working[value_column] = working["value_amount"]
        else:
            working[value_column] = ""

    working[value_column] = _clean_series(working, value_column)
    working = working.drop_duplicates(subset=[carrier_column, value_column])

    keep_cols = [carrier_column, value_column]
    for extra in ("value_label", "value_qid"):
        if extra in working.columns:
            keep_cols.append(extra)

    joined = base.merge(working[keep_cols], on=carrier_column, how="left")

    if "value_label" in joined.columns and "value_qid" in joined.columns:
        joined[value_column] = joined[value_column].where(
            joined[value_column] != "",
            joined["value_label"].fillna(joined["value_qid"]),
        )

    joined[value_column] = _clean_series(joined, value_column)
    joined[appearance_column] = joined[appearance_column].fillna(1).astype(int)
    return joined[[carrier_id_column, carrier_column, label_column, episode_column, value_column, appearance_column]].copy()


def build_value_episode_matrix(
    frame: pd.DataFrame,
    *,
    value_column: str,
    episode_column: str = "episode_id",
    carrier_column: str = "canonical_entity_id",
) -> pd.DataFrame:
    """Build value x episode matrix with unique carrier counts per cell.

    Each cell is the number of unique carriers with a given value present in an
    episode. Zero values are preserved for all known episode columns.
    """

    if frame is None or frame.empty:
        return pd.DataFrame(columns=["value"])

    required = {value_column, episode_column, carrier_column}
    missing = required.difference(frame.columns)
    if missing:
        raise KeyError(f"Missing required columns: {sorted(missing)}")

    working = frame.copy()
    working["_value"] = _clean_series(working, value_column)
    working["_episode"] = _clean_series(working, episode_column)
    working["_carrier"] = _clean_series(working, carrier_column)
    working = working[(working["_episode"] != "") & (working["_carrier"] != "")]

    episodes = sorted(working["_episode"].unique())
    valid = working[working["_value"] != ""]
    if valid.empty:
        out = pd.DataFrame(columns=["value"] + episodes)
        return out

    matrix = valid.pivot_table(
        index="_value",
        columns="_episode",
        values="_carrier",
        aggfunc="nunique",
        fill_value=0,
    )
    matrix = matrix.reindex(columns=episodes, fill_value=0)
    matrix = matrix.reset_index().rename(columns={"_value": "value"})
    matrix.columns.name = None
    return matrix


def build_frequency_distribution(
    frame: pd.DataFrame,
    *,
    carrier_column: str = "canonical_entity_id",
    appearance_column: str = "appearance_count",
) -> pd.DataFrame:
    """Return a frequency table mapping appearance count to guest count."""

    if frame is None or frame.empty:
        return pd.DataFrame(columns=["frequency", "guest_count"])

    if carrier_column not in frame.columns:
        raise KeyError(f"Missing required carrier column: {carrier_column}")

    working = frame.copy()
    working["_carrier"] = _clean_series(working, carrier_column)
    working["_appearance"] = _ensure_numeric(working, appearance_column).astype(int)
    per_guest = (
        working[working["_carrier"] != ""]
        .groupby("_carrier")
        .agg(appearance_count=("_appearance", "sum"))
        .reset_index(drop=True)
    )
    if per_guest.empty:
        return pd.DataFrame(columns=["frequency", "guest_count"])
    distribution = (
        per_guest["appearance_count"].value_counts()
        .sort_index()
        .reset_index()
    )
    distribution.columns = ["frequency", "guest_count"]
    return distribution


def build_pareto_table(
    frame: pd.DataFrame,
    *,
    carrier_column: str = "canonical_entity_id",
    appearance_column: str = "appearance_count",
) -> pd.DataFrame:
    """Return guest counts sorted descending with cumulative appearance shares."""

    if frame is None or frame.empty:
        return pd.DataFrame(columns=["carrier", "appearance_count", "cumulative_appearances", "pct_cumulative_appearances"])

    if carrier_column not in frame.columns:
        raise KeyError(f"Missing required carrier column: {carrier_column}")

    working = frame.copy()
    working["_carrier"] = _clean_series(working, carrier_column)
    working["_appearance"] = _ensure_numeric(working, appearance_column).astype(int)
    per_guest = (
        working[working["_carrier"] != ""]
        .groupby("_carrier")
        .agg(appearance_count=("_appearance", "sum"))
        .reset_index()
        .rename(columns={"_carrier": "carrier"})
        .sort_values(["appearance_count", "carrier"], ascending=[False, True])
        .reset_index(drop=True)
    )
    if per_guest.empty:
        return pd.DataFrame(columns=["carrier", "appearance_count", "cumulative_appearances", "pct_cumulative_appearances"])

    per_guest["cumulative_appearances"] = per_guest["appearance_count"].cumsum()
    total = max(int(per_guest["appearance_count"].sum()), 1)
    per_guest["pct_cumulative_appearances"] = (per_guest["cumulative_appearances"] / total * 100).round(2)
    return per_guest