from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Iterable

import pandas as pd

from .config import FILE_INSTITUTION_MENTIONS, INSTITUTION_MENTION_COLUMNS, PHASE_DIR


_INSTITUTION_HINTS = [
	"ZDF",
	"ARD",
	"SPD",
	"CDU",
	"CSU",
	"FDP",
	"BSW",
	"NATO",
	"EU",
	"Bundestag",
	"Bundesregierung",
	"Stiftung",
	"Institut",
	"Universität",
	"Universitaet",
	"Verband",
	"Klinik",
]


def _extract_sachinhalt(text: str) -> str:
	m = re.search(r"Sachinhalt(.*?)Jugendeignung", text, flags=re.DOTALL | re.IGNORECASE)
	return m.group(1).strip() if m else ""


def _institution_mentions_from_text(text: str) -> list[str]:
	candidates: set[str] = set()

	for hint in _INSTITUTION_HINTS:
		if hint in text:
			candidates.add(hint)

	# Capture quoted organization names.
	for m in re.finditer(r'"([^"]{3,80})"', text):
		value = m.group(1).strip()
		if any(k.lower() in value.lower() for k in ["stiftung", "institut", "verband", "zdf", "ard"]):
			candidates.add(value)

	return sorted(candidates)


def _mention_id(episode_id: str, institution: str) -> str:
	raw = f"{episode_id}|{institution}".encode("utf-8")
	return f"im_{hashlib.sha1(raw).hexdigest()[:12]}"


def extract_institution_mentions(episode_blocks: Iterable[str], episodes_df: pd.DataFrame) -> pd.DataFrame:
	rows: list[dict[str, str]] = []
	episode_ids = episodes_df["episode_id"].tolist() if not episodes_df.empty else []

	for idx, block in enumerate(episode_blocks):
		if idx >= len(episode_ids):
			break

		episode_id = episode_ids[idx]
		sachinhalt = _extract_sachinhalt(block)
		if not sachinhalt:
			continue

		for institution in _institution_mentions_from_text(sachinhalt):
			rows.append(
				{
					"mention_id": _mention_id(episode_id, institution),
					"episode_id": episode_id,
					"institution": institution,
					"source_text": sachinhalt,
				}
			)

	df = pd.DataFrame(rows)
	if df.empty:
		return pd.DataFrame(columns=INSTITUTION_MENTION_COLUMNS)
	df = df.drop_duplicates(subset=["episode_id", "institution"]).reset_index(drop=True)
	episode_order = {eid: idx for idx, eid in enumerate(episodes_df["episode_id"].tolist())}
	df["_episode_order"] = df["episode_id"].map(episode_order).fillna(len(episode_order)).astype(int)
	df = df.sort_values(by=["_episode_order", "institution", "mention_id"]).drop(columns=["_episode_order"])
	return df[INSTITUTION_MENTION_COLUMNS]


def save_institution_mentions(df: pd.DataFrame, output_dir: str | Path | None = None) -> Path:
	out_dir = Path(output_dir) if output_dir else PHASE_DIR
	out_dir.mkdir(parents=True, exist_ok=True)
	out_path = out_dir / FILE_INSTITUTION_MENTIONS
	df.to_csv(out_path, index=False)
	return out_path
