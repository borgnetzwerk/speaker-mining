from __future__ import annotations

from pathlib import Path

import pandas as pd

from .contracts import COMMON_BASE_COLUMNS, OUTPUT_FILES, REQUIRED_ALIGNED_FILES, UNRESOLVED_TIER


class QualityGateError(RuntimeError):
    pass


def _load_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str).fillna("")


def run_quality_gates() -> dict[str, str | int | float]:
    missing = [name for name in REQUIRED_ALIGNED_FILES if not OUTPUT_FILES[name].exists()]
    if missing:
        raise QualityGateError(f"Missing aligned output files: {missing}")

    unresolved_rows = 0
    inferred_rows = 0

    for name in REQUIRED_ALIGNED_FILES:
        df = _load_csv(OUTPUT_FILES[name])

        missing_columns = [col for col in COMMON_BASE_COLUMNS if col not in df.columns]
        if missing_columns:
            raise QualityGateError(f"{name} missing shared columns: {missing_columns}")

        if not df.empty and df["alignment_unit_id"].duplicated().any():
            duplicated = int(df["alignment_unit_id"].duplicated().sum())
            raise QualityGateError(f"{name} has duplicate alignment_unit_id values: {duplicated}")

        unresolved = df[df["match_tier"] == UNRESOLVED_TIER]
        unresolved_rows += len(unresolved)
        if not unresolved.empty:
            bad_code = unresolved["unresolved_reason_code"].str.strip() == ""
            bad_detail = unresolved["unresolved_reason_detail"].str.strip() == ""
            if bad_code.any() or bad_detail.any():
                raise QualityGateError(f"{name} has unresolved rows without unresolved reason fields")

        inferred = df[df["inference_flag"].str.lower() == "true"]
        inferred_rows += len(inferred)
        if not inferred.empty:
            bad_basis = inferred["inference_basis"].str.strip() == ""
            if bad_basis.any():
                raise QualityGateError(f"{name} has inferred rows without inference_basis")

    return {
        "status": "ok",
        "unresolved_rows": unresolved_rows,
        "inferred_rows": inferred_rows,
        "checked_files": len(REQUIRED_ALIGNED_FILES),
    }
