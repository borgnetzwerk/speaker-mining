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


def _normalize_ws(text: str) -> str:
	return " ".join((text or "").replace("\n", " ").split())


def _extract_infos_sections(infos: str) -> list[str]:
	"""Return candidate interview sections from normalized infos text."""
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
		segment = text[start:end].strip(" .,;")
		segment = re.split(r"\(O-Ton\)", segment, maxsplit=1, flags=re.IGNORECASE)[0]
		segment = segment.strip(" .,;")
		if segment:
			sections.append(segment)

	return sections


_BAD_TOPIC_PREFIX_PATTERN = re.compile(
	r"^(?:\d{1,2}:\d{2}:\d{2}\s*-\s*\d{1,2}:\d{2}:\d{2}\s+\d{2,3}'\d{2}\s+)?"
	r"(?:Interview(?:\s+und\s+Diskussion)?|Diskussion)\b",
	flags=re.IGNORECASE,
)


def _normalize_topic(candidate: str) -> str:
	topic = _normalize_ws(candidate)
	if not topic:
		return ""

	topic = re.sub(r"\(O-Ton\)\.?$", "", topic, flags=re.IGNORECASE).strip(" .,;:-")
	topic = re.sub(r"^über\s+die\s+Schwerpunktthemen\s*:??\s*", "", topic, flags=re.IGNORECASE)
	topic = re.sub(r"^über\s+die\s+Themen\s*:??\s*", "", topic, flags=re.IGNORECASE)
	topic = re.sub(r"^(?:Themen?|Schwerpunktthemen?)\s*:\s*", "", topic, flags=re.IGNORECASE)
	topic = re.sub(r"^(?:Themen?|Schwerpunktthemen?)\s+", "", topic, flags=re.IGNORECASE)
	topic = re.sub(r"^Thema\s*:\s*", "", topic, flags=re.IGNORECASE)
	topic = re.sub(r"^über\s+(?:den|die|das|dem|der|ein|eine|einen|einem|einer)\s+", "", topic, flags=re.IGNORECASE)
	topic = re.sub(r"^über\s+", "", topic, flags=re.IGNORECASE)
	topic = re.sub(r"^zu(?:m|r)?\s+", "", topic, flags=re.IGNORECASE)
	topic = re.sub(r"\s+u\.a\.\s*", " ", topic, flags=re.IGNORECASE)
	topic = topic.strip(" .,;:-")

	if _BAD_TOPIC_PREFIX_PATTERN.search(topic):
		return ""
	if "studiogäst" in topic.lower():
		return ""
	if 4 <= len(topic) <= 220:
		return topic
	return ""


def _assess_comma_ambiguity(part: str, section_text: str) -> tuple[float, str]:
	"""
	Assess confidence for comma-splitting within a topic part.
	
	Commas in German are ambiguous: they can separate distinct topics OR introduce
	relative clauses and embedded descriptions. This function detects ambiguity markers
	to adjust confidence downward when comma-splitting is risky.
	
	Args:
		part: The text part potentially containing comma-separated topics
		section_text: Full section for context analysis
	
	Returns:
		(confidence_adjustment_factor, ambiguity_explanation)
	"""
	if "," not in part:
		return (1.0, "")

	# Check for relative clause markers: comma followed by relative pronouns (lowercase typically triggers)
	relative_pattern = re.compile(
		r",\s+(?:den|die|das|dem|der|denen|deren|deshalb|daher|dazu|das\s+zu|welche|welcher|welches|wovon|womit|worauf)",
		flags=re.IGNORECASE
	)
	if relative_pattern.search(section_text):
		return (0.60, "section contains relative clause markers after commas (e.g., 'den', 'die'); comma reliability severely compromised")

	# Check for lowercase word after comma (often signals relative clause continuation)
	lowercase_after_comma = re.findall(r",\s+[a-zäöü]", part)
	if lowercase_after_comma:
		return (0.70, "lowercase text follows commas; likely relative clauses or embedded clauses; comma-split ambiguity high")

	# Count capitalized starts after commas (suggests new topics)
	comma_splits = part.split(",")
	capitalized_continuations = sum(
		1 for s in comma_splits[1:] if s.strip() and s.strip()[0].isupper()
	)
	
	if len(comma_splits) > 1:
		capital_ratio = capitalized_continuations / (len(comma_splits) - 1)
		if capital_ratio < 0.5:
			return (0.65, "only some comma-separated parts start with capitals; mixed capitalization suggests ambiguity")
		elif capital_ratio >= 0.8:
			return (0.82, "most comma-separated parts start with capitals; higher confidence that commas separate topics")

	return (0.75, "comma-splitting ambiguity present; commas may introduce embedded descriptions rather than separating topics")


