from __future__ import annotations

from pathlib import Path

import pandas as pd

from .config import PHASE_DIR


def split_exact_duplicates(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split a DataFrame into unique rows and exact duplicate rows.

    Exact duplicates are rows where all column values are identical.
    The first occurrence is kept in the unique output; subsequent identical
    rows are returned in the duplicate output.
    """
    if df.empty:
        return df.copy(), df.copy()

    duplicate_mask = df.duplicated(keep="first")
    unique_df = df.loc[~duplicate_mask].copy().reset_index(drop=True)
    duplicates_df = df.loc[duplicate_mask].copy().reset_index(drop=True)
    return unique_df, duplicates_df


def save_exact_duplicate_rows(
    table_name: str,
    duplicates_df: pd.DataFrame,
    output_dir: str | Path | None = None,
) -> Path:
    """Persist exact duplicate rows for one table under data/10_mention_detection."""
    out_dir = Path(output_dir) if output_dir else PHASE_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"duplicates_{table_name}.csv"
    duplicates_df.to_csv(out_path, index=False)
    return out_path


def filter_exact_duplicates_with_report(
    table_name: str,
    df: pd.DataFrame,
    output_dir: str | Path | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, Path, dict[str, int]]:
    """Filter exact duplicates and persist duplicate rows for reporting.

    Returns:
        (filtered_df, duplicates_df, duplicates_path, stats)
        where stats contains raw_rows, kept_rows, duplicate_rows.
    """
    filtered_df, duplicates_df = split_exact_duplicates(df)
    duplicates_path = save_exact_duplicate_rows(table_name, duplicates_df, output_dir)
    stats = {
        "raw_rows": int(len(df)),
        "kept_rows": int(len(filtered_df)),
        "duplicate_rows": int(len(duplicates_df)),
    }
    return filtered_df, duplicates_df, duplicates_path, stats
