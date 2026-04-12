from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from process.io_guardrails import atomic_write_csv

from .contracts import INPUT_FILES, NORMALIZED_DIR
from .utils import (
    aliases_from_wikidata_item,
    description_from_wikidata_item,
    label_from_wikidata_item,
    normalize_text,
    parse_date,
    read_json_dict,
    safe_column_name,
)


def _normalize_csv(path: Path, date_columns: list[str]) -> pd.DataFrame:
    df = pd.read_csv(path, dtype=str).fillna("")
    for col in df.columns:
        df[f"{col}_norm"] = df[col].map(normalize_text)
    for date_col in date_columns:
        if date_col in df.columns:
            df[f"{date_col}_date"] = df[date_col].map(parse_date)
    return df


def _normalize_json_entities(path: Path) -> pd.DataFrame:
    entities = read_json_dict(path)
    property_lookup: dict[str, str] = {}
    properties_path = INPUT_FILES.get("wikidata_properties")
    if properties_path is not None and properties_path.exists():
        properties_df = pd.read_csv(properties_path, dtype=str).fillna("")
        for _, prop_row in properties_df.iterrows():
            pid = str(prop_row.get("id", "")).strip()
            if not pid:
                continue
            label = str(prop_row.get("label_en", "")).strip() or str(prop_row.get("label_de", "")).strip()
            property_lookup[pid] = label

    def _snak_value_to_text(snak: dict[str, Any]) -> str:
        datavalue = snak.get("datavalue", {}) or {}
        value = datavalue.get("value", "")
        if isinstance(value, dict):
            if "id" in value:
                return str(value.get("id", ""))
            if "text" in value:
                return str(value.get("text", ""))
            if "time" in value:
                return str(value.get("time", ""))
            if "amount" in value:
                unit = str(value.get("unit", ""))
                amount = str(value.get("amount", ""))
                return f"{amount}|{unit}" if unit else amount
            return json.dumps(value, ensure_ascii=True, sort_keys=True)
        if isinstance(value, list):
            return "|".join(str(v) for v in value)
        return str(value or "")

    entity_claim_values: dict[str, dict[str, list[str]]] = {}
    max_values_per_pid: dict[str, int] = {}

    for entity_id, item in sorted(entities.items(), key=lambda pair: pair[0]):
        if not isinstance(item, dict):
            continue
        claims = item.get("claims", {}) or {}
        claim_values: dict[str, list[str]] = {}
        if isinstance(claims, dict):
            for pid, statements in claims.items():
                values: list[str] = []
                if isinstance(statements, list):
                    for statement in statements:
                        if not isinstance(statement, dict):
                            continue
                        mainsnak = statement.get("mainsnak", {}) or {}
                        if not isinstance(mainsnak, dict):
                            continue
                        value_text = _snak_value_to_text(mainsnak).strip()
                        if value_text:
                            values.append(value_text)
                if values:
                    claim_values[pid] = values
                    max_values_per_pid[pid] = max(max_values_per_pid.get(pid, 0), len(values))
        entity_claim_values[str(entity_id)] = claim_values

    pid_column_specs: list[tuple[str, str, int]] = []
    for pid in sorted(max_values_per_pid.keys()):
        label = property_lookup.get(pid, "").strip()
        base = f"{label}_({pid})" if label else pid
        base = safe_column_name(base) or pid
        pid_column_specs.append((pid, base, max_values_per_pid[pid]))

    rows: list[dict[str, Any]] = []

    for entity_id, item in sorted(entities.items(), key=lambda pair: pair[0]):
        if not isinstance(item, dict):
            continue

        claim_values = entity_claim_values.get(str(entity_id), {})
        rows.append(
            {
                "entity_id": str(entity_id),
                "entity_type": str(item.get("type", "")),
                "label": label_from_wikidata_item(item),
                "description": description_from_wikidata_item(item),
                "aliases": aliases_from_wikidata_item(item),
                "claim_property_count": int(len(claim_values)),
                "raw_json": json.dumps(item, ensure_ascii=True, sort_keys=True),
            }
        )

        row = rows[-1]
        for pid, col_base, max_count in pid_column_specs:
            values = claim_values.get(pid, [])
            for idx in range(1, max_count + 1):
                col_name = f"{col_base}_{idx}" if max_count > 1 else col_base
                row[col_name] = values[idx - 1] if idx - 1 < len(values) else ""

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    for col in df.columns:
        if col == "raw_json":
            continue
        df[f"{col}_norm"] = df[col].map(normalize_text)
    return df


def normalize_inputs() -> dict[str, pd.DataFrame]:
    NORMALIZED_DIR.mkdir(parents=True, exist_ok=True)

    normalized: dict[str, pd.DataFrame] = {}
    csv_inputs: dict[str, tuple[str, list[str]]] = {
        "setup_broadcasting_programs": ("setup_broadcasting_programs_normalized.csv", []),
        "zdf_episodes": ("episodes_normalized.csv", ["publikationsdatum"]),
        "zdf_persons": ("persons_normalized.csv", []),
        "zdf_topics": ("topics_normalized.csv", []),
        "zdf_publications": ("publications_normalized.csv", ["date"]),
        "zdf_seasons": ("seasons_normalized.csv", ["start_time", "end_time"]),
        "fs_episode_metadata": ("fs_episode_metadata_normalized.csv", ["premiere_date"]),
        "fs_episode_broadcasts": ("fs_episode_broadcasts_normalized.csv", ["broadcast_date", "broadcast_end_date"]),
        "fs_episode_guests": ("fs_episode_guests_normalized.csv", []),
    }

    for key, (target_name, date_columns) in csv_inputs.items():
        df = _normalize_csv(INPUT_FILES[key], date_columns)
        atomic_write_csv(NORMALIZED_DIR / target_name, df, index=False)
        normalized[key] = df

    json_inputs: dict[str, str] = {
        "wikidata_programs": "wikidata_programs_normalized.csv",
        "wikidata_series": "wikidata_series_normalized.csv",
        "wikidata_episodes": "wikidata_episodes_normalized.csv",
        "wikidata_persons": "wikidata_persons_normalized.csv",
        "wikidata_topics": "wikidata_topics_normalized.csv",
        "wikidata_roles": "wikidata_roles_normalized.csv",
        "wikidata_organizations": "wikidata_organizations_normalized.csv",
    }

    for key, target_name in json_inputs.items():
        df = _normalize_json_entities(INPUT_FILES[key])
        atomic_write_csv(NORMALIZED_DIR / target_name, df, index=False)
        normalized[key] = df

    return normalized