def _topic_rows_from_section(episode_id: str, section: str) -> list[dict[str, str]]:
	rows: list[dict[str, str]] = []
	section_text = _normalize_ws(section)
	if not section_text:
		return rows

	candidates: list[tuple[str, str, float, str]] = []
	label_match = re.search(
		r"\b(?:über\s+die\s+)?(?:Themen?|Schwerpunktthemen?)\s*:??\s*",
		section_text,
		flags=re.IGNORECASE,
	)
	if label_match:
		trailing = section_text[label_match.end() :]
		trailing = re.split(r"\s+[A-ZÄÖÜ][a-zäöüß]+\s+LANZ\b", trailing, maxsplit=1, flags=re.IGNORECASE)[0]
		parts = [part.strip() for part in trailing.split(";") if part.strip()]
		
		# Special handling: if there's only one semicolon-part with trailing commas,
		# and it looks like an inline comma-separated list, split by comma with lower confidence
		if len(parts) == 1 and parts[0].count(",") >= 1:
			comma_confidence, comma_note = _assess_comma_ambiguity(parts[0], section_text)
			adjusted_confidence = 0.88 * comma_confidence  # Base 0.88 adjusted by ambiguity factor
			comma_parts = [part.strip() for part in parts[0].split(",") if part.strip()]
			for part in comma_parts:
				candidates.append(
					(
						part,
						"inline_label_comma_split",
						adjusted_confidence,
						f"topic from inline Themen/Schwerpunktthemen list split by comma; {comma_note}",
					)
				)
		else:
			# Multiple semicolon-separated parts: process each, checking for internal commas
			for part in parts:
				if "," in part:
					# This semicolon-part contains commas: assess whether to split by comma
					comma_confidence, comma_note = _assess_comma_ambiguity(part, section_text)
					
					# Only split by comma if confidence > 0.70 (threshold for reliable splitting)
					if comma_confidence > 0.70:
						comma_parts = [cp.strip() for cp in part.split(",") if cp.strip()]
						base_conf = 0.93 * comma_confidence  # Adjust the base semicolon confidence
						for cp in comma_parts:
							candidates.append(
								(
									cp,
									"semicolon_part_comma_split",
									base_conf,
									f"topic from semicolon-separated part further split by comma; {comma_note}",
								)
							)
					else:
						# Comma-split too risky; treat whole part as a single topic with lower confidence
						adjusted_conf = 0.93 * comma_confidence
						candidates.append(
							(
								part,
								"labelled_topic_list_with_commas",
								adjusted_conf,
								f"topic contains commas but splitting rejected due to ambiguity; {comma_note}",
							)
						)
				else:
					# No commas in this part: standard semicolon-separated topic
					candidates.append(
						(
							part,
							"labelled_topic_list",
							0.93,
							"topic from explicit Thema/Themen/Schwerpunktthemen segment",
						)
					)
	else:
		parts = [part.strip() for part in section_text.split(";") if part.strip()]
		for part in parts:
			cue = re.search(r"\b(?:über|zu(?:m|r)?)\b", part, flags=re.IGNORECASE)
			if cue:
				candidates.append(
					(
						part[cue.start() :].strip(),
						"cue_based_clause",
						0.72,
						"topic inferred from über/zu cue in semicolon clause",
					)
				)

	seen: set[str] = set()
	for candidate, parsing_rule, confidence, confidence_note in candidates:
		normalized = _normalize_topic(candidate)
		if not normalized or normalized in seen:
			continue
		seen.add(normalized)
		rows.append(
			{
				"mention_id": _mention_id(episode_id, normalized),
				"episode_id": episode_id,
				"topic": normalized,
				"source_text": candidate,
				"source_context": section_text,
				"parsing_rule": parsing_rule,
				"confidence": f"{confidence:.2f}",
				"confidence_note": confidence_note,
			}
		)

	return rows


def _mention_id(episode_id: str, topic: str) -> str:
	raw = f"{episode_id}|{topic}".encode("utf-8")
	return f"tm_{hashlib.sha1(raw).hexdigest()[:12]}"


def extract_topic_mentions(episode_blocks: Iterable[str], episodes_df: pd.DataFrame) -> pd.DataFrame:
	rows: list[dict[str, str]] = []

	# Preferred path: parse normalized infos from extracted episode table.
	if not episodes_df.empty and "infos" in episodes_df.columns:
		for _, row in episodes_df[["episode_id", "infos"]].fillna("").iterrows():
			episode_id = str(row["episode_id"])
			infos = str(row["infos"])
			for section in _extract_infos_sections(infos):
				rows.extend(_topic_rows_from_section(episode_id, section))
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

			for topic in _topic_rows_from_section(episode_id, sachinhalt):
				rows.append(topic)

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
