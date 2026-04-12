from __future__ import annotations

from typing import Any

import pandas as pd

from .contracts import COMMON_BASE_COLUMNS, INPUT_FILES, UNRESOLVED_TIER
from .utils import aliases_from_wikidata_item, description_from_wikidata_item, ensure_columns, label_from_wikidata_item, prefixed_row_values, read_json_dict, stable_id


def build_aligned_topics(normalized: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    zdf_topics = normalized["zdf_topics"].copy()
    wikidata_topics = read_json_dict(INPUT_FILES["wikidata_topics"])
    wikidata_topics_norm = normalized.get("wikidata_topics", pd.DataFrame()).copy()
    wd_norm_by_id = {
        str(row.get("entity_id", "")): row
        for _, row in wikidata_topics_norm.iterrows()
        if str(row.get("entity_id", "")).strip()
    }

    rows: list[dict[str, Any]] = []
    evidence_rows: list[dict[str, Any]] = []

    for _, topic in zdf_topics.iterrows():
        mention_id = str(topic.get("mention_id", ""))
        label = str(topic.get("topic", ""))

        row = {
            "alignment_unit_id": mention_id,
            "wikidata_id": "",
            "fernsehserien_de_id": "",
            "mention_id": mention_id,
            "canonical_label": label,
            "entity_class": "topic",
            "match_confidence": 0.0,
            "match_tier": UNRESOLVED_TIER,
            "match_strategy": "topic_context_only_best_effort",
            "evidence_summary": "No deterministic cross-source topic link in current baseline run",
            "unresolved_reason_code": "no_candidate",
            "unresolved_reason_detail": "No deterministic topic candidate in fernsehserien_de or Wikidata",
            "inference_flag": "false",
            "inference_basis": "",
            "notes": "",
            "label_wikidata": "",
            "label_fernsehserien_de": "",
            "label_zdf": label,
            "description_wikidata": "",
            "description_fernsehserien_de": "",
            "description_zdf": str(topic.get("source_context", "")),
            "alias_wikidata": "",
            "alias_fernsehserien_de": "",
            "alias_zdf": "",
            "episode_id_zdf": str(topic.get("episode_id", "")),
        }
        row.update(prefixed_row_values(topic, suffix="zdf"))

        rows.append(row)
        evidence_rows.append(
            {
                "alignment_unit_id": mention_id,
                "entity_class": "topic",
                "match_strategy": row["match_strategy"],
                "match_tier": row["match_tier"],
                "match_confidence": row["match_confidence"],
                "evidence_summary": row["evidence_summary"],
                "unresolved_reason_code": row["unresolved_reason_code"],
            }
        )

    # Preserve unmatched Wikidata topics as unresolved rows.
    for wd_id, wd_item in sorted(wikidata_topics.items(), key=lambda pair: pair[0]):
        if not isinstance(wd_item, dict):
            continue

        wd_label = label_from_wikidata_item(wd_item)
        row = {
            "alignment_unit_id": stable_id("topic_wd", wd_id),
            "wikidata_id": wd_id,
            "fernsehserien_de_id": "",
            "mention_id": "",
            "canonical_label": wd_label,
            "entity_class": "topic",
            "match_confidence": 0.0,
            "match_tier": UNRESOLVED_TIER,
            "match_strategy": "wikidata_topic_only_baseline",
            "evidence_summary": "Wikidata topic carried forward without deterministic ZDF/fernsehserien_de candidate",
            "unresolved_reason_code": "no_candidate",
            "unresolved_reason_detail": "No deterministic ZDF topic candidate",
            "inference_flag": "false",
            "inference_basis": "",
            "notes": "",
            "label_wikidata": wd_label,
            "label_fernsehserien_de": "",
            "label_zdf": "",
            "description_wikidata": description_from_wikidata_item(wd_item),
            "description_fernsehserien_de": "",
            "description_zdf": "",
            "alias_wikidata": aliases_from_wikidata_item(wd_item),
            "alias_fernsehserien_de": "",
            "alias_zdf": "",
            "episode_id_zdf": "",
        }
        if wd_id in wd_norm_by_id:
            row.update(prefixed_row_values(wd_norm_by_id[wd_id], suffix="wikidata"))
        rows.append(row)
        evidence_rows.append(
            {
                "alignment_unit_id": row["alignment_unit_id"],
                "entity_class": "topic",
                "match_strategy": row["match_strategy"],
                "match_tier": row["match_tier"],
                "match_confidence": row["match_confidence"],
                "evidence_summary": row["evidence_summary"],
                "unresolved_reason_code": row["unresolved_reason_code"],
            }
        )

    aligned = pd.DataFrame(rows)
    aligned = ensure_columns(aligned, COMMON_BASE_COLUMNS + [c for c in aligned.columns if c not in COMMON_BASE_COLUMNS])
    aligned = aligned.sort_values(by=["canonical_label", "alignment_unit_id"]).reset_index(drop=True)
    return aligned, evidence_rows
