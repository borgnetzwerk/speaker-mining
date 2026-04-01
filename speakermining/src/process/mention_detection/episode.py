from __future__ import annotations

import hashlib
import re
from datetime import datetime
from pathlib import Path
from typing import Iterable

import pandas as pd

from .config import EPISODE_COLUMNS, FILE_EPISODES, PHASE_DIR
from .publications import build_publication_rows, extract_publication_rows_from_text, to_publication_dataframe
from process.io_guardrails import atomic_write_csv


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
	pub_rows = extract_publication_rows_from_text(text)
	if pub_rows:
		return pub_rows[0]["date"]

	if "Publikation" in text:
		tail = text.split("Publikation", 1)[1]
		m = re.search(r"(\d{2}\.\d{2}\.\d{4})", tail)
		if m:
			return m.group(1)
	m = re.search(r"(\d{2}\.\d{2}\.\d{4})", text)
	return m.group(1) if m else ""


def _extract_archivnummer(text: str) -> str:
	m = re.search(r"Archivnummer\s*(\d+)", text, flags=re.IGNORECASE)
	return m.group(1) if m else ""


def _extract_prod_nr_beitrag(text: str) -> str:
	m = re.search(r"Prod-Nr\s+Beitrag\s*([0-9]{5}/[0-9]{5})", text, flags=re.IGNORECASE)
	return m.group(1) if m else ""


def _extract_tc_range(text: str) -> tuple[str, str]:
	m = re.search(r"Zeit\s+TC\s+(\d{2}:\d{2}:\d{2})\s*-\s*(\d{2}:\d{2}:\d{2})", text, flags=re.IGNORECASE)
	if not m:
		return "", ""
	return m.group(1), m.group(2)


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


def extract_episode_and_publication_rows(episode_blocks: Iterable[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
	episode_rows: list[dict[str, str]] = []
	publication_rows_out: list[dict[str, str]] = []

	for block in episode_blocks:
		if not block.strip():
			continue

		title = _extract_title(block)
		date_value = _extract_date(block)
		parsed_publications = extract_publication_rows_from_text(block)
		primary_pub = parsed_publications[0] if parsed_publications else {}
		staffel = _extract_field("Staffel", block)
		folge = _extract_field("Folge", block)
		folgennr = _extract_field("FolgenNr", block)
		tc_start, tc_end = _extract_tc_range(block)

		episode_id = _stable_episode_id(title, date_value, block)
		primary_publication_id, publication_rows = build_publication_rows(episode_id, parsed_publications)
		publication_rows_out.extend(publication_rows)

		episode_rows.append(
			{
				"episode_id": episode_id,
				"sendungstitel": title,
				"publikation_id": primary_publication_id,
				"publikationsdatum": date_value,
				"dauer": primary_pub.get("duration", "") or _extract_time_length(block),
				"archivnummer": _extract_archivnummer(block),
				"prod_nr_beitrag": _extract_prod_nr_beitrag(block),
				"zeit_tc_start": tc_start,
				"zeit_tc_end": tc_end,
				"season": _season_string(staffel, title, date_value),
				"staffel": staffel,
				"folge": folge,
				"folgennr": folgennr,
				"infos": _extract_info_block(block),
			}
		)

	episodes_df = pd.DataFrame(episode_rows)
	if episodes_df.empty:
		episodes_df = pd.DataFrame(columns=EPISODE_COLUMNS)
	else:
		# Keep deterministic ordering for notebook runs.
		episodes_df["_sort"] = pd.to_datetime(episodes_df["publikationsdatum"], format="%d.%m.%Y", errors="coerce")
		episodes_df = episodes_df.sort_values(by=["_sort", "sendungstitel"], na_position="last").drop(columns=["_sort"])
		episodes_df = episodes_df[EPISODE_COLUMNS]

	publication_df = to_publication_dataframe(publication_rows_out)
	if not publication_df.empty:
		episode_order = {eid: idx for idx, eid in enumerate(episodes_df["episode_id"].tolist())}
		publication_df["_episode_order"] = publication_df["episode_id"].map(episode_order).fillna(len(episode_order)).astype(int)
		publication_df["_pub_idx"] = pd.to_numeric(publication_df["publication_index"], errors="coerce").fillna(0).astype(int)
		publication_df = publication_df.sort_values(by=["_episode_order", "_pub_idx", "publikation_id"]).drop(
			columns=["_episode_order", "_pub_idx"]
		)

	return episodes_df, publication_df


def extract_episode_rows(episode_blocks: Iterable[str]) -> pd.DataFrame:
	episodes_df, _ = extract_episode_and_publication_rows(episode_blocks)
	return episodes_df


def save_episodes(df: pd.DataFrame, output_dir: str | Path | None = None) -> Path:
	out_dir = Path(output_dir) if output_dir else PHASE_DIR
	out_dir.mkdir(parents=True, exist_ok=True)
	out_path = out_dir / FILE_EPISODES
	atomic_write_csv(out_path, df, index=False)
	return out_path
