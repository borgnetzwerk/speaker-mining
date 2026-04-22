from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Iterable

import pandas as pd

from .config import FILE_PERSON_MENTIONS, PERSON_MENTION_COLUMNS, PHASE_DIR
from process.io_guardrails import atomic_write_csv


def _extract_sachinhalt(text: str) -> str:
	m = re.search(r"Sachinhalt(.*?)Jugendeignung", text, flags=re.DOTALL | re.IGNORECASE)
	return m.group(1).strip() if m else ""


def _normalize_ws(text: str) -> str:
	return " ".join((text or "").replace("\n", " ").split())


def _extract_infos_sections(infos: str) -> list[str]:
	"""Return candidate guest-list sections from infos text.

	Primary mode uses host+mit anchors.
	Fallback mode is conservative and only activates for Studiogast/Studiogästen cues
	when no primary anchor is found.
	"""
	text = _normalize_ws(infos)
	if not text:
		return []

	anchor_pattern = re.compile(
		r"(?:Interview(?:\s+und\s+Diskussion)?|Diskussion)?\s*Mark\w*\s+LANZ(?:\s*\([^)]+\))?\s+mit",
		flags=re.IGNORECASE,
	)
	matches = list(anchor_pattern.finditer(text))
	if not matches:
		fallback_sections = _extract_studiogast_sections(text)
		return fallback_sections

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


def _extract_studiogast_sections(text: str) -> list[str]:
	"""Conservative fallback extraction for Studiogast/Studiogästen phrasing."""
	cue_pattern = re.compile(
		r"\b(?:den\s+)?(?:Studiogast|Studiogäste|Studiogästen|Studiogasts)\b",
		flags=re.IGNORECASE,
	)

	sections: list[str] = []
	for cue_match in cue_pattern.finditer(text):
		segment = text[cue_match.end() :]
		segment = re.split(r"\b(?:Thema(?:n)?|Schwerpunktthemen?)\s*:", segment, maxsplit=1, flags=re.IGNORECASE)[0]
		segment = re.split(r"\bJugendeignung\b", segment, maxsplit=1, flags=re.IGNORECASE)[0]
		segment = re.split(r"\(O-Ton\)", segment, maxsplit=1, flags=re.IGNORECASE)[0]
		segment = segment.strip(" .,;")

		# Keep fallback strict: only return segments that still contain parenthetical pairs.
		if segment and "(" in segment and ")" in segment:
			sections.append(segment)
			break

	return sections


_NAME_PATTERN = re.compile(
	r"\b(?:[A-ZÄÖÜ][a-zäöüß]+|[A-ZÄÖÜ]\.)(?:\s+(?:[A-ZÄÖÜ][a-zäöüß]+|[A-ZÄÖÜ]\.))*\s+"
	r"(?:[A-ZÄÖÜ][A-ZÄÖÜß-]+(?:\s+[A-ZÄÖÜ][A-ZÄÖÜß-]+)*|[A-ZÄÖÜ][a-zäöüß]+(?:-[A-ZÄÖÜ][a-zäöüß]+)?)\b"
)

_MONONYM_PATTERN = re.compile(r"\b[A-ZÄÖÜ][A-ZÄÖÜß-]{3,}\b")

_SURNAME_PRIMARY_NAME_PATTERN = re.compile(
	r"\b(?:[A-ZÄÖÜ][a-zäöüß]+|[A-ZÄÖÜ]\.)(?:\s+(?:[A-ZÄÖÜ][a-zäöüß]+|[A-ZÄÖÜ]\.))*\s+"
	r"[A-ZÄÖÜ][A-ZÄÖÜß-]+(?:\s+[A-ZÄÖÜ][A-ZÄÖÜß-]+)*\b"
)

_MONONYM_STOPWORDS = {
	"LANZ",
	"OTON",
	"STUDIOGAST",
	"STUDIOGÄSTE",
	"STUDIOGÄSTEN",
	"STUDIOGASTS",
	"THEMEN",
	"THEMA",
	"SCHWERPUNKTTHEMEN",
}

_ABBREV_EXPANSIONS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\behem\.", re.IGNORECASE), "ehemalig"),
    (re.compile(r"\bstellv\.", re.IGNORECASE), "stellvertretend"),
    (re.compile(r"\bVors\."), "Vorsitzende(r)"),
    (re.compile(r"\bVizepräs\."), "Vizepräsident"),
    (re.compile(r"\bPräs\."), "Präsident"),
]


def _expand_abbreviations(text: str) -> str:
    for pattern, replacement in _ABBREV_EXPANSIONS:
        text = pattern.sub(replacement, text)
    return text


