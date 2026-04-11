from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from .normalization import (
    extract_label_and_date_from_parenthetical,
    normalize_name,
    normalize_program_name,
    parse_date_to_iso,
    parse_duration_to_seconds,
)


def read_csv_if_exists(path: Path) -> pd.DataFrame:
    """Read a CSV file if it exists, otherwise return empty DataFrame.
    
    Args:
        path: Path to CSV file
    
    Returns:
        DataFrame with CSV contents, or empty DataFrame if file doesn't exist
    """
    if path.exists():
        return pd.read_csv(path)
    return pd.DataFrame()


def read_json_object_if_exists(path: Path) -> dict[str, Any]:
    """Read a JSON object from file if it exists, otherwise return empty dict.
    
    Args:
        path: Path to JSON file
    
    Returns:
        Dictionary with JSON contents, or empty dict if file doesn't exist or is not a dict
    """
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if isinstance(payload, dict):
        return payload
    return {}


def _pick_label(entity: dict[str, Any]) -> tuple[str, str, str]:
    labels = entity.get("labels", {}) or {}
    label_de = ((labels.get("de") or {}).get("value") or "").strip()
    label_en = ((labels.get("en") or {}).get("value") or "").strip()
    label_mul = ((labels.get("mul") or {}).get("value") or "").strip()
    primary = label_de or label_en or label_mul
    return primary, label_de, label_en


def _aliases(entity: dict[str, Any]) -> list[str]:
    aliases_obj = entity.get("aliases", {}) or {}
    values: list[str] = []
    for items in aliases_obj.values():
        if not isinstance(items, list):
            continue
        for item in items:
            val = str((item or {}).get("value", "")).strip()
            if val:
                values.append(val)
    seen: set[str] = set()
    out: list[str] = []
    for v in values:
        key = normalize_name(v)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(v)
    return out


def _claim_statements(entity: dict[str, Any], pid: str) -> list[dict[str, Any]]:
    claims = entity.get("claims", {}) or {}
    items = claims.get(pid, [])
    if isinstance(items, list):
        return [x for x in items if isinstance(x, dict)]
    return []


def _extract_entity_id_from_snak(statement: dict[str, Any]) -> Optional[str]:
    mainsnak = statement.get("mainsnak", {}) or {}
    datavalue = mainsnak.get("datavalue", {}) or {}
    value = datavalue.get("value", {}) or {}
    if isinstance(value, dict):
        entity_id = str(value.get("id", "")).strip()
        if entity_id:
            return entity_id
    return None


def _extract_time_from_snak(statement: dict[str, Any]) -> str:
    mainsnak = statement.get("mainsnak", {}) or {}
    datavalue = mainsnak.get("datavalue", {}) or {}
    value = datavalue.get("value", {}) or {}
    raw_time = str((value or {}).get("time", "")).strip()
    if not raw_time:
        return ""
    cleaned = raw_time.lstrip("+")
    if "T" in cleaned:
        cleaned = cleaned.split("T", 1)[0]
    return parse_date_to_iso(cleaned)


