"""Shared guarded write helpers for process modules.

These helpers provide atomic writes plus soft-recovery snapshots when a final
rename is blocked by OS file locks (common on Windows).
"""
from __future__ import annotations

import os
import time
from pathlib import Path

import pandas as pd


_PROTECTED_DELETE_NAMES = {"archive", "archives", "backup", "backups"}


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


def _is_protected_archive_or_backup_path(path: Path) -> bool:
	parts = {str(part).lower() for part in Path(path).parts}
	return any(part in _PROTECTED_DELETE_NAMES for part in parts)


def _contains_protected_backup_descendant(path: Path) -> bool:
	target = Path(path)
	if not target.exists() or not target.is_dir():
		return False
	for descendant in target.rglob("*"):
		if descendant.is_dir() and str(descendant.name).lower() in _PROTECTED_DELETE_NAMES:
			return True
	return False


def assert_safe_delete_target(path: str | Path) -> Path:
	target = Path(path)
	if _is_protected_archive_or_backup_path(target):
		raise RuntimeError(f"Refusing to delete protected archive/backup path: {target}")
	if target.exists() and target.is_dir() and _contains_protected_backup_descendant(target):
		raise RuntimeError(f"Refusing to delete directory containing a backup/archive tree: {target}")
	return target


def safe_unlink(path: str | Path, *, missing_ok: bool = False) -> None:
	assert_safe_delete_target(path).unlink(missing_ok=missing_ok)


def safe_rmtree(path: str | Path) -> None:
	target = assert_safe_delete_target(path)
	if target.exists():
		import shutil

		shutil.rmtree(target)


def atomic_write_text(path: str | Path, text: str, encoding: str = "utf-8") -> Path:
	"""Write text atomically with Windows file-lock retry logic.
	
	On Windows, file handles can persist briefly after read operations,
	causing replace() to fail. This function retries with exponential backoff.
	"""
	target = Path(path)
	target.parent.mkdir(parents=True, exist_ok=True)
	_restore_recovery_if_present(target)
	if target.exists():
		try:
			if target.read_text(encoding=encoding).replace("\r\n", "\n").replace("\r", "\n") == text.replace("\r\n", "\n").replace("\r", "\n"):
				return target
		except Exception:
			pass
	tmp_path = target.with_suffix(target.suffix + ".tmp")
	
	max_retries = 5
	retry_delay_ms = 10  # Start with 10ms
	
	for attempt in range(max_retries):
		try:
			tmp_path.write_text(text, encoding=encoding)
			# Explicitly flush to ensure data is written
			tmp_path.sync() if hasattr(Path, 'sync') else None
			tmp_path.replace(target)
			return target
		except PermissionError as exc:
			if attempt < max_retries - 1:
				# Retry with exponential backoff
				delay = retry_delay_ms * (2 ** attempt) / 1000.0
				time.sleep(delay)
				continue
			# Final attempt failed; create recovery snapshot
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
						safe_unlink(tmp_path)
				except Exception:
					pass
			raise RuntimeError(
				(
					f"Permission denied while writing {target} after {max_retries} retries. "
					f"A recovery snapshot was written to {recovery_path}. "
					"Stop this run, close any editor/process that may lock the target file, "
					"then rerun to restore and continue."
				)
			) from exc
	return target


def atomic_write_csv(path: str | Path, df: pd.DataFrame, *, index: bool = False) -> Path:
	"""Write a CSV atomically with Windows file-lock retry logic.
	
	On Windows, file handles can persist briefly after read operations,
	causing replace() to fail. This function retries with exponential backoff.
	"""
	target = Path(path)
	target.parent.mkdir(parents=True, exist_ok=True)
	_restore_recovery_if_present(target)
	csv_text = df.to_csv(index=index, lineterminator="\n")
	if target.exists():
		try:
			if target.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n") == csv_text:
				return target
		except Exception:
			pass
	tmp_path = target.with_suffix(target.suffix + ".tmp")
	
	max_retries = 5
	retry_delay_ms = 10  # Start with 10ms
	
	for attempt in range(max_retries):
		try:
			tmp_path.write_text(csv_text, encoding="utf-8", newline="")
			tmp_path.replace(target)
			return target
		except PermissionError as exc:
			if attempt < max_retries - 1:
				# Retry with exponential backoff
				delay = retry_delay_ms * (2 ** attempt) / 1000.0
				time.sleep(delay)
				continue
			# Final attempt failed; create recovery snapshot
			recovery_path = _recovery_path(target)
			try:
				if tmp_path.exists():
					tmp_path.replace(recovery_path)
				else:
					recovery_path.write_text(csv_text, encoding="utf-8", newline="")
			except Exception:
				recovery_path.write_text(csv_text, encoding="utf-8", newline="")
			finally:
				try:
					if tmp_path.exists():
						safe_unlink(tmp_path)
				except Exception:
					pass
			raise RuntimeError(
				(
					f"Permission denied while writing {target} after {max_retries} retries. "
					f"A recovery snapshot was written to {recovery_path}. "
					"Stop this run, close any editor/process that may lock the target file, "
					"then rerun to restore and continue."
				)
			) from exc
	return target


def atomic_write_parquet(path: str | Path, df: pd.DataFrame, *, index: bool = False) -> Path:
	"""Write a Parquet file atomically with the same lock/recovery policy as CSV/text."""
	target = Path(path)
	target.parent.mkdir(parents=True, exist_ok=True)
	_restore_recovery_if_present(target)
	tmp_path = target.with_suffix(target.suffix + ".tmp")

	max_retries = 5
	retry_delay_ms = 10

	for attempt in range(max_retries):
		try:
			df.to_parquet(tmp_path, index=index)
			tmp_path.replace(target)
			return target
		except PermissionError as exc:
			if attempt < max_retries - 1:
				delay = retry_delay_ms * (2 ** attempt) / 1000.0
				time.sleep(delay)
				continue
			recovery_path = _recovery_path(target)
			try:
				if tmp_path.exists():
					tmp_path.replace(recovery_path)
				else:
					df.to_parquet(recovery_path, index=index)
			except Exception:
				df.to_parquet(recovery_path, index=index)
			finally:
				try:
					if tmp_path.exists():
						safe_unlink(tmp_path)
				except Exception:
					pass
			raise RuntimeError(
				(
					f"Permission denied while writing {target} after {max_retries} retries. "
					f"A recovery snapshot was written to {recovery_path}. "
					"Stop this run, close any editor/process that may lock the target file, "
					"then rerun to restore and continue."
				)
			) from exc
	return target