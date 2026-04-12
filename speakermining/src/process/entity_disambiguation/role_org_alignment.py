from __future__ import annotations

from typing import Any

import pandas as pd

from .contracts import COMMON_BASE_COLUMNS, INPUT_FILES, UNRESOLVED_TIER
from .utils import aliases_from_wikidata_item, description_from_wikidata_item, ensure_columns, label_from_wikidata_item, prefixed_row_values, read_json_dict, stable_id


def build_aligned_roles(normalized: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    persons = normalized["zdf_persons"].copy()
    wikidata_roles = read_json_dict(INPUT_FILES["wikidata_roles"])
    wikidata_roles_norm = normalized.get("wikidata_roles", pd.DataFrame()).copy()
    wd_norm_by_id = {
        str(row.get("entity_id", "")): row
        for _, row in wikidata_roles_norm.iterrows()
        if str(row.get("entity_id", "")).strip()
    }

    rows: list[dict[str, Any]] = []
    evidence_rows: list[dict[str, Any]] = []

    role_source = persons[persons["beschreibung"].fillna("").str.strip() != ""]

    for _, person in role_source.iterrows():
        role_text = str(person.get("beschreibung", "")).strip()
        mention_id = str(person.get("mention_id", ""))
        role_id = stable_id("role", mention_id, role_text)

        row = {
            "alignment_unit_id": role_id,
            "wikidata_id": "",
            "fernsehserien_de_id": "",
            "mention_id": mention_id,
            "canonical_label": role_text,
            "entity_class": "role",
            "match_confidence": 0.0,
            "match_tier": UNRESOLVED_TIER,
            "match_strategy": "description_role_extraction_best_effort",
            "evidence_summary": "Role text extracted from source description; no deterministic cross-source role mapping",
            "unresolved_reason_code": "insufficient_context",
            "unresolved_reason_detail": "Unstructured role descriptors cannot be aligned deterministically in baseline",
            "inference_flag": "false",
            "inference_basis": "",
            "notes": "",
            "label_wikidata": "",
            "label_fernsehserien_de": "",
            "label_zdf": role_text,
            "description_wikidata": "",
            "description_fernsehserien_de": "",
            "description_zdf": str(person.get("source_context", "")),
            "alias_wikidata": "",
            "alias_fernsehserien_de": "",
            "alias_zdf": "",
        }
        row.update(prefixed_row_values(person, suffix="zdf"))

        rows.append(row)
        evidence_rows.append(
            {
                "alignment_unit_id": role_id,
                "entity_class": "role",
                "match_strategy": row["match_strategy"],
                "match_tier": row["match_tier"],
                "match_confidence": row["match_confidence"],
                "evidence_summary": row["evidence_summary"],
                "unresolved_reason_code": row["unresolved_reason_code"],
            }
        )

    for wd_id, wd_item in sorted(wikidata_roles.items(), key=lambda pair: pair[0]):
        if not isinstance(wd_item, dict):
            continue

        wd_label = label_from_wikidata_item(wd_item)
        row = {
            "alignment_unit_id": stable_id("role_wd", wd_id),
            "wikidata_id": wd_id,
            "fernsehserien_de_id": "",
            "mention_id": "",
            "canonical_label": wd_label,
            "entity_class": "role",
            "match_confidence": 0.0,
            "match_tier": UNRESOLVED_TIER,
            "match_strategy": "wikidata_role_only_baseline",
            "evidence_summary": "Wikidata role carried forward without deterministic ZDF/fernsehserien_de mapping",
            "unresolved_reason_code": "no_candidate",
            "unresolved_reason_detail": "No deterministic role candidate in non-Wikidata sources",
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
        }
        if wd_id in wd_norm_by_id:
            row.update(prefixed_row_values(wd_norm_by_id[wd_id], suffix="wikidata"))
        rows.append(row)
        evidence_rows.append(
            {
                "alignment_unit_id": row["alignment_unit_id"],
                "entity_class": "role",
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


def build_aligned_organizations(normalized: dict[str, pd.DataFrame] | None = None) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    wikidata_orgs = read_json_dict(INPUT_FILES["wikidata_organizations"])
    orgs_norm_df = (normalized or {}).get("wikidata_organizations", pd.DataFrame()).copy()
    wd_norm_by_id = {
        str(row.get("entity_id", "")): row
        for _, row in orgs_norm_df.iterrows()
        if str(row.get("entity_id", "")).strip()
    }

    rows: list[dict[str, Any]] = []
    evidence_rows: list[dict[str, Any]] = []
    for wd_id, wd_item in sorted(wikidata_orgs.items(), key=lambda pair: pair[0]):
        if not isinstance(wd_item, dict):
            continue

        wd_label = label_from_wikidata_item(wd_item)
        row = {
            "alignment_unit_id": stable_id("organization_wd", wd_id),
            "wikidata_id": wd_id,
            "fernsehserien_de_id": "",
            "mention_id": "",
            "canonical_label": wd_label,
            "entity_class": "organization",
            "match_confidence": 0.0,
            "match_tier": UNRESOLVED_TIER,
            "match_strategy": "wikidata_organization_only_baseline",
            "evidence_summary": "Wikidata organization carried forward without deterministic ZDF/fernsehserien_de mapping",
            "unresolved_reason_code": "no_candidate",
            "unresolved_reason_detail": "No deterministic organization candidate in non-Wikidata sources",
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
        }
        if wd_id in wd_norm_by_id:
            row.update(prefixed_row_values(wd_norm_by_id[wd_id], suffix="wikidata"))
        rows.append(row)
        evidence_rows.append(
            {
                "alignment_unit_id": row["alignment_unit_id"],
                "entity_class": "organization",
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
