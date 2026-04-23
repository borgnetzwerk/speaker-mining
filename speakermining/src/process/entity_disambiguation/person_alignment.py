from __future__ import annotations

from collections import defaultdict
from typing import Any

import pandas as pd

from .contracts import COMMON_BASE_COLUMNS, HIGH_TIER, INPUT_FILES, UNRESOLVED_TIER
from .utils import (
    aliases_from_wikidata_item,
    description_from_wikidata_item,
    ensure_columns,
    label_from_wikidata_item,
    normalize_text,
    prefixed_row_values,
    read_json_dict,
    safe_column_name,
    stable_id,
)


def _indexed_wikidata_persons() -> tuple[dict[str, dict[str, str]], dict[str, list[str]]]:
    entities = read_json_dict(INPUT_FILES["wikidata_persons"])
    by_id: dict[str, dict[str, str]] = {}
    by_label_norm: dict[str, list[str]] = defaultdict(list)

    for qid, item in entities.items():
        label = label_from_wikidata_item(item)
        by_id[qid] = {
            "id": qid,
            "label": label,
            "description": description_from_wikidata_item(item),
            "aliases": aliases_from_wikidata_item(item),
        }
        if label:
            by_label_norm[normalize_text(label)].append(qid)

    return by_id, by_label_norm


def _build_fs_guest_index(fs_guests: pd.DataFrame) -> dict[str, list[dict[str, Any]]]:
    index: dict[str, list[dict[str, str]]] = defaultdict(list)
    for _, row in fs_guests.sort_values(by=["episode_url", "guest_order"]).iterrows():
        index[str(row.get("episode_url", ""))].append(
            {
                "guest_name": str(row.get("guest_name", "")),
                "guest_description": str(row.get("guest_description", "")),
                "raw_row": row,
            }
        )
    return index


