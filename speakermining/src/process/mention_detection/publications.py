from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pandas as pd

from .config import FILE_PUBLIKATION, PHASE_DIR, PUBLIKATION_COLUMNS


def _stable_publikation_id(episode_id: str, publication_index: int, raw_line: str) -> str:
	raw = f"{episode_id}|{publication_index}|{raw_line[:200]}".encode("utf-8")
	digest = hashlib.sha1(raw).hexdigest()[:12]
	return f"pb_{digest}"


def _publication_section(text: str) -> str:
	if "Publikation" not in text:
		return ""

	tail = text.split("Publikation", 1)[1]
	end_markers = ["Archivnummer", "Sendetitel", "FolgenNr"]
	end_positions = [tail.find(marker) for marker in end_markers if tail.find(marker) >= 0]
	if end_positions:
		tail = tail[: min(end_positions)]
	return tail.strip()


def extract_publication_rows_from_text(text: str) -> list[dict[str, str]]:
	section = _publication_section(text)
	if not section:
		return []

	rows: list[dict[str, str]] = []
	for line in section.splitlines():
		line = line.strip()
		if not line:
			continue

		m = re.match(r"^(\d{2}\.\d{2}\.\d{4})\s+(\d{2}:\d{2}:\d{2})\s+(.+)$", line)
		if not m:
			continue

		date_value = m.group(1)
		time_value = m.group(2)
		tokens = m.group(3).split()
		if not tokens:
			continue

		program = tokens[-1]
		meta_tokens = tokens[:-1]

		duration = ""
		if meta_tokens and re.match(r"^\d{2,3}'\d{2}$", meta_tokens[0]):
			duration = meta_tokens[0]
			meta_tokens = meta_tokens[1:]

		prod_numbers = [t for t in meta_tokens if re.match(r"^\d{5}/\d{5}$", t)]
		prod_nr_sendung = prod_numbers[0] if len(prod_numbers) >= 1 else ""
		prod_nr_secondary = prod_numbers[1] if len(prod_numbers) >= 2 else ""

		rows.append(
			{
				"date": date_value,
				"time": time_value,
				"duration": duration,
				"prod_nr_sendung": prod_nr_sendung,
				"prod_nr_secondary": prod_nr_secondary,
				"program": program,
				"raw_line": line,
			}
		)

	return rows


def build_publication_rows(episode_id: str, parsed_publications: list[dict[str, str]]) -> tuple[str, list[dict[str, str]]]:
	primary_publication_id = ""
	rows: list[dict[str, str]] = []

	for pub_idx, pub in enumerate(parsed_publications, start=1):
		publikation_id = _stable_publikation_id(episode_id, pub_idx, pub.get("raw_line", ""))
		if pub_idx == 1:
			primary_publication_id = publikation_id

		rows.append(
			{
				"publikation_id": publikation_id,
				"episode_id": episode_id,
				"publication_index": str(pub_idx),
				"date": pub.get("date", ""),
				"time": pub.get("time", ""),
				"duration": pub.get("duration", ""),
				"program": pub.get("program", ""),
				"prod_nr_sendung": pub.get("prod_nr_sendung", ""),
				"prod_nr_secondary": pub.get("prod_nr_secondary", ""),
				"is_primary": "1" if pub_idx == 1 else "0",
				"raw_line": pub.get("raw_line", ""),
			}
		)

	return primary_publication_id, rows


def to_publication_dataframe(rows: list[dict[str, str]]) -> pd.DataFrame:
	df = pd.DataFrame(rows)
	if df.empty:
		return pd.DataFrame(columns=PUBLIKATION_COLUMNS)
	return df.sort_values(by=["episode_id", "publication_index"])[PUBLIKATION_COLUMNS]


def save_publications(df: pd.DataFrame, output_dir: str | Path | None = None) -> Path:
	out_dir = Path(output_dir) if output_dir else PHASE_DIR
	out_dir.mkdir(parents=True, exist_ok=True)
	out_path = out_dir / FILE_PUBLIKATION
	df.to_csv(out_path, index=False)
	return out_path
