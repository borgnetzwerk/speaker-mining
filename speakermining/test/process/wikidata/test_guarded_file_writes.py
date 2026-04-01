from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from process.io_guardrails import atomic_write_csv


def test_atomic_write_csv_creates_recovery_and_resumes(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "guarded.csv"
    recovery = target.with_suffix(target.suffix + ".recovery")
    first_df = pd.DataFrame([{"value": 1}])
    second_df = pd.DataFrame([{"value": 2}])

    original_replace = Path.replace
    fail_once = {"armed": True}

    def _replace_with_single_lock_failure(self: Path, target_path) -> Path:
        if fail_once["armed"] and self.suffix == ".tmp" and Path(target_path) == target:
            fail_once["armed"] = False
            raise PermissionError("simulated lock")
        return original_replace(self, target_path)

    monkeypatch.setattr(Path, "replace", _replace_with_single_lock_failure)

    with pytest.raises(RuntimeError, match="recovery snapshot"):
        atomic_write_csv(target, first_df, index=False)

    assert recovery.exists()

    # Next run restores pending recovery and then proceeds with normal write.
    atomic_write_csv(target, second_df, index=False)

    assert not recovery.exists()
    restored_df = pd.read_csv(target)
    assert restored_df["value"].tolist() == [2]