def build_aligned_persons(
    normalized: dict[str, pd.DataFrame],
    aligned_episodes: pd.DataFrame,
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    zdf_persons = normalized["zdf_persons"].copy()
    fs_guests = normalized["fs_episode_guests"].copy()

    episode_to_fs = {
        str(row.get("alignment_unit_id", "")): str(row.get("fernsehserien_de_id", ""))
        for _, row in aligned_episodes.iterrows()
    }

    fs_guest_index = _build_fs_guest_index(fs_guests)
    wikidata_by_id, wikidata_by_label_norm = _indexed_wikidata_persons()
    wikidata_persons_norm = normalized.get("wikidata_persons", pd.DataFrame()).copy()
    wd_norm_by_id = {
        str(row.get("entity_id", "")): row
        for _, row in wikidata_persons_norm.iterrows()
        if str(row.get("entity_id", "")).strip()
    }
    used_wikidata_ids: set[str] = set()
    used_fs_guest_keys: set[str] = set()

    rows: list[dict[str, Any]] = []
    evidence_rows: list[dict[str, Any]] = []

    for _, person in zdf_persons.iterrows():
        mention_id = str(person.get("mention_id", ""))
        episode_id = str(person.get("episode_id", ""))
        name = str(person.get("name", ""))
        description = str(person.get("beschreibung", ""))
        fs_episode_url = episode_to_fs.get(episode_id, "")

        fs_match_name = ""
        fs_match_description = ""
        fs_match_row = None
        if fs_episode_url and fs_episode_url in fs_guest_index:
            norm_name = normalize_text(name)
            for guest in fs_guest_index[fs_episode_url]:
                if normalize_text(guest["guest_name"]) == norm_name:
                    fs_match_name = guest["guest_name"]
                    fs_match_description = guest["guest_description"]
                    fs_match_row = guest.get("raw_row")
                    used_fs_guest_keys.add(stable_id("guest", fs_episode_url, fs_match_name, fs_match_description))
                    break

        wd_ids = wikidata_by_label_norm.get(normalize_text(name), [])
        wd_id = wd_ids[0] if len(wd_ids) == 1 else ""
        wd_item = wikidata_by_id.get(wd_id, {}) if wd_id else {}
        if wd_id:
            used_wikidata_ids.add(wd_id)

        matched = bool(fs_match_name or wd_id)
        confidence = 0.95 if fs_match_name else (0.83 if wd_id else 0.0)
        tier = HIGH_TIER if matched else UNRESOLVED_TIER

        unresolved_code = ""
        unresolved_detail = ""
        if not matched:
            unresolved_code = "no_candidate"
            unresolved_detail = "No deterministic same-episode guest or unique Wikidata person candidate"

        row = {
            "alignment_unit_id": mention_id,
            "wikidata_id": wd_id,
            "fernsehserien_de_id": fs_episode_url,
            "mention_id": mention_id,
            "canonical_label": name,
            "open_refine_name": name.strip().strip("-").strip(),
            "entity_class": "person",
            "match_confidence": round(confidence, 3),
            "match_tier": tier,
            "match_strategy": "episode_context_name_exact",
            "evidence_summary": "same-episode exact guest-name match" if fs_match_name else ("unique label-equal wikidata person" if wd_id else "no candidate above threshold"),
            "unresolved_reason_code": unresolved_code,
            "unresolved_reason_detail": unresolved_detail,
            "inference_flag": "false",
            "inference_basis": "",
            "notes": "",
            "label_wikidata": wd_item.get("label", ""),
            "label_fernsehserien_de": fs_match_name,
            "label_zdf": name,
            "description_wikidata": wd_item.get("description", ""),
            "description_fernsehserien_de": fs_match_description,
            "description_zdf": description,
            "alias_wikidata": wd_item.get("aliases", ""),
            "alias_fernsehserien_de": "",
            "alias_zdf": "",
            "episode_id_zdf": episode_id,
        }
        row.update(prefixed_row_values(person, suffix="zdf"))
        if fs_match_row is not None:
            row.update(prefixed_row_values(fs_match_row, suffix="fernsehserien_de"))
        if wd_id and wd_id in wd_norm_by_id:
            row.update(prefixed_row_values(wd_norm_by_id[wd_id], suffix="wikidata"))

        rows.append(row)
        evidence_rows.append(
            {
                "alignment_unit_id": mention_id,
                "entity_class": "person",
                "match_strategy": row["match_strategy"],
                "match_tier": row["match_tier"],
                "match_confidence": row["match_confidence"],
                "evidence_summary": row["evidence_summary"],
                "unresolved_reason_code": row["unresolved_reason_code"],
            }
        )

    # Preserve unmatched fernsehserien_de guests as unresolved person rows.
    for _, guest in fs_guests.sort_values(by=["episode_url", "guest_order"]).iterrows():
        fs_episode_url = str(guest.get("episode_url", "")).strip()
        guest_name = str(guest.get("guest_name", "")).strip()
        guest_description = str(guest.get("guest_description", "")).strip()
        guest_key = stable_id("guest", fs_episode_url, guest_name, guest_description)
        if not guest_name or guest_key in used_fs_guest_keys:
            continue

        row = {
            "alignment_unit_id": stable_id("person_fs", fs_episode_url, guest_name, guest_description),
            "wikidata_id": "",
            "fernsehserien_de_id": fs_episode_url,
            "mention_id": "",
            "canonical_label": guest_name,
            "open_refine_name": guest_name.strip().strip("-").strip(),
            "entity_class": "person",
            "match_confidence": 0.0,
            "match_tier": UNRESOLVED_TIER,
            "match_strategy": "fernsehserien_guest_only_baseline",
            "evidence_summary": "Fernsehserien guest carried forward without deterministic ZDF mention or unique Wikidata person match",
            "unresolved_reason_code": "no_candidate",
            "unresolved_reason_detail": "No deterministic ZDF person mention candidate",
            "inference_flag": "false",
            "inference_basis": "",
            "notes": "",
            "label_wikidata": "",
            "label_fernsehserien_de": guest_name,
            "label_zdf": "",
            "description_wikidata": "",
            "description_fernsehserien_de": guest_description,
            "description_zdf": "",
            "alias_wikidata": "",
            "alias_fernsehserien_de": "",
            "alias_zdf": "",
            "episode_id_zdf": "",
        }
        row.update(prefixed_row_values(guest, suffix="fernsehserien_de"))
        rows.append(row)
        evidence_rows.append(
            {
                "alignment_unit_id": row["alignment_unit_id"],
                "entity_class": "person",
                "match_strategy": row["match_strategy"],
                "match_tier": row["match_tier"],
                "match_confidence": row["match_confidence"],
                "evidence_summary": row["evidence_summary"],
                "unresolved_reason_code": row["unresolved_reason_code"],
            }
        )

    # Preserve unmatched Wikidata persons as unresolved rows.
    for wd_id, wd_item in sorted(wikidata_by_id.items(), key=lambda pair: pair[0]):
        if wd_id in used_wikidata_ids:
            continue

        wd_label = wd_item.get("label", "")
        row = {
            "alignment_unit_id": stable_id("person_wd", wd_id),
            "wikidata_id": wd_id,
            "fernsehserien_de_id": "",
            "mention_id": "",
            "canonical_label": wd_label,
            "open_refine_name": wd_label.strip().strip("-").strip(),
            "entity_class": "person",
            "match_confidence": 0.0,
            "match_tier": UNRESOLVED_TIER,
            "match_strategy": "wikidata_person_only_baseline",
            "evidence_summary": "Wikidata person carried forward without deterministic ZDF/fernsehserien_de match",
            "unresolved_reason_code": "no_candidate",
            "unresolved_reason_detail": "No deterministic ZDF mention or fernsehserien_de guest candidate",
            "inference_flag": "false",
            "inference_basis": "",
            "notes": "",
            "label_wikidata": wd_item.get("label", ""),
            "label_fernsehserien_de": "",
            "label_zdf": "",
            "description_wikidata": wd_item.get("description", ""),
            "description_fernsehserien_de": "",
            "description_zdf": "",
            "alias_wikidata": wd_item.get("aliases", ""),
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
                "entity_class": "person",
                "match_strategy": row["match_strategy"],
                "match_tier": row["match_tier"],
                "match_confidence": row["match_confidence"],
                "evidence_summary": row["evidence_summary"],
                "unresolved_reason_code": row["unresolved_reason_code"],
            }
        )

    aligned = pd.DataFrame(rows)
    aligned = ensure_columns(aligned, COMMON_BASE_COLUMNS + [c for c in aligned.columns if c not in COMMON_BASE_COLUMNS])
    aligned = aligned.sort_values(by=["canonical_label", "episode_id_zdf", "alignment_unit_id"]).reset_index(drop=True)
    return aligned, evidence_rows