def _extract_p2699_urls_from_p1343(entity: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for statement in _claim_statements(entity, "P1343"):
        qualifiers = statement.get("qualifiers", {}) or {}
        p2699 = qualifiers.get("P2699", [])
        if not isinstance(p2699, list):
            continue
        for q in p2699:
            datavalue = (q or {}).get("datavalue", {}) or {}
            value = str(datavalue.get("value", "")).strip()
            if value:
                values.append(value)
    return values


def _claim_property_profile(entity: dict[str, Any]) -> dict[str, str]:
    claims = entity.get("claims", {}) or {}
    if not isinstance(claims, dict):
        claims = {}

    property_counts: dict[str, int] = {}
    property_ids: list[str] = []
    statement_count = 0
    for pid, statements in claims.items():
        if not isinstance(statements, list):
            continue
        count = len(statements)
        property_counts[str(pid)] = count
        property_ids.append(str(pid))
        statement_count += count

    property_ids = sorted(set(property_ids))

    def entity_qids_for(pid: str) -> str:
        qids = [_extract_entity_id_from_snak(s) for s in _claim_statements(entity, pid)]
        qids = [q for q in qids if q]
        return "|".join(sorted(set(qids)))

    return {
        "wikidata_claim_properties": "|".join(property_ids),
        "wikidata_claim_property_count": str(len(property_ids)),
        "wikidata_claim_statement_count": str(statement_count),
        "wikidata_property_counts_json": json.dumps(property_counts, ensure_ascii=False, sort_keys=True),
        "wikidata_p31_qids": entity_qids_for("P31"),
        "wikidata_p179_qids": entity_qids_for("P179"),
        "wikidata_p106_qids": entity_qids_for("P106"),
        "wikidata_p39_qids": entity_qids_for("P39"),
        "wikidata_p921_qids": entity_qids_for("P921"),
        "wikidata_p527_qids": entity_qids_for("P527"),
        "wikidata_p361_qids": entity_qids_for("P361"),
    }


def load_wikidata_entities_df(json_path: Path) -> pd.DataFrame:
    """Load Wikidata entities from JSON projection into normalized DataFrame.
    
    Extracts labels, descriptions, aliases, relationships, and metadata for deterministic matching.
    
    Args:
        json_path: Path to Wikidata JSON projection file (e.g., instances_core_episodes.json, instances_core_persons.json)
    
    Returns:
        DataFrame with columns:
        - id: Q-identifier
        - label: Primary label (German, English, or multilingual)
        - label_de/label_en: Language-specific labels
        - description_de/description_en: Descriptions
        - aliases: Pipe-separated list of aliases
        - part_of_qids: Pipe-separated Q-IDs of parent entities (P179)
        - broadcast_date: ISO date from P577 or P580
        - program_from_label: Extracted program name from parenthetical label
        - program_norm: Normalized program name
        - fs_urls: Pipe-separated Wikidata P1343+P2699 URLs (Fernsehserien links)
    
    Examples:
        >>> df = load_wikidata_entities_df(Path("instances_core_episodes.json"))
        >>> len(df) # Number of episodes in projection
        1500
        >>> df[["id", "label", "broadcast_date"]].head()
    """
    payload = read_json_object_if_exists(json_path)
    rows: list[dict[str, Any]] = []
    for qid, entity in payload.items():
        if not isinstance(entity, dict):
            continue
        primary, label_de, label_en = _pick_label(entity)
        desc = entity.get("descriptions", {}) or {}
        description_de = str((desc.get("de") or {}).get("value", "")).strip()
        description_en = str((desc.get("en") or {}).get("value", "")).strip()
        part_of = [_extract_entity_id_from_snak(s) for s in _claim_statements(entity, "P179")]
        part_of = [x for x in part_of if x]
        start_time = ""
        for pid in ("P577", "P580"):
            for statement in _claim_statements(entity, pid):
                maybe_time = _extract_time_from_snak(statement)
                if maybe_time:
                    start_time = maybe_time
                    break
            if start_time:
                break
        program_from_label, date_from_label = extract_label_and_date_from_parenthetical(primary)
        claim_profile = _claim_property_profile(entity)
        rows.append(
            {
                "id": str(entity.get("id", qid)).strip() or str(qid),
                "label": primary,
                "label_de": label_de,
                "label_en": label_en,
                "description_de": description_de,
                "description_en": description_en,
                "aliases": "|".join(_aliases(entity)),
                "part_of_qids": "|".join(part_of),
                "broadcast_date": start_time or date_from_label,
                "program_from_label": program_from_label,
                "program_norm": normalize_program_name(program_from_label),
                "fs_urls": "|".join(_extract_p2699_urls_from_p1343(entity)),
                **claim_profile,
            }
        )

    if not rows:
        return pd.DataFrame(
            columns=[
                "id",
                "label",
                "label_de",
                "label_en",
                "description_de",
                "description_en",
                "aliases",
                "part_of_qids",
                "broadcast_date",
                "program_from_label",
                "program_norm",
                "fs_urls",
                "wikidata_claim_properties",
                "wikidata_claim_property_count",
                "wikidata_claim_statement_count",
                "wikidata_property_counts_json",
                "wikidata_p31_qids",
                "wikidata_p179_qids",
                "wikidata_p106_qids",
                "wikidata_p39_qids",
                "wikidata_p921_qids",
                "wikidata_p527_qids",
                "wikidata_p361_qids",
            ]
        )
    return pd.DataFrame(rows)


def normalize_zdf_episodes_df(df: pd.DataFrame, publications_df: pd.DataFrame) -> pd.DataFrame:
    """Join and normalize ZDF episodes with publication metadata.
    
    Merges episode metadata with publication signals (date, time, duration, program).
    Pre-normalizes fields for deterministic cross-source matching.
    
    Args:
        df: Episodes DataFrame from Phase 10 (episodes.csv)
        publications_df: Publications DataFrame from Phase 10 (publications.csv)
    
    Returns:
        Normalized DataFrame with columns:
        - episode_id: Unique episode identifier
        - program_name: Broadcasting program title
        - program_norm: Normalized program name
        - publication_date: ISO date of broadcast
        - publication_time: Broadcast start time
        - duration_seconds: Duration in seconds
        - season_number: Season number (may be None)
        - episode_number: Episode number within season (may be None)
        - date_iso: ISO date for deterministic comparison
    
    Examples:
        >>> norm_episodes = normalize_zdf_episodes_df(episodes_df, publications_df)
        >>> norm_episodes[["episode_id", "program_norm", "date_iso"]].head()
    """
    if df.empty:
        return pd.DataFrame(columns=["episode_id", "program_name", "program_norm", "publication_date", "publication_time", "duration_seconds", "season_number", "episode_number", "date_iso"])

    work = df.copy()
    work["episode_id"] = work.get("episode_id", "").astype(str)

    pub_first: dict[str, dict[str, str]] = {}
    if not publications_df.empty and "episode_id" in publications_df.columns:
        pub = publications_df.copy()
        pub["episode_id"] = pub["episode_id"].astype(str)
        if "publication_index" in pub.columns:
            pub = pub.sort_values(by=["publication_index"])
        for _, row in pub.iterrows():
            episode_id = str(row.get("episode_id", "")).strip()
            if not episode_id or episode_id in pub_first:
                continue
            pub_first[episode_id] = {
                "date": str(row.get("date", "")).strip(),
                "time": str(row.get("time", "")).strip(),
                "duration": str(row.get("duration", "")).strip(),
                "program": str(row.get("program", "")).strip(),
            }

    rows: list[dict[str, Any]] = []
    for _, row in work.iterrows():
        episode_id = str(row.get("episode_id", "")).strip()
        if not episode_id:
            continue
        publication_date = str(row.get("publikationsdatum", "")).strip()
        publication_time = ""
        duration_raw = str(row.get("dauer", "")).strip()
        program_name = str(row.get("sendungstitel", "")).strip()
        if episode_id in pub_first:
            publication_date = publication_date or pub_first[episode_id]["date"]
            publication_time = pub_first[episode_id]["time"]
            duration_raw = duration_raw or pub_first[episode_id]["duration"]
            program_name = program_name or pub_first[episode_id]["program"]
        rows.append(
            {
                "episode_id": episode_id,
                "program_name": program_name,
                "program_norm": normalize_program_name(program_name),
                "publication_date": publication_date,
                "publication_time": publication_time,
                "duration_seconds": parse_duration_to_seconds(duration_raw),
                "season_number": str(row.get("staffel", row.get("season", ""))).strip(),
                "episode_number": str(row.get("folge", row.get("folgennr", ""))).strip(),
                "date_iso": parse_date_to_iso(publication_date),
            }
        )

    return pd.DataFrame(rows)
