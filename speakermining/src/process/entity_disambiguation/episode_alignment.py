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
    parse_date,
    prefixed_row_values,
    read_json_dict,
    stable_id,
)


def _indexed_wikidata_episodes() -> tuple[dict[str, dict[str, Any]], dict[str, list[str]]]:
    entities = read_json_dict(INPUT_FILES["wikidata_episodes"])
    by_id: dict[str, dict[str, Any]] = {}
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


def _match_fernsehserien_episode(zdf_episode: pd.Series, fs_metadata: pd.DataFrame) -> pd.Series | None:
    zdf_date = parse_date(zdf_episode.get("publikationsdatum", ""))
    if pd.isna(zdf_date):
        return None

    candidates = fs_metadata[fs_metadata["premiere_date"].map(parse_date) == zdf_date]
    if candidates.empty:
        return None

    zdf_title_norm = normalize_text(zdf_episode.get("sendungstitel", ""))
    if zdf_title_norm:
        titled = candidates[candidates["episode_title_norm"].str.contains("folge", na=False)]
        if not titled.empty:
            return titled.sort_values(by=["episode_url"]).iloc[0]
    return candidates.sort_values(by=["episode_url"]).iloc[0]


def build_aligned_episodes(normalized: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    zdf_episodes = normalized["zdf_episodes"].copy()
    fs_metadata = normalized["fs_episode_metadata"].copy()
    fs_broadcasts = normalized["fs_episode_broadcasts"].copy()
    fs_guests = normalized["fs_episode_guests"].copy()
    zdf_publications = normalized["zdf_publications"].copy()
    wikidata_episodes_norm = normalized.get("wikidata_episodes", pd.DataFrame()).copy()

    fs_metadata["premiere_date"] = fs_metadata["premiere_date"].fillna("")
    fs_metadata["episode_title_norm"] = fs_metadata["episode_title"].map(normalize_text)

    wikidata_by_id, wikidata_by_label_norm = _indexed_wikidata_episodes()

    pub_by_episode = zdf_publications.sort_values(by=["episode_id", "publication_index"]).groupby("episode_id")
    guest_by_url = fs_guests.sort_values(by=["episode_url", "guest_order"]).groupby("episode_url")
    broadcasts_by_url = fs_broadcasts.sort_values(by=["episode_url", "broadcast_order"]).groupby("episode_url")
    wd_norm_by_id = {
        str(row.get("entity_id", "")): row
        for _, row in wikidata_episodes_norm.iterrows()
        if str(row.get("entity_id", "")).strip()
    }

    rows: list[dict[str, Any]] = []
    evidence_rows: list[dict[str, Any]] = []
    used_fs_ids: set[str] = set()
    used_wikidata_ids: set[str] = set()

    max_publications = 0
    max_guests = 0
    max_broadcasts = 0

    for _, ep in zdf_episodes.iterrows():
        episode_id = ep.get("episode_id", "")
        zdf_label = ep.get("sendungstitel", "")
        zdf_desc = ep.get("infos", "")

        fs_match = _match_fernsehserien_episode(ep, fs_metadata)
        fs_id = ""
        fs_label = ""
        fs_desc = ""

        if fs_match is not None:
            fs_id = str(fs_match.get("episode_url", ""))
            fs_label = str(fs_match.get("episode_title", ""))
            fs_desc = str(fs_match.get("description_text", ""))

        wd_ids = wikidata_by_label_norm.get(normalize_text(zdf_label), [])
        wd_id = wd_ids[0] if len(wd_ids) == 1 else ""
        wd_item = wikidata_by_id.get(wd_id, {}) if wd_id else {}
        if wd_id:
            used_wikidata_ids.add(wd_id)

        is_matched = bool(fs_id or wd_id)
        match_conf = 0.92 if fs_id else (0.80 if wd_id else 0.0)
        match_tier = HIGH_TIER if is_matched else UNRESOLVED_TIER

        unresolved_code = ""
        unresolved_detail = ""
        if not is_matched:
            unresolved_code = "no_candidate"
            unresolved_detail = "No deterministic fernsehserien_de or unique Wikidata episode candidate found"

        if fs_id:
            used_fs_ids.add(fs_id)

        inference_flag = False
        inference_basis = ""
        if not str(ep.get("season", "")).strip() and str(ep.get("publikationsdatum", "")).strip():
            inference_flag = True
            inference_basis = "Derived context from publication date when season label missing"

        row: dict[str, Any] = {
            "alignment_unit_id": episode_id,
            "wikidata_id": wd_id,
            "fernsehserien_de_id": fs_id,
            "mention_id": "",
            "canonical_label": zdf_label or fs_label or wd_item.get("label", ""),
            "entity_class": "episode",
            "match_confidence": round(match_conf, 3),
            "match_tier": match_tier,
            "match_strategy": "date_backbone_plus_title_signals",
            "evidence_summary": "date-aligned fs episode" if fs_id else ("unique label-equal wikidata episode" if wd_id else "no candidate above threshold"),
            "unresolved_reason_code": unresolved_code,
            "unresolved_reason_detail": unresolved_detail,
            "inference_flag": str(inference_flag).lower(),
            "inference_basis": inference_basis,
            "notes": "",
            "label_wikidata": wd_item.get("label", ""),
            "label_fernsehserien_de": fs_label,
            "label_zdf": zdf_label,
            "description_wikidata": wd_item.get("description", ""),
            "description_fernsehserien_de": fs_desc,
            "description_zdf": zdf_desc,
            "alias_wikidata": wd_item.get("aliases", ""),
            "alias_fernsehserien_de": "",
            "alias_zdf": "",
            "publikationsdatum_zdf": ep.get("publikationsdatum", ""),
            "dauer_zdf": ep.get("dauer", ""),
            "season_zdf": ep.get("season", ""),
        }
        row.update(prefixed_row_values(ep, suffix="zdf"))
        if fs_match is not None:
            row.update(prefixed_row_values(fs_match, suffix="fernsehserien_de"))
        if wd_id and wd_id in wd_norm_by_id:
            row.update(prefixed_row_values(wd_norm_by_id[wd_id], suffix="wikidata"))

        pubs = pub_by_episode.get_group(episode_id) if episode_id in pub_by_episode.groups else pd.DataFrame()
        guests = guest_by_url.get_group(fs_id) if fs_id and fs_id in guest_by_url.groups else pd.DataFrame()
        broadcasts = broadcasts_by_url.get_group(fs_id) if fs_id and fs_id in broadcasts_by_url.groups else pd.DataFrame()

        max_publications = max(max_publications, len(pubs))
        max_guests = max(max_guests, len(guests))
        max_broadcasts = max(max_broadcasts, len(broadcasts))

        for idx, (_, pub) in enumerate(pubs.iterrows(), start=1):
            row[f"publication_{idx}_date_zdf"] = pub.get("date", "")
            row[f"publication_{idx}_time_zdf"] = pub.get("time", "")
            row[f"publication_{idx}_program_zdf"] = pub.get("program", "")

        for idx, (_, guest) in enumerate(guests.iterrows(), start=1):
            row[f"guest_{idx}_name_fernsehserien_de"] = guest.get("guest_name", "")
            row[f"guest_{idx}_role_fernsehserien_de"] = guest.get("guest_role", "")

        for idx, (_, broadcast) in enumerate(broadcasts.iterrows(), start=1):
            row[f"broadcast_{idx}_date_fernsehserien_de"] = broadcast.get("broadcast_date", "")
            row[f"broadcast_{idx}_start_time_fernsehserien_de"] = broadcast.get("broadcast_start_time", "")
            row[f"broadcast_{idx}_end_date_fernsehserien_de"] = broadcast.get("broadcast_end_date", "")
            row[f"broadcast_{idx}_end_time_fernsehserien_de"] = broadcast.get("broadcast_end_time", "")
            row[f"broadcast_{idx}_broadcaster_fernsehserien_de"] = broadcast.get("broadcast_broadcaster", "")
            row[f"broadcast_{idx}_is_premiere_fernsehserien_de"] = broadcast.get("broadcast_is_premiere", "")

        rows.append(row)
        evidence_rows.append(
            {
                "alignment_unit_id": episode_id,
                "entity_class": "episode",
                "match_strategy": row["match_strategy"],
                "match_tier": row["match_tier"],
                "match_confidence": row["match_confidence"],
                "evidence_summary": row["evidence_summary"],
                "unresolved_reason_code": row["unresolved_reason_code"],
            }
        )

    # Preserve unmatched fernsehserien.de episodes as unresolved rows.
    for _, fs_row in fs_metadata.sort_values(by=["premiere_date", "episode_url"]).iterrows():
        fs_id = str(fs_row.get("episode_url", ""))
        if not fs_id or fs_id in used_fs_ids:
            continue

        row = {
            "alignment_unit_id": stable_id("episode_fs", fs_id),
            "wikidata_id": "",
            "fernsehserien_de_id": fs_id,
            "mention_id": "",
            "canonical_label": str(fs_row.get("episode_title", "")),
            "entity_class": "episode",
            "match_confidence": 0.0,
            "match_tier": UNRESOLVED_TIER,
            "match_strategy": "fs_episode_only_baseline",
            "evidence_summary": "fernsehserien_de episode carried forward without deterministic ZDF/Wikidata match",
            "unresolved_reason_code": "no_candidate",
            "unresolved_reason_detail": "No deterministic ZDF episode or unique Wikidata episode candidate",
            "inference_flag": "false",
            "inference_basis": "",
            "notes": "",
            "label_wikidata": "",
            "label_fernsehserien_de": str(fs_row.get("episode_title", "")),
            "label_zdf": "",
            "description_wikidata": "",
            "description_fernsehserien_de": str(fs_row.get("description_text", "")),
            "description_zdf": "",
            "alias_wikidata": "",
            "alias_fernsehserien_de": "",
            "alias_zdf": "",
            "publikationsdatum_zdf": "",
            "dauer_zdf": "",
            "season_zdf": "",
        }

        guests = guest_by_url.get_group(fs_id) if fs_id in guest_by_url.groups else pd.DataFrame()
        broadcasts = broadcasts_by_url.get_group(fs_id) if fs_id in broadcasts_by_url.groups else pd.DataFrame()
        max_guests = max(max_guests, len(guests))
        max_broadcasts = max(max_broadcasts, len(broadcasts))
        for idx, (_, guest) in enumerate(guests.iterrows(), start=1):
            row[f"guest_{idx}_name_fernsehserien_de"] = guest.get("guest_name", "")
            row[f"guest_{idx}_role_fernsehserien_de"] = guest.get("guest_role", "")
        for idx, (_, broadcast) in enumerate(broadcasts.iterrows(), start=1):
            row[f"broadcast_{idx}_date_fernsehserien_de"] = broadcast.get("broadcast_date", "")
            row[f"broadcast_{idx}_start_time_fernsehserien_de"] = broadcast.get("broadcast_start_time", "")
            row[f"broadcast_{idx}_end_date_fernsehserien_de"] = broadcast.get("broadcast_end_date", "")
            row[f"broadcast_{idx}_end_time_fernsehserien_de"] = broadcast.get("broadcast_end_time", "")
            row[f"broadcast_{idx}_broadcaster_fernsehserien_de"] = broadcast.get("broadcast_broadcaster", "")
            row[f"broadcast_{idx}_is_premiere_fernsehserien_de"] = broadcast.get("broadcast_is_premiere", "")

        row.update(prefixed_row_values(fs_row, suffix="fernsehserien_de"))

        rows.append(row)
        evidence_rows.append(
            {
                "alignment_unit_id": row["alignment_unit_id"],
                "entity_class": "episode",
                "match_strategy": row["match_strategy"],
                "match_tier": row["match_tier"],
                "match_confidence": row["match_confidence"],
                "evidence_summary": row["evidence_summary"],
                "unresolved_reason_code": row["unresolved_reason_code"],
            }
        )

    # Preserve unmatched Wikidata episodes as unresolved rows.
    for wd_id, wd_item in sorted(wikidata_by_id.items(), key=lambda pair: pair[0]):
        if wd_id in used_wikidata_ids:
            continue

        row = {
            "alignment_unit_id": stable_id("episode_wd", wd_id),
            "wikidata_id": wd_id,
            "fernsehserien_de_id": "",
            "mention_id": "",
            "canonical_label": wd_item.get("label", ""),
            "entity_class": "episode",
            "match_confidence": 0.0,
            "match_tier": UNRESOLVED_TIER,
            "match_strategy": "wikidata_episode_only_baseline",
            "evidence_summary": "Wikidata episode carried forward without deterministic ZDF/fernsehserien_de match",
            "unresolved_reason_code": "no_candidate",
            "unresolved_reason_detail": "No deterministic ZDF episode or fernsehserien_de episode candidate",
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
            "publikationsdatum_zdf": "",
            "dauer_zdf": "",
            "season_zdf": "",
        }
        if wd_id in wd_norm_by_id:
            row.update(prefixed_row_values(wd_norm_by_id[wd_id], suffix="wikidata"))

        rows.append(row)
        evidence_rows.append(
            {
                "alignment_unit_id": row["alignment_unit_id"],
                "entity_class": "episode",
                "match_strategy": row["match_strategy"],
                "match_tier": row["match_tier"],
                "match_confidence": row["match_confidence"],
                "evidence_summary": row["evidence_summary"],
                "unresolved_reason_code": row["unresolved_reason_code"],
            }
        )

    aligned = pd.DataFrame(rows)
    for idx in range(1, max_publications + 1):
        for col in ("date", "time", "program"):
            column = f"publication_{idx}_{col}_zdf"
            if column not in aligned.columns:
                aligned[column] = ""

    for idx in range(1, max_guests + 1):
        for col in ("name", "role"):
            column = f"guest_{idx}_{col}_fernsehserien_de"
            if column not in aligned.columns:
                aligned[column] = ""

    for idx in range(1, max_broadcasts + 1):
        for col in ("date", "start_time", "end_date", "end_time", "broadcaster", "is_premiere"):
            column = f"broadcast_{idx}_{col}_fernsehserien_de"
            if column not in aligned.columns:
                aligned[column] = ""

    aligned = ensure_columns(aligned, COMMON_BASE_COLUMNS + [c for c in aligned.columns if c not in COMMON_BASE_COLUMNS])
    aligned = aligned.sort_values(by=["publikationsdatum_zdf", "canonical_label", "alignment_unit_id"], na_position="last")
    return aligned.reset_index(drop=True), evidence_rows
