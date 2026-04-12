from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"\s+", " ", text)
    return text


def safe_column_name(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"[^0-9A-Za-z_()]", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text


def stable_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(str(p) for p in parts).encode("utf-8")
    digest = hashlib.sha1(raw).hexdigest()[:12]
    return f"{prefix}_{digest}"


def parse_date(value: Any) -> pd.Timestamp:
    text = str(value or "").strip()
    if not text:
        return pd.NaT
    for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            return pd.Timestamp(datetime.strptime(text, fmt).date())
        except ValueError:
            continue
    return pd.to_datetime(text, errors="coerce")


def read_json_dict(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        return data
    return {}


def label_from_wikidata_item(item: dict[str, Any]) -> str:
    labels = item.get("labels", {}) or {}
    for key in ("de", "en", "mul"):
        node = labels.get(key)
        if isinstance(node, dict):
            value = node.get("value")
            if value:
                return str(value)
    return ""


def description_from_wikidata_item(item: dict[str, Any]) -> str:
    descriptions = item.get("descriptions", {}) or {}
    for key in ("de", "en", "mul"):
        node = descriptions.get(key)
        if isinstance(node, dict):
            value = node.get("value")
            if value:
                return str(value)
    return ""


def aliases_from_wikidata_item(item: dict[str, Any]) -> str:
    aliases = item.get("aliases", {}) or {}
    values: list[str] = []
    for lang_nodes in aliases.values():
        if not isinstance(lang_nodes, list):
            continue
        for alias_node in lang_nodes:
            if isinstance(alias_node, dict) and alias_node.get("value"):
                values.append(str(alias_node["value"]))
    # Keep deterministic order and uniqueness.
    unique = sorted({v.strip() for v in values if v.strip()})
    return "|".join(unique)


def ensure_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    out = df.copy()
    for column in columns:
        if column not in out.columns:
            out[column] = ""
    return out[columns]


def first_non_empty(values: list[Any]) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def prefixed_row_values(
    row: dict[str, Any] | pd.Series,
    *,
    suffix: str,
    exclude: set[str] | None = None,
) -> dict[str, str]:
    excluded = exclude or set()
    out: dict[str, str] = {}
    if isinstance(row, pd.Series):
        items = row.to_dict().items()
    else:
        items = row.items()

    for key, value in items:
        if key in excluded:
            continue
        out[f"{key}_{suffix}"] = str(value or "")
    return out
