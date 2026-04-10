from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from process.io_guardrails import atomic_write_csv, atomic_write_text


def test_atomic_write_csv_creates_recovery_and_resumes(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "guarded.csv"
    recovery = target.with_suffix(target.suffix + ".recovery")
    first_df = pd.DataFrame([{"value": 1}])
    second_df = pd.DataFrame([{"value": 2}])

    original_replace = Path.replace

    def _replace_with_lock_failure(self: Path, target_path) -> Path:
        if self.suffix == ".tmp" and Path(target_path) == target:
            raise PermissionError("simulated lock")
        return original_replace(self, target_path)

    monkeypatch.setattr(Path, "replace", _replace_with_lock_failure)

    with pytest.raises(RuntimeError, match="recovery snapshot"):
        atomic_write_csv(target, first_df, index=False)

    assert recovery.exists()

    monkeypatch.setattr(Path, "replace", original_replace)

    # Next run restores pending recovery and then proceeds with normal write.
    atomic_write_csv(target, second_df, index=False)

    assert not recovery.exists()
    restored_df = pd.read_csv(target)
    assert restored_df["value"].tolist() == [2]


def test_atomic_write_csv_skips_identical_rewrites(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "guarded.csv"
    df = pd.DataFrame([{"value": 1}, {"value": 2}])

    atomic_write_csv(target, df, index=False)
    before_text = target.read_text(encoding="utf-8")

    def _forbidden_replace(self: Path, target_path) -> Path:
        raise AssertionError("identical CSV rewrites should not rename the file")

    monkeypatch.setattr(Path, "replace", _forbidden_replace)

    atomic_write_csv(target, df, index=False)

    assert target.read_text(encoding="utf-8") == before_text


def test_atomic_write_text_skips_identical_rewrites(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "summary.json"
    text = '{"a":1}\n'

    atomic_write_text(target, text)
    before_text = target.read_text(encoding="utf-8")

    def _forbidden_replace(self: Path, target_path) -> Path:
        raise AssertionError("identical text rewrites should not rename the file")

    monkeypatch.setattr(Path, "replace", _forbidden_replace)

    atomic_write_text(target, text)

    assert target.read_text(encoding="utf-8") == before_text
