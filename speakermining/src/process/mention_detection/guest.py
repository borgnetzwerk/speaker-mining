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


def _normalize_ws(text: str) -> str:
	return " ".join((text or "").replace("\n", " ").split())


def _extract_infos_sections(infos: str) -> list[str]:
	"""Return candidate guest-list sections anchored on host+mit patterns."""
	text = _normalize_ws(infos)
	if not text:
		return []

	anchor_pattern = re.compile(
		r"(?:Interview(?:\s+und\s+Diskussion)?|Diskussion)?\s*Mark\w*\s+LANZ(?:\s*\([^)]+\))?\s+mit",
		flags=re.IGNORECASE,
	)
	matches = list(anchor_pattern.finditer(text))
	if not matches:
		return []

	sections: list[str] = []
	for idx, match in enumerate(matches):
		start = match.start()
		end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
		segment = text[start:end]
		segment = segment[match.end() - start :].strip(" .,;")
		segment = re.split(r"\bThema(?:n)?\s*:\s*", segment, maxsplit=1, flags=re.IGNORECASE)[0]
		segment = re.split(r"\(O-Ton\)", segment, maxsplit=1, flags=re.IGNORECASE)[0]
		segment = segment.strip(" .,;")
		if segment:
			sections.append(segment)

	return sections


_NAME_PATTERN = re.compile(
	r"\b(?:[A-ZÄÖÜ][a-zäöüß]+|[A-ZÄÖÜ]\.)(?:\s+(?:[A-ZÄÖÜ][a-zäöüß]+|[A-ZÄÖÜ]\.))*\s+"
	r"(?:[A-ZÄÖÜ][A-ZÄÖÜß-]+(?:\s+[A-ZÄÖÜ][A-ZÄÖÜß-]+)*|[A-ZÄÖÜ][a-zäöüß]+(?:-[A-ZÄÖÜ][a-zäöüß]+)?)\b"
)


def _clean_name(raw_name: str) -> str:
	name = _normalize_ws(raw_name).strip(" ,.;:")
	name = re.sub(
		r"^(?:den|dem|die|der|des|mit|und|sowie|den\s+Studiogästen|den\s+Studiogast|"
		r"Studiogästen|Studiogäste|Studiogast|Studiogasts|seine|seiner|ihre|ihrer|ihrem)\s+",
		"",
		name,
		flags=re.IGNORECASE,
	)
	name = re.sub(r"^\d{1,2}-j[a-zäöüß]+r(?:e|er|en)?\s+", "", name, flags=re.IGNORECASE)
	return name.strip(" ,.;:")


def _is_plausible_person_name(name: str) -> bool:
	if not name:
		return False
	if any(token in name.lower() for token in ["thema", "themen", "interview", "o-ton", "diskussion"]):
		return False
	parts = name.split()
	if len(parts) < 2:
		return False
	if not any(part.isupper() and len(part) >= 3 for part in parts):
		return False
	return True


def _extract_person_rows_from_infos(episode_id: str, infos: str) -> list[dict[str, str]]:
	rows: list[dict[str, str]] = []
	for section in _extract_infos_sections(infos):
		for m in re.finditer(r"([^)]+?)\(([^)]+)\)", section):
			raw_names = _normalize_ws(m.group(1)).strip(" ,;")
			desc = _normalize_ws(m.group(2))

			candidates = [_clean_name(n) for n in _NAME_PATTERN.findall(raw_names)]
			if not candidates:
				continue

			for name in candidates:
				if not _is_plausible_person_name(name):
					continue
				rows.append(
					{
						"mention_id": _mention_id(episode_id, name, desc),
						"episode_id": episode_id,
						"name": name,
						"beschreibung": desc,
						"source_text": raw_names,
					}
				)

	return rows


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

	# Preferred path: parse normalized infos from extracted episode table.
	if not episodes_df.empty and "infos" in episodes_df.columns:
		for _, row in episodes_df[["episode_id", "infos"]].fillna("").iterrows():
			episode_id = str(row["episode_id"])
			infos = str(row["infos"])
			rows.extend(_extract_person_rows_from_infos(episode_id, infos))
	else:
		# Fallback for legacy callers without infos in episodes_df.
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
	episode_order = {eid: idx for idx, eid in enumerate(episodes_df["episode_id"].tolist())}
	df["_episode_order"] = df["episode_id"].map(episode_order).fillna(len(episode_order)).astype(int)
	df = df.sort_values(by=["_episode_order", "name", "beschreibung", "mention_id"]).drop(columns=["_episode_order"])
	return df[PERSON_MENTION_COLUMNS]


def save_person_mentions(df: pd.DataFrame, output_dir: str | Path | None = None) -> Path:
	out_dir = Path(output_dir) if output_dir else PHASE_DIR
	out_dir.mkdir(parents=True, exist_ok=True)
	out_path = out_dir / FILE_PERSON_MENTIONS
	df.to_csv(out_path, index=False)
	return out_path
