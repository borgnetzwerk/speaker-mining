"""Shared guarded write helpers for process modules.

These helpers provide atomic writes plus soft-recovery snapshots when a final
rename is blocked by OS file locks (common on Windows).
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd


def _recovery_path(path: Path) -> Path:
	return path.with_suffix(path.suffix + ".recovery")


def _restore_recovery_if_present(path: Path) -> None:
	"""Restore pending recovery content before normal writes."""
	recovery_path = _recovery_path(path)
	if not recovery_path.exists():
		return
	try:
		recovery_path.replace(path)
	except PermissionError as exc:
		raise RuntimeError(
			(
				f"Recovery snapshot exists for {path} but could not be restored from {recovery_path}. "
				"Close any process locking the target file and rerun."
			)
		) from exc


def atomic_write_text(path: str | Path, text: str, encoding: str = "utf-8") -> Path:
	"""Write text atomically and persist a recovery snapshot on lock failures."""
	target = Path(path)
	target.parent.mkdir(parents=True, exist_ok=True)
	_restore_recovery_if_present(target)
	tmp_path = target.with_suffix(target.suffix + ".tmp")
	try:
		tmp_path.write_text(text, encoding=encoding)
		tmp_path.replace(target)
	except PermissionError as exc:
		recovery_path = _recovery_path(target)
		try:
			if tmp_path.exists():
				tmp_path.replace(recovery_path)
			else:
				recovery_path.write_text(text, encoding=encoding)
		except Exception:
			recovery_path.write_text(text, encoding=encoding)
		finally:
			try:
				if tmp_path.exists():
					tmp_path.unlink()
			except Exception:
				pass
		raise RuntimeError(
			(
				f"Permission denied while writing {target}. "
				f"A recovery snapshot was written to {recovery_path}. "
				"Stop this run, close any editor/process that may lock the target file, "
				"then rerun to restore and continue."
			)
		) from exc
	return target


def atomic_write_csv(path: str | Path, df: pd.DataFrame, *, index: bool = False) -> Path:
	"""Write a CSV atomically and persist a recovery snapshot on lock failures."""
	target = Path(path)
	target.parent.mkdir(parents=True, exist_ok=True)
	_restore_recovery_if_present(target)
	tmp_path = target.with_suffix(target.suffix + ".tmp")
	try:
		df.to_csv(tmp_path, index=index)
		tmp_path.replace(target)
	except PermissionError as exc:
		recovery_path = _recovery_path(target)
		try:
			if tmp_path.exists():
				tmp_path.replace(recovery_path)
			else:
				df.to_csv(recovery_path, index=index)
		except Exception:
			df.to_csv(recovery_path, index=index)
		finally:
			try:
				if tmp_path.exists():
					tmp_path.unlink()
			except Exception:
				pass
		raise RuntimeError(
			(
				f"Permission denied while writing {target}. "
				f"A recovery snapshot was written to {recovery_path}. "
				"Stop this run, close any editor/process that may lock the target file, "
				"then rerun to restore and continue."
			)
		) from exc
	return target