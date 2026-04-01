from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

from .config import FILE_SEASONS, PHASE_DIR, SEASON_COLUMNS
from process.io_guardrails import atomic_write_csv


def extract_season_rows(episodes_df: pd.DataFrame) -> pd.DataFrame:
	if episodes_df.empty:
		return pd.DataFrame(columns=SEASON_COLUMNS)

	work = episodes_df.copy()
	work["_dt"] = pd.to_datetime(work["publikationsdatum"], format="%d.%m.%Y", errors="coerce")
	work = work.dropna(subset=["_dt"])
	if work.empty:
		return pd.DataFrame(columns=SEASON_COLUMNS)

	out_rows: list[dict[str, str | int]] = []
	for season_label, grp in work.groupby("season", dropna=False):
		season_label = str(season_label or "").strip()
		if not season_label:
			continue

		start_dt = grp["_dt"].min()
		end_dt = grp["_dt"].max()

		season_id = "se_" + hashlib.sha1(season_label.encode("utf-8")).hexdigest()[:12]
		out_rows.append(
			{
				"season_id": season_id,
				"season_label": season_label,
				"start_time": start_dt.strftime("%d.%m.%Y"),
				"end_time": end_dt.strftime("%d.%m.%Y"),
				"episode_count": int(grp.shape[0]),
				"_start_dt": start_dt,
			}
		)

	df = pd.DataFrame(out_rows)
	if df.empty:
		return pd.DataFrame(columns=SEASON_COLUMNS)
	return df.sort_values(by=["_start_dt", "season_label"]).drop(columns=["_start_dt"])[SEASON_COLUMNS]


def save_seasons(df: pd.DataFrame, output_dir: str | Path | None = None) -> Path:
	out_dir = Path(output_dir) if output_dir else PHASE_DIR
	out_dir.mkdir(parents=True, exist_ok=True)
	out_path = out_dir / FILE_SEASONS
	atomic_write_csv(out_path, df, index=False)
	return out_path
