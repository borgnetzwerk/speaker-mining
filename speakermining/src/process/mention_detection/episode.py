from __future__ import annotations

import hashlib
import re
from datetime import datetime
from pathlib import Path
from typing import Iterable

import pandas as pd

from .config import EPISODE_COLUMNS, FILE_EPISODES, FILE_SEASONS, PHASE_DIR, SEASON_COLUMNS


def _stable_episode_id(title: str, date_value: str, fallback_text: str) -> str:
	raw = f"{title}|{date_value}|{fallback_text[:200]}".encode("utf-8")
	digest = hashlib.sha1(raw).hexdigest()[:12]
	return f"ep_{digest}"


def _search(pattern: str, text: str) -> str:
	match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
	return match.group(1).strip() if match else ""


def _extract_title(text: str) -> str:
	line = _search(r"Sendetitel\s*(.+)", text)
	if line:
		return line.splitlines()[0].strip()
	return ""


def _extract_date(text: str) -> str:
	if "Publikation" in text:
		tail = text.split("Publikation", 1)[1]
		m = re.search(r"(\d{2}\.\d{2}\.\d{4})", tail)
		if m:
			return m.group(1)
	m = re.search(r"(\d{2}\.\d{2}\.\d{4})", text)
	return m.group(1) if m else ""


def _extract_info_block(text: str) -> str:
	m = re.search(r"Sachinhalt(.*?)Jugendeignung", text, flags=re.DOTALL | re.IGNORECASE)
	if not m:
		return ""
	return " ".join(m.group(1).replace("\n", " ").split())


def _extract_time_length(text: str) -> str:
	m = re.search(r"\b(\d{2,3}'\d{2})\b", text)
	return m.group(1) if m else ""


def _extract_field(label: str, text: str) -> str:
	return _search(rf"\b{label}\s+(\d+)\b", text)


def _season_string(staffel: str, title: str, date_value: str) -> str:
	if staffel:
		return f"Markus Lanz, Staffel {staffel}"

	if re.match(r"^Markus Lanz \d{2}\.\d{2}\.\d{4}$", title) and date_value:
		try:
			dt = datetime.strptime(date_value, "%d.%m.%Y")
			return f"Markus Lanz, Staffel {dt.year - 2007}"
		except ValueError:
			return ""
	return ""


def extract_episode_rows(episode_blocks: Iterable[str]) -> pd.DataFrame:
	rows: list[dict[str, str]] = []

	for block in episode_blocks:
		if not block.strip():
			continue

		title = _extract_title(block)
		date_value = _extract_date(block)
		staffel = _extract_field("Staffel", block)
		folge = _extract_field("Folge", block)
		folgennr = _extract_field("FolgenNr", block)

		rows.append(
			{
				"episode_id": _stable_episode_id(title, date_value, block),
				"sendungstitel": title,
				"publikationsdatum": date_value,
				"dauer": _extract_time_length(block),
				"season": _season_string(staffel, title, date_value),
				"staffel": staffel,
				"folge": folge,
				"folgennr": folgennr,
				"infos": _extract_info_block(block),
				"instance_of": "Q21191270",
				"part_of_series": "Q1499182",
				"genre": "Q622812",
				"presenter": "Q43773",
				"original_broadcaster": "Q48989",
				"country_of_origin": "Q183",
				"original_language_of_film_or_tv_show": "Q188",
			}
		)

	df = pd.DataFrame(rows)
	if df.empty:
		return pd.DataFrame(columns=EPISODE_COLUMNS)

	# Keep deterministic ordering for notebook runs.
	df["_sort"] = pd.to_datetime(df["publikationsdatum"], format="%d.%m.%Y", errors="coerce")
	df = df.sort_values(by=["_sort", "sendungstitel"], na_position="last").drop(columns=["_sort"])
	return df[EPISODE_COLUMNS]


def save_episodes(df: pd.DataFrame, output_dir: str | Path | None = None) -> Path:
	out_dir = Path(output_dir) if output_dir else PHASE_DIR
	out_dir.mkdir(parents=True, exist_ok=True)
	out_path = out_dir / FILE_EPISODES
	df.to_csv(out_path, index=False)
	return out_path


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

		season_id = "se_" + hashlib.sha1(season_label.encode("utf-8")).hexdigest()[:12]
		out_rows.append(
			{
				"season_id": season_id,
				"season_label": season_label,
				"start_time": grp["_dt"].min().strftime("%d.%m.%Y"),
				"end_time": grp["_dt"].max().strftime("%d.%m.%Y"),
				"episode_count": int(grp.shape[0]),
				"instance_of": "Q3464665",
				"part_of_series": "Q1499182",
				"genre": "Q622812",
				"presenter": "Q43773",
				"original_broadcaster": "Q48989",
				"country_of_origin": "Q183",
				"original_language_of_film_or_tv_show": "Q188",
			}
		)

	df = pd.DataFrame(out_rows)
	if df.empty:
		return pd.DataFrame(columns=SEASON_COLUMNS)
	return df.sort_values(by=["start_time", "season_label"])[SEASON_COLUMNS]


def save_seasons(df: pd.DataFrame, output_dir: str | Path | None = None) -> Path:
	out_dir = Path(output_dir) if output_dir else PHASE_DIR
	out_dir.mkdir(parents=True, exist_ok=True)
	out_path = out_dir / FILE_SEASONS
	df.to_csv(out_path, index=False)
	return out_path
