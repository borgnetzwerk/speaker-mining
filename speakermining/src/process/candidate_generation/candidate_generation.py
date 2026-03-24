from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd

from .config import (
	CACHE_DIR,
	CANDIDATE_COLUMNS,
	FILE_CANDIDATES,
	FILE_LINKS,
	LINK_COLUMNS,
	PHASE_DIR,
	SOURCE_PRIORITY,
)


def _empty_candidates() -> pd.DataFrame:
	return pd.DataFrame(columns=CANDIDATE_COLUMNS)


def _empty_links() -> pd.DataFrame:
	return pd.DataFrame(columns=LINK_COLUMNS)


def source_priority_rank(source: str) -> int:
	try:
		return SOURCE_PRIORITY.index(source)
	except ValueError:
		return len(SOURCE_PRIORITY)


def merge_candidate_frames(frames: Iterable[pd.DataFrame]) -> pd.DataFrame:
	frames = [f for f in frames if f is not None and not f.empty]
	if not frames:
		return _empty_candidates()

	df = pd.concat(frames, ignore_index=True)
	missing = [c for c in CANDIDATE_COLUMNS if c not in df.columns]
	if missing:
		raise ValueError(f"Candidate frame missing columns: {missing}")

	df = df[CANDIDATE_COLUMNS].copy()
	df["_rank"] = df["source"].astype(str).map(source_priority_rank)
	df["_score"] = pd.to_numeric(df["score"], errors="coerce").fillna(0.0)

	df = df.sort_values(by=["mention_id", "_rank", "_score"], ascending=[True, True, False])
	df = df.drop_duplicates(subset=["mention_id", "candidate_id"], keep="first")
	return df.drop(columns=["_rank", "_score"]).reset_index(drop=True)


def merge_link_frames(frames: Iterable[pd.DataFrame]) -> pd.DataFrame:
	frames = [f for f in frames if f is not None and not f.empty]
	if not frames:
		return _empty_links()

	df = pd.concat(frames, ignore_index=True)
	missing = [c for c in LINK_COLUMNS if c not in df.columns]
	if missing:
		raise ValueError(f"Link frame missing columns: {missing}")

	return df[LINK_COLUMNS].drop_duplicates().reset_index(drop=True)


def load_cache(cache_name: str) -> pd.DataFrame:
	CACHE_DIR.mkdir(parents=True, exist_ok=True)
	path = CACHE_DIR / cache_name
	if not path.exists():
		return pd.DataFrame()
	return pd.read_csv(path)


def append_cache_rows(cache_name: str, rows: pd.DataFrame) -> Path:
	CACHE_DIR.mkdir(parents=True, exist_ok=True)
	path = CACHE_DIR / cache_name
	if path.exists():
		current = pd.read_csv(path)
		out = pd.concat([current, rows], ignore_index=True).drop_duplicates()
	else:
		out = rows.drop_duplicates().copy()
	out.to_csv(path, index=False)
	return path


def save_candidates(df: pd.DataFrame, output_dir: str | Path | None = None) -> Path:
	out_dir = Path(output_dir) if output_dir else PHASE_DIR
	out_dir.mkdir(parents=True, exist_ok=True)
	out_path = out_dir / FILE_CANDIDATES
	df[CANDIDATE_COLUMNS].to_csv(out_path, index=False)
	return out_path


def save_links(df: pd.DataFrame, output_dir: str | Path | None = None) -> Path:
	out_dir = Path(output_dir) if output_dir else PHASE_DIR
	out_dir.mkdir(parents=True, exist_ok=True)
	out_path = out_dir / FILE_LINKS
	df[LINK_COLUMNS].to_csv(out_path, index=False)
	return out_path
