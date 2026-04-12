from __future__ import annotations

import shutil
from pathlib import Path

import pandas as pd

from process.io_guardrails import atomic_write_csv

from .contracts import INPUT_FILES, RAW_IMPORT_DIR


def stage_inputs() -> pd.DataFrame:
    rows: list[dict[str, str | int]] = []
    RAW_IMPORT_DIR.mkdir(parents=True, exist_ok=True)

    for logical_name, source_path in INPUT_FILES.items():
        target_name = source_path.name
        target_path = RAW_IMPORT_DIR / target_name
        if target_path.exists():
            # Guard against rare filename collisions across different sources.
            target_name = f"{logical_name}__{source_path.name}"
            target_path = RAW_IMPORT_DIR / target_name
        shutil.copy2(source_path, target_path)

        rows.append(
            {
                "logical_name": logical_name,
                "source_path": source_path.as_posix(),
                "staged_path": target_path.as_posix(),
                "staged_filename": target_name,
                "size_bytes": source_path.stat().st_size,
            }
        )

    manifest_df = pd.DataFrame(rows).sort_values(by=["logical_name"]).reset_index(drop=True)
    atomic_write_csv(RAW_IMPORT_DIR / "staging_manifest.csv", manifest_df, index=False)
    return manifest_df
