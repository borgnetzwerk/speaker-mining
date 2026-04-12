from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from process.io_guardrails import atomic_write_csv

from .contracts import INPUT_FILES, OUTPUT_FILES


def write_schema_mapping(datasets: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows: list[dict[str, str]] = []

    for source_name, df in datasets.items():
        for column in df.columns:
            rows.append(
                {
                    "source_name": source_name,
                    "source_column": column,
                    "canonical_column": column,
                    "mapping_strategy": "direct",
                }
            )

    # Ensure source inventory is symmetric: include all remaining input files,
    # including projection JSON structures that are not represented as normalized DataFrames.
    for source_name, path in INPUT_FILES.items():
        if source_name in datasets:
            continue

        if path.suffix.lower() == ".csv" and path.exists():
            df = pd.read_csv(path, dtype=str, nrows=1).fillna("")
            for column in df.columns:
                rows.append(
                    {
                        "source_name": source_name,
                        "source_column": column,
                        "canonical_column": column,
                        "mapping_strategy": "direct_raw_inventory",
                    }
                )
            continue

        if path.suffix.lower() == ".json" and path.exists():
            with path.open("r", encoding="utf-8") as f:
                payload = json.load(f)

            json_columns: set[str] = set()
            if isinstance(payload, dict):
                for item in payload.values():
                    if not isinstance(item, dict):
                        continue
                    json_columns.update(item.keys())
                    claims = item.get("claims", {}) or {}
                    if isinstance(claims, dict):
                        for claim_key in claims.keys():
                            json_columns.add(f"claims.{claim_key}")

            for column in sorted(json_columns):
                rows.append(
                    {
                        "source_name": source_name,
                        "source_column": column,
                        "canonical_column": column,
                        "mapping_strategy": "direct_raw_inventory",
                    }
                )

    mapping_df = pd.DataFrame(rows).sort_values(by=["source_name", "source_column"]).reset_index(drop=True)
    atomic_write_csv(OUTPUT_FILES["source_schema_mapping"], mapping_df, index=False)
    return mapping_df
