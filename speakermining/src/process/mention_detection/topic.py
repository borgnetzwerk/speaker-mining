from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Iterable

import pandas as pd

from .config import FILE_TOPIC_MENTIONS, PHASE_DIR, TOPIC_MENTION_COLUMNS


def _extract_sachinhalt(text: str) -> str:
	m = re.search(r"Sachinhalt(.*?)Jugendeignung", text, flags=re.DOTALL | re.IGNORECASE)
	return m.group(1).strip() if m else ""


def _topic_snippets(text: str) -> list[str]:
	snippets: list[str] = []

	for m in re.finditer(r"(?:Themen?|Schwerpunktthemen?)\s*:\s*([^\.]+)", text, flags=re.IGNORECASE):
		value = " ".join(m.group(1).split())
		if value:
			snippets.append(value)

	# Fallback: split after semicolons in the info block.
	if not snippets:
		parts = [p.strip() for p in text.split(";") if p.strip()]
		snippets.extend(parts[:3])

	# Keep compact and deterministic.
	cleaned = []
	for s in snippets:
		s = s.strip(" -,")
		if 3 <= len(s) <= 180:
			cleaned.append(s)
	return list(dict.fromkeys(cleaned))


def _mention_id(episode_id: str, topic: str) -> str:
	raw = f"{episode_id}|{topic}".encode("utf-8")
	return f"tm_{hashlib.sha1(raw).hexdigest()[:12]}"


def extract_topic_mentions(episode_blocks: Iterable[str], episodes_df: pd.DataFrame) -> pd.DataFrame:
	rows: list[dict[str, str]] = []
	episode_ids = episodes_df["episode_id"].tolist() if not episodes_df.empty else []

	for idx, block in enumerate(episode_blocks):
		if idx >= len(episode_ids):
			break

		episode_id = episode_ids[idx]
		sachinhalt = _extract_sachinhalt(block)
		if not sachinhalt:
			continue

		for topic in _topic_snippets(sachinhalt):
			rows.append(
				{
					"mention_id": _mention_id(episode_id, topic),
					"episode_id": episode_id,
					"topic": topic,
					"source_text": sachinhalt,
				}
			)

	df = pd.DataFrame(rows)
	if df.empty:
		return pd.DataFrame(columns=TOPIC_MENTION_COLUMNS)
	df = df.drop_duplicates(subset=["episode_id", "topic"]).reset_index(drop=True)
	episode_order = {eid: idx for idx, eid in enumerate(episodes_df["episode_id"].tolist())}
	df["_episode_order"] = df["episode_id"].map(episode_order).fillna(len(episode_order)).astype(int)
	df = df.sort_values(by=["_episode_order", "topic", "mention_id"]).drop(columns=["_episode_order"])
	return df[TOPIC_MENTION_COLUMNS]


def save_topic_mentions(df: pd.DataFrame, output_dir: str | Path | None = None) -> Path:
	out_dir = Path(output_dir) if output_dir else PHASE_DIR
	out_dir.mkdir(parents=True, exist_ok=True)
	out_path = out_dir / FILE_TOPIC_MENTIONS
	df.to_csv(out_path, index=False)
	return out_path
