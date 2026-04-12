from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from process.io_guardrails import atomic_write_csv, atomic_write_text, safe_rmtree

from .contracts import (
    ALIGNED_DIR,
    COMMON_BASE_COLUMNS,
    EXACT_TIER,
    INPUT_FILES,
    LAYERED_EXAMPLES_DIR,
    NORMALIZED_DIR,
    NORMALIZED_EXAMPLES_DIR,
    OUTPUT_FILES,
    PHASE31_DIR,
    RAW_EXAMPLES_DIR,
    RAW_IMPORT_DIR,
    SCHEMA_EXAMPLES_DIR,
)
from .episode_alignment import build_aligned_episodes
from .evidence import combine_evidence_rows
from .io_staging import stage_inputs
from .normalization import normalize_inputs
from .person_alignment import build_aligned_persons
from .quality_gates import run_quality_gates
from .role_org_alignment import build_aligned_organizations, build_aligned_roles
from .schema_mapping import write_schema_mapping
from .topic_alignment import build_aligned_topics
from .utils import (
    aliases_from_wikidata_item,
    description_from_wikidata_item,
    ensure_columns,
    first_non_empty,
    label_from_wikidata_item,
    normalize_text,
    prefixed_row_values,
    read_json_dict,
    stable_id,
)


def _write_example(df: pd.DataFrame, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sample = df.head(1)
    atomic_write_csv(out_path, sample, index=False)


def build_source_inventory_report() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for source_name, source_path in INPUT_FILES.items():
        if source_path.suffix.lower() == ".csv":
            df = pd.read_csv(source_path, dtype=str).fillna("")
            rows.append(
                {
                    "source_name": source_name,
                    "source_kind": "csv",
                    "instances": int(len(df)),
                    "properties": int(len(df.columns)),
                    "property_summary": ", ".join(df.columns[:8]),
                    "source_path": source_path.as_posix(),
                }
            )
            continue

        if source_path.suffix.lower() == ".json":
            with source_path.open("r", encoding="utf-8") as f:
                payload = json.load(f)

            if isinstance(payload, dict):
                claim_properties = sorted(
                    {
                        claim_property
                        for item in payload.values()
                        if isinstance(item, dict)
                        for claim_property in (item.get("claims", {}) or {}).keys()
                    }
                )
                rows.append(
                    {
                        "source_name": source_name,
                        "source_kind": "json",
                        "instances": int(len(payload)),
                        "properties": int(len(claim_properties)),
                        "property_summary": ", ".join(claim_properties[:8]),
                        "source_path": source_path.as_posix(),
                    }
                )
                continue

            rows.append(
                {
                    "source_name": source_name,
                    "source_kind": "json",
                    "instances": int(len(payload)) if isinstance(payload, list) else 0,
                    "properties": 0,
                    "property_summary": "",
                    "source_path": source_path.as_posix(),
                }
            )

    inventory = pd.DataFrame(rows).sort_values(by=["source_name"]).reset_index(drop=True)
    return inventory


def _wikidata_series_rows() -> list[dict[str, str]]:
    series_path = INPUT_FILES.get("wikidata_series")
    if series_path is None or not series_path.exists():
        return []

    with series_path.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    if not isinstance(payload, dict):
        return []

    rows: list[dict[str, str]] = []
    for qid, item in payload.items():
        if not isinstance(item, dict):
            continue

        labels = item.get("labels", {}) or {}
        descriptions = item.get("descriptions", {}) or {}
        label = first_non_empty(
            [
                ((labels.get("de") or {}).get("value", "") if isinstance(labels, dict) else ""),
                ((labels.get("en") or {}).get("value", "") if isinstance(labels, dict) else ""),
            ]
        )

        description = first_non_empty(
            [
                ((descriptions.get("de") or {}).get("value", "") if isinstance(descriptions, dict) else ""),
                ((descriptions.get("en") or {}).get("value", "") if isinstance(descriptions, dict) else ""),
            ]
        )

        if not label or not qid:
            continue

        rows.append(
            {
                "wikidata_id": str(qid).strip(),
                "label": label,
                "description": description,
                "normalized_label": normalize_text(label),
                "has_de_label": "1" if isinstance(labels, dict) and bool((labels.get("de") or {}).get("value", "")) else "0",
            }
        )

    return sorted(rows, key=lambda row: (row.get("normalized_label", ""), row.get("has_de_label", "0") != "1", row.get("wikidata_id", "")))


def _write_raw_input_examples(staging_manifest: pd.DataFrame) -> None:
    RAW_EXAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    for _, row in staging_manifest.iterrows():
        staged_path = Path(str(row.get("staged_path", "")))
        if not staged_path.exists():
            continue

        suffix = staged_path.suffix.lower()
        example_name = f"{staged_path.stem}.example{suffix}"
        example_path = RAW_EXAMPLES_DIR / example_name

        if suffix == ".csv":
            sample = pd.read_csv(staged_path, nrows=1, dtype=str).fillna("")
            atomic_write_csv(example_path, sample, index=False)
            continue

        if suffix == ".json":
            with staged_path.open("r", encoding="utf-8") as f:
                payload = json.load(f)

            if isinstance(payload, dict):
                if payload:
                    first_key = sorted(payload.keys())[0]
                    sample_payload = {first_key: payload[first_key]}
                else:
                    sample_payload = {}
            elif isinstance(payload, list):
                sample_payload = payload[:1]
            else:
                sample_payload = payload

            atomic_write_text(example_path, json.dumps(sample_payload, indent=2, ensure_ascii=True) + "\n")
            continue

        atomic_write_text(example_path, staged_path.read_text(encoding="utf-8")[:2000])


def _build_aligned_broadcasting_programs(normalized: dict[str, pd.DataFrame] | None = None) -> pd.DataFrame:
    normalized = normalized or {}
    programs = normalized.get("setup_broadcasting_programs", pd.DataFrame()).copy()
    if programs.empty:
        programs = pd.read_csv(INPUT_FILES["setup_broadcasting_programs"], dtype=str).fillna("")

    wikidata_programs_norm = normalized.get("wikidata_programs", pd.DataFrame()).copy()
    wd_norm_by_id = {
        str(row.get("entity_id", "")): row
        for _, row in wikidata_programs_norm.iterrows()
        if str(row.get("entity_id", "")).strip()
    }
    wikidata_programs = read_json_dict(INPUT_FILES["wikidata_programs"])

    setup_by_norm_label: dict[str, list[dict[str, str]]] = {}
    for _, program in programs.iterrows():
        setup_label = first_non_empty([program.get("label_de", ""), program.get("label", "")])
        normalized_label = normalize_text(setup_label)
        if not normalized_label:
            continue
        setup_by_norm_label.setdefault(normalized_label, []).append(
            {
                "filename": str(program.get("filename", "")).strip(),
                "wikidata_id": str(program.get("wikidata_id", "")).strip(),
                "fernsehserien_de_id": str(program.get("fernsehserien_de_id", "")).strip(),
                "label": str(program.get("label", "")).strip(),
                "label_de": str(program.get("label_de", "")).strip(),
                "description": str(program.get("description", "")).strip(),
                "description_de": str(program.get("description_de", "")).strip(),
                "alias": str(program.get("alias", "")).strip(),
                "alias_de": str(program.get("alias_de", "")).strip(),
            }
        )

    for setup_candidates in setup_by_norm_label.values():
        setup_candidates.sort(key=lambda row: (row.get("filename", ""), row.get("fernsehserien_de_id", "")))

    rows: list[dict[str, Any]] = []
    used_setup_filenames: set[str] = set()

    for wd_id, wd_item in sorted(wikidata_programs.items(), key=lambda pair: pair[0]):
        if not isinstance(wd_item, dict):
            continue

        wd_label = label_from_wikidata_item(wd_item)
        normalized_label = normalize_text(wd_label)
        matched_setup = None
        if normalized_label in setup_by_norm_label:
            candidates = [candidate for candidate in setup_by_norm_label[normalized_label] if candidate.get("filename", "") not in used_setup_filenames]
            if candidates:
                matched_setup = candidates[0]
                used_setup_filenames.add(matched_setup.get("filename", ""))

        has_setup_match = matched_setup is not None
        setup_filename = matched_setup.get("filename", "") if matched_setup else ""
        setup_label_de = matched_setup.get("label_de", "") if matched_setup else ""
        setup_label = matched_setup.get("label", "") if matched_setup else ""
        canonical_label = first_non_empty([setup_label_de, setup_label, wd_label])

        rows.append(
            {
                "alignment_unit_id": setup_filename or stable_id("broadcasting_program_wd", wd_id, wd_label),
                "wikidata_id": wd_id,
                "fernsehserien_de_id": matched_setup.get("fernsehserien_de_id", "") if matched_setup else "",
                "mention_id": "",
                "canonical_label": canonical_label,
                "entity_class": "broadcasting_program",
                "match_confidence": 1.0 if has_setup_match else 0.0,
                "match_tier": EXACT_TIER if has_setup_match else "unresolved",
                "match_strategy": "wikidata_setup_label_match" if has_setup_match else "wikidata_program_only_baseline",
                "evidence_summary": (
                    f"Exact normalized label match between setup baseline and Wikidata for {canonical_label}"
                    if has_setup_match
                    else "Wikidata program carried forward without deterministic setup baseline match"
                ),
                "unresolved_reason_code": "" if has_setup_match else "no_candidate",
                "unresolved_reason_detail": "" if has_setup_match else "No deterministic setup baseline candidate for this Wikidata program",
                "inference_flag": "false",
                "inference_basis": "",
                "notes": "",
                "label_wikidata": wd_label,
                "label_fernsehserien_de": setup_label_de,
                "label_zdf": setup_label,
                "description_wikidata": description_from_wikidata_item(wd_item),
                "description_fernsehserien_de": matched_setup.get("description_de", "") if matched_setup else "",
                "description_zdf": matched_setup.get("description", "") if matched_setup else "",
                "alias_wikidata": aliases_from_wikidata_item(wd_item),
                "alias_fernsehserien_de": matched_setup.get("alias_de", "") if matched_setup else "",
                "alias_zdf": matched_setup.get("alias", "") if matched_setup else "",
            }
        )
        row = rows[-1]
        if matched_setup is not None:
            row.update(prefixed_row_values(matched_setup, suffix="setup"))
        if wd_id in wd_norm_by_id:
            row.update(prefixed_row_values(wd_norm_by_id[wd_id], suffix="wikidata"))

    # Preserve unmatched setup baseline programs as unresolved rows.
    for _, program in programs.iterrows():
        filename = str(program.get("filename", "")).strip()
        if filename and filename in used_setup_filenames:
            continue

        label_wikidata = str(program.get("label", "")).strip()
        label_fernsehserien_de = first_non_empty([program.get("label_de", ""), program.get("label", "")])
        label_zdf = first_non_empty([program.get("label", ""), program.get("label_de", "")])
        canonical_label = first_non_empty([label_fernsehserien_de, label_wikidata, filename.replace("_", " ").title()])
        rows.append(
            {
                "alignment_unit_id": filename or stable_id("broadcasting_program_setup", label_wikidata, label_fernsehserien_de),
                "wikidata_id": str(program.get("wikidata_id", "")).strip(),
                "fernsehserien_de_id": str(program.get("fernsehserien_de_id", "")).strip(),
                "mention_id": "",
                "canonical_label": canonical_label,
                "entity_class": "broadcasting_program",
                "match_confidence": 0.0,
                "match_tier": "unresolved",
                "match_strategy": "setup_program_only_baseline",
                "evidence_summary": "Setup baseline program carried forward without deterministic Wikidata match",
                "unresolved_reason_code": "no_candidate",
                "unresolved_reason_detail": "No deterministic Wikidata program candidate for this setup baseline row",
                "inference_flag": "false",
                "inference_basis": "",
                "notes": "",
                "label_wikidata": label_wikidata,
                "label_fernsehserien_de": label_fernsehserien_de,
                "label_zdf": label_zdf,
                "description_wikidata": str(program.get("description", "")).strip(),
                "description_fernsehserien_de": str(program.get("description_de", "")).strip(),
                "description_zdf": str(program.get("description", "")).strip(),
                "alias_wikidata": str(program.get("alias", "")).strip(),
                "alias_fernsehserien_de": str(program.get("alias_de", "")).strip(),
                "alias_zdf": str(program.get("alias", "")).strip(),
            }
        )
        rows[-1].update(prefixed_row_values(program, suffix="setup"))

    aligned = pd.DataFrame(rows)
    aligned = ensure_columns(aligned, COMMON_BASE_COLUMNS + [c for c in aligned.columns if c not in COMMON_BASE_COLUMNS])
    return aligned.sort_values(by=["canonical_label", "alignment_unit_id"]).reset_index(drop=True)


def _build_aligned_seasons(normalized: dict[str, pd.DataFrame]) -> pd.DataFrame:
    seasons = normalized["zdf_seasons"].copy()
    wikidata_rows = _wikidata_series_rows()
    wikidata_series_norm = normalized.get("wikidata_series", pd.DataFrame()).copy()
    wd_norm_by_id = {
        str(row.get("entity_id", "")): row
        for _, row in wikidata_series_norm.iterrows()
        if str(row.get("entity_id", "")).strip()
    }

    zdf_by_norm_label: dict[str, list[dict[str, str]]] = {}
    for _, season in seasons.iterrows():
        season_label = str(season.get("season_label", "")).strip()
        season_id = str(season.get("season_id", "")).strip()
        normalized_label = normalize_text(season_label)
        if not normalized_label:
            continue

        zdf_by_norm_label.setdefault(normalized_label, []).append(
            {
                "season_id": season_id,
                "season_label": season_label,
                "start_time": str(season.get("start_time", "")),
                "end_time": str(season.get("end_time", "")),
            }
        )

    for zdf_candidates in zdf_by_norm_label.values():
        zdf_candidates.sort(key=lambda row: (row.get("season_id", ""), row.get("season_label", "")))

    used_zdf_ids: set[str] = set()
    rows: list[dict[str, Any]] = []

    # First emit all Wikidata series rows; attach matching ZDF season when label-normalized match exists.
    for wd in wikidata_rows:
        normalized_label = wd.get("normalized_label", "")
        matched_zdf = None
        if normalized_label and normalized_label in zdf_by_norm_label:
            candidates = [candidate for candidate in zdf_by_norm_label[normalized_label] if candidate.get("season_id", "") not in used_zdf_ids]
            if candidates:
                matched_zdf = candidates[0]
                used_zdf_ids.add(matched_zdf.get("season_id", ""))

        has_zdf_match = matched_zdf is not None
        season_id = matched_zdf.get("season_id", "") if matched_zdf else ""
        zdf_label = matched_zdf.get("season_label", "") if matched_zdf else ""
        canonical_label = first_non_empty([zdf_label, wd.get("label", "")])

        rows.append(
            {
                "alignment_unit_id": season_id or stable_id("season_wd", wd.get("wikidata_id", ""), wd.get("label", "")),
                "wikidata_id": wd.get("wikidata_id", ""),
                "fernsehserien_de_id": "",
                "mention_id": season_id,
                "canonical_label": canonical_label,
                "entity_class": "season",
                "match_confidence": 1.0 if has_zdf_match else 0.0,
                "match_tier": EXACT_TIER if has_zdf_match else "unresolved",
                "match_strategy": "wikidata_zdf_label_match" if has_zdf_match else "wikidata_series_only_baseline",
                "evidence_summary": (
                    f"Exact normalized label match between Wikidata and ZDF for {canonical_label}"
                    if has_zdf_match
                    else "Wikidata series row carried forward without deterministic ZDF season match"
                ),
                "unresolved_reason_code": "" if has_zdf_match else "no_candidate",
                "unresolved_reason_detail": "" if has_zdf_match else "No deterministic ZDF season candidate for this Wikidata series label",
                "inference_flag": "false",
                "inference_basis": "",
                "notes": "",
                "label_wikidata": wd.get("label", ""),
                "label_fernsehserien_de": "",
                "label_zdf": zdf_label,
                "description_wikidata": wd.get("description", ""),
                "description_fernsehserien_de": "",
                "description_zdf": "",
                "alias_wikidata": "",
                "alias_fernsehserien_de": "",
                "alias_zdf": "",
                "start_time_zdf": matched_zdf.get("start_time", "") if matched_zdf else "",
                "end_time_zdf": matched_zdf.get("end_time", "") if matched_zdf else "",
            }
        )
        row = rows[-1]
        if matched_zdf is not None:
            row.update(prefixed_row_values(matched_zdf, suffix="zdf"))
        wd_id = wd.get("wikidata_id", "")
        if wd_id in wd_norm_by_id:
            row.update(prefixed_row_values(wd_norm_by_id[wd_id], suffix="wikidata"))

    # Then preserve remaining unmatched ZDF seasons as unresolved rows.
    for _, season in seasons.iterrows():
        season_id = str(season.get("season_id", "")).strip()
        if season_id in used_zdf_ids:
            continue

        season_label = str(season.get("season_label", "")).strip()
        rows.append(
            {
                "alignment_unit_id": season_id,
                "wikidata_id": "",
                "fernsehserien_de_id": "",
                "mention_id": season_id,
                "canonical_label": season_label,
                "entity_class": "season",
                "match_confidence": 0.0,
                "match_tier": "unresolved",
                "match_strategy": "zdf_season_only_baseline",
                "evidence_summary": "ZDF season row carried forward without deterministic Wikidata series match",
                "unresolved_reason_code": "no_candidate",
                "unresolved_reason_detail": "No deterministic Wikidata series candidate for this ZDF season label",
                "inference_flag": "false",
                "inference_basis": "",
                "notes": "",
                "label_wikidata": "",
                "label_fernsehserien_de": "",
                "label_zdf": season_label,
                "description_wikidata": "",
                "description_fernsehserien_de": "",
                "description_zdf": "",
                "alias_wikidata": "",
                "alias_fernsehserien_de": "",
                "alias_zdf": "",
                "start_time_zdf": str(season.get("start_time", "")),
                "end_time_zdf": str(season.get("end_time", "")),
            }
        )
        rows[-1].update(prefixed_row_values(season, suffix="zdf"))

    aligned = pd.DataFrame(rows)
    aligned = ensure_columns(aligned, COMMON_BASE_COLUMNS + [c for c in aligned.columns if c not in COMMON_BASE_COLUMNS])
    return aligned.sort_values(by=["canonical_label", "alignment_unit_id"]).reset_index(drop=True)


def _reset_outputs() -> None:
    for path in (RAW_IMPORT_DIR, NORMALIZED_DIR, ALIGNED_DIR):
        if path.exists():
            safe_rmtree(path)


def run_phase31(*, overwrite_outputs: bool = False, write_examples: bool = True, strict_mode: bool = True) -> dict[str, Any]:
    if overwrite_outputs:
        _reset_outputs()

    PHASE31_DIR.mkdir(parents=True, exist_ok=True)
    RAW_IMPORT_DIR.mkdir(parents=True, exist_ok=True)
    NORMALIZED_DIR.mkdir(parents=True, exist_ok=True)
    ALIGNED_DIR.mkdir(parents=True, exist_ok=True)

    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")

    staging_manifest = stage_inputs()
    normalized = normalize_inputs()
    schema_mapping = write_schema_mapping(normalized)

    aligned_broadcasting_programs = _build_aligned_broadcasting_programs(normalized)
    aligned_seasons = _build_aligned_seasons(normalized)
    aligned_episodes, episode_evidence = build_aligned_episodes(normalized)
    aligned_persons, person_evidence = build_aligned_persons(normalized, aligned_episodes)
    aligned_topics, topic_evidence = build_aligned_topics(normalized)
    aligned_roles, role_evidence = build_aligned_roles(normalized)
    aligned_organizations, organization_evidence = build_aligned_organizations(normalized)

    atomic_write_csv(OUTPUT_FILES["aligned_broadcasting_programs"], aligned_broadcasting_programs, index=False)
    atomic_write_csv(OUTPUT_FILES["aligned_seasons"], aligned_seasons, index=False)
    atomic_write_csv(OUTPUT_FILES["aligned_episodes"], aligned_episodes, index=False)
    atomic_write_csv(OUTPUT_FILES["aligned_persons"], aligned_persons, index=False)
    atomic_write_csv(OUTPUT_FILES["aligned_topics"], aligned_topics, index=False)
    atomic_write_csv(OUTPUT_FILES["aligned_roles"], aligned_roles, index=False)
    atomic_write_csv(OUTPUT_FILES["aligned_organizations"], aligned_organizations, index=False)

    evidence_df = combine_evidence_rows(episode_evidence, person_evidence, topic_evidence, role_evidence, organization_evidence)
    atomic_write_csv(OUTPUT_FILES["match_evidence"], evidence_df, index=False)

    if write_examples:
        _write_example(staging_manifest, RAW_EXAMPLES_DIR / "staging_manifest.example.csv")
        _write_raw_input_examples(staging_manifest)
        for key, df in normalized.items():
            _write_example(df, NORMALIZED_EXAMPLES_DIR / f"{key}.example.csv")
        _write_example(schema_mapping, SCHEMA_EXAMPLES_DIR / "source_schema_mapping.example.csv")
        _write_example(aligned_broadcasting_programs, LAYERED_EXAMPLES_DIR / "aligned_broadcasting_programs.example.csv")
        _write_example(aligned_seasons, LAYERED_EXAMPLES_DIR / "aligned_seasons.example.csv")
        _write_example(aligned_episodes, LAYERED_EXAMPLES_DIR / "aligned_episodes.example.csv")
        _write_example(aligned_persons, LAYERED_EXAMPLES_DIR / "aligned_persons.example.csv")
        _write_example(aligned_topics, LAYERED_EXAMPLES_DIR / "aligned_topics.example.csv")
        _write_example(aligned_roles, LAYERED_EXAMPLES_DIR / "aligned_roles.example.csv")
        _write_example(aligned_organizations, LAYERED_EXAMPLES_DIR / "aligned_organizations.example.csv")

    gate_report = run_quality_gates()

    summary = {
        "run_id": run_id,
        "strict_mode": strict_mode,
        "write_examples": write_examples,
        "staged_files": int(len(staging_manifest)),
        "aligned_counts": {
            "broadcasting_programs": int(len(aligned_broadcasting_programs)),
            "seasons": int(len(aligned_seasons)),
            "episodes": int(len(aligned_episodes)),
            "persons": int(len(aligned_persons)),
            "topics": int(len(aligned_topics)),
            "roles": int(len(aligned_roles)),
            "organizations": int(len(aligned_organizations)),
        },
        "quality_gates": gate_report,
    }

    atomic_write_text(OUTPUT_FILES["run_summary"], json.dumps(summary, indent=2, ensure_ascii=True) + "\n")
    return summary


if __name__ == "__main__":
    result = run_phase31(overwrite_outputs=False, write_examples=True, strict_mode=True)
    print(json.dumps(result, indent=2, ensure_ascii=True))