_RELATION_CUE_PATTERN = re.compile(
	r"\b(?:ehefrau|ehemann|mutter|vater|tochter|sohn|bruder|schwester|"
	r"zwillingsbruder|freundin|freund|deren|dessen|seine|ihr|ihre|ihrer|ihrem)\b",
	flags=re.IGNORECASE,
)

_GROUP_DESC_PATTERN = re.compile(
	r"\b(?:geschwister|eltern|ehepaar|beide|familie|zwillinge|br[üu]der|schwestern|wettk[öo]nige)\b",
	flags=re.IGNORECASE,
)


def _clean_name(raw_name: str) -> str:
	name = _normalize_ws(raw_name).strip(" ,.;:")
	name = re.sub(r'\s+"[^"]+"\s+', " ", name)
	prefix_pattern = (
		r"^(?:den|dem|die|der|des|mit|und|sowie|den\s+Studiogästen|den\s+Studiogast|"
		r"Studiogästen|Studiogäste|Studiogast|Studiogasts|seine|seiner|ihre|ihrer|ihrem|"
		r"ehefrau|ehemann|mutter|vater|tochter|sohn|bruder|schwester|zwillingsbruder|"
		r"lebensgefährtin|lebensgefährte)\s+"
	)
	while True:
		stripped = re.sub(prefix_pattern, "", name, flags=re.IGNORECASE)
		if stripped == name:
			break
		name = stripped.strip(" ,.;:")
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
	# Check if any part has uppercase letters and is >= 3 chars (handles ß in surnames like THEVEßEN)
	if not any(any(c.isupper() for c in part) and len(part) >= 3 for part in parts):
		return False
	return True


def _is_plausible_mononym(name: str) -> bool:
	token = (name or "").strip().upper()
	if not token or token in _MONONYM_STOPWORDS:
		return False
	if len(token) < 4:
		return False
	if "THEMA" in token:
		return False
	return token.isupper()


def _is_group_description(desc: str) -> bool:
	return bool(_GROUP_DESC_PATTERN.search(desc or ""))


def _candidate_names_with_spans(raw_names: str) -> list[tuple[str, int, int, str]]:
	items: list[tuple[str, int, int, str]] = []
	for m in _NAME_PATTERN.finditer(raw_names):
		name = _clean_name(m.group(0))
		if not _is_plausible_person_name(name):
			continue
		items.append((name, m.start(), m.end(), "surname_name"))

	if items:
		return items

	for m in _MONONYM_PATTERN.finditer(raw_names):
		name = _clean_name(m.group(0))
		if not _is_plausible_mononym(name):
			continue
		items.append((name, m.start(), m.end(), "mononym"))

	return items


def _rule_rows_for_block(
	episode_id: str,
	raw_names: str,
	desc: str,
	block_text: str,
	section: str,
) -> list[dict[str, str]]:
	desc = _expand_abbreviations(desc)
	candidates = _candidate_names_with_spans(raw_names)
	if not candidates:
		return []

	rows: list[dict[str, str]] = []
	group_desc = _is_group_description(desc)
	multi = len(candidates) > 1

	prev_end = 0
	for idx, (name, start, _end, name_kind) in enumerate(candidates):
		is_last = idx == len(candidates) - 1
		# Check only the inter-name segment (from previous name's end to this name's start)
		# to avoid spill-over of relation cues from earlier names in a chain.
		inter_segment = raw_names[prev_end:start]
		has_relation_cue = bool(_RELATION_CUE_PATTERN.search(inter_segment))
		prev_end = _end

		beschreibung = ""
		parsing_rule = "single_parenthetical"
		confidence = 0.95
		confidence_note = "single name directly tied to parenthetical description"

		if name_kind == "mononym":
			parsing_rule = "single_parenthetical_mononym"
			confidence = 0.62
			confidence_note = "single-token stage or artist name tied to parenthetical description"

		if not multi:
			beschreibung = desc
		else:
			if group_desc:
				beschreibung = desc
				parsing_rule = "group_parenthetical"
				confidence = 0.70
				confidence_note = "group-style description assigned to all names in chain"
			elif is_last:
				beschreibung = desc
				parsing_rule = "last_name_parenthetical"
				confidence = 0.82
				confidence_note = "description assigned to nearest name before parenthetical"
			else:
				beschreibung = ""
				parsing_rule = "name_without_local_parenthetical"
				confidence = 0.45 if has_relation_cue else 0.55
				confidence_note = "name appears in multi-name chain; description withheld to avoid misattribution"

		mention_category = "incidental" if has_relation_cue else "guest"

		rows.append(
			{
				"mention_id": _mention_id(episode_id, name, beschreibung),
				"episode_id": episode_id,
				"name": name,
				"mention_category": mention_category,
				"beschreibung": beschreibung,
				"source_text": block_text,
				"source_context": section,
				"parsing_rule": parsing_rule,
				"confidence": f"{confidence:.2f}",
				"confidence_note": confidence_note,
			}
		)

	return rows


