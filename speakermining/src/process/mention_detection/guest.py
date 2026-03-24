from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Iterable

import pandas as pd

from .config import FILE_PERSON_MENTIONS, PERSON_MENTION_COLUMNS, PHASE_DIR


def _extract_sachinhalt(text: str) -> str:
	m = re.search(r"Sachinhalt(.*?)Jugendeignung", text, flags=re.DOTALL | re.IGNORECASE)
	return m.group(1).strip() if m else ""


def _extract_person_blocks(sachinhalt: str) -> list[tuple[str, str]]:
	out: list[tuple[str, str]] = []
	for m in re.finditer(r"([^)]+?)\(([^)]+)\)", sachinhalt):
		raw_names = m.group(1).strip(" ,;")
		desc = m.group(2).strip()
		out.append((raw_names, desc))
	return out


def _extract_candidate_names(raw_names: str) -> list[str]:
	# Precision-first name extraction: TitleCase parts with uppercase surname patterns.
	pattern = re.compile(
		r"\b[A-ZÄÖÜ][a-zäöüß]+(?:\s+(?:[A-Z]\.?|[A-ZÄÖÜ][a-zäöüß]+))*\s+"
		r"[A-ZÄÖÜ][A-ZÄÖÜß-]+\b"
	)
	names = [n.strip() for n in pattern.findall(raw_names)]
	if names:
		return names

	# Conservative fallback split.
	parts = [p.strip() for p in re.split(r",| und ", raw_names) if p.strip()]
	return [p for p in parts if len(p.split()) >= 2]


def _mention_id(episode_id: str, name: str, beschreibung: str) -> str:
	raw = f"{episode_id}|{name}|{beschreibung}".encode("utf-8")
	return f"pm_{hashlib.sha1(raw).hexdigest()[:12]}"


def extract_person_mentions(episode_blocks: Iterable[str], episodes_df: pd.DataFrame) -> pd.DataFrame:
	rows: list[dict[str, str]] = []

	# Build fast lookup by title+date-ish key using episode order as fallback.
	episode_ids = episodes_df["episode_id"].tolist() if not episodes_df.empty else []

	for idx, block in enumerate(episode_blocks):
		if idx >= len(episode_ids):
			break

		episode_id = episode_ids[idx]
		sachinhalt = _extract_sachinhalt(block)
		if not sachinhalt:
			continue

		for raw_names, desc in _extract_person_blocks(sachinhalt):
			for name in _extract_candidate_names(raw_names):
				rows.append(
					{
						"mention_id": _mention_id(episode_id, name, desc),
						"episode_id": episode_id,
						"name": name,
						"beschreibung": desc,
						"source_text": raw_names,
					}
				)

	df = pd.DataFrame(rows)
	if df.empty:
		return pd.DataFrame(columns=PERSON_MENTION_COLUMNS)

	df = df.drop_duplicates(subset=["episode_id", "name", "beschreibung"]).reset_index(drop=True)
	return df[PERSON_MENTION_COLUMNS]


def save_person_mentions(df: pd.DataFrame, output_dir: str | Path | None = None) -> Path:
	out_dir = Path(output_dir) if output_dir else PHASE_DIR
	out_dir.mkdir(parents=True, exist_ok=True)
	out_path = out_dir / FILE_PERSON_MENTIONS
	df.to_csv(out_path, index=False)
	return out_path