def _trim_section_tail(segment: str) -> str:
	segment = re.split(r"\bThema(?:n)?\s*:\s*", segment, maxsplit=1, flags=re.IGNORECASE)[0]
	segment = re.split(r"\bSchwerpunktthemen?\s*:\s*", segment, maxsplit=1, flags=re.IGNORECASE)[0]
	segment = re.split(r"\(O-Ton\)", segment, maxsplit=1, flags=re.IGNORECASE)[0]
	return segment.strip(" .,;")


def _strip_leading_timecodes(text: str) -> str:
	return re.sub(
		r"^\d{1,2}:\d{2}:\d{2}\s*-\s*\d{1,2}:\d{2}:\d{2}\s+\d{2,3}'\d{2}\s+",
		"",
		text,
	)


def _extract_opening_guest_sections(text: str) -> list[str]:
	sections: list[str] = []
	opening = _strip_leading_timecodes(text)

	opening_patterns = [
		r"^(?:O-Ton\s+)?(?:Interview(?:\s+und\s+Diskussion)?\s+)?(?:Mark\w*\s+)?LANZ(?:\s*\([^)]+\))?\s+mit\s+",
		r"^(?:O-Ton\s+)?Interview(?:\s+und\s+Diskussion)?\s+",
		r"^(?:O-Ton\s+)?(?:den\s+)?Studiogästen?\s+",
		r"^(?:O-Ton\s+)?(?:dem\s+)?Studiogast\s+",
	]
	for pattern in opening_patterns:
		m = re.match(pattern, opening, flags=re.IGNORECASE)
		if not m:
			continue
		segment = opening[m.end() :].strip(" .,;")
		segment = _trim_section_tail(segment)
		if segment:
			sections.append(segment)
			return sections

	# Last-resort fallback: preserve precision by requiring surname-style names plus parenthetical descriptors.
	if _SURNAME_PRIMARY_NAME_PATTERN.search(opening) and re.search(r"\([^)]+\)", opening):
		segment = _trim_section_tail(opening)
		if segment:
			sections.append(segment)

	return sections


def _extract_surname_fallback_rows(episode_id: str, section: str) -> list[dict[str, str]]:
	lead = _strip_leading_timecodes(section)
	lead = re.split(r"\s+über\s+", lead, maxsplit=1, flags=re.IGNORECASE)[0]
	lead = lead.split(";", 1)[0].strip(" .,;")

	candidates = [_clean_name(m.group(0)) for m in _SURNAME_PRIMARY_NAME_PATTERN.finditer(lead)]
	if not candidates:
		return []

	# Keep first occurrence order and avoid duplicate rows for repeated names.
	seen: set[str] = set()
	rows: list[dict[str, str]] = []
	for name in candidates:
		if not _is_plausible_person_name(name) or name in seen:
			continue
		seen.add(name)
		rows.append(
			{
				"mention_id": _mention_id(episode_id, name, ""),
				"episode_id": episode_id,
				"name": name,
				"mention_category": "guest",
				"beschreibung": "",
				"source_text": lead,
				"source_context": section,
				"parsing_rule": "surname_primary_no_parenthetical",
				"confidence": "0.68",
				"confidence_note": "name identified via uppercase surname pattern without local descriptor",
			}
		)

	return rows


def _extract_person_rows_from_infos(episode_id: str, infos: str) -> list[dict[str, str]]:
	rows: list[dict[str, str]] = []
	sections = _extract_infos_sections(infos)
	if not sections:
		sections = _extract_opening_guest_sections(_normalize_ws(infos))

	for section in sections:
		section_rows: list[dict[str, str]] = []
		for m in re.finditer(r"([^)]+?)\(([^)]+)\)", section):
			raw_names = _normalize_ws(m.group(1)).strip(" ,;")
			desc = _normalize_ws(m.group(2))
			block_text = f"{raw_names} ({desc})"
			section_rows.extend(_rule_rows_for_block(episode_id, raw_names, desc, block_text, section))

		if not section_rows:
			section_rows.extend(_extract_surname_fallback_rows(episode_id, section))

		rows.extend(section_rows)

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
							"mention_category": "guest",
							"beschreibung": desc,
							"source_text": f"{raw_names} ({desc})",
							"source_context": sachinhalt,
							"parsing_rule": "legacy_sachinhalt_fallback",
							"confidence": "0.50",
							"confidence_note": "legacy fallback extraction path",
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
	atomic_write_csv(out_path, df, index=False)
	return out_path
