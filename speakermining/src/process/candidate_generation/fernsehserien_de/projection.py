from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from process.io_guardrails import atomic_write_csv, atomic_write_text

from .event_store import FernsehserienEventStore
from .handler_progress import get_last_processed_sequence, keep_only_handlers, upsert_progress
from .paths import FernsehserienPaths


PROGRAM_PAGES_COLUMNS = [
    "fernsehserien_de_id",
    "program_name",
    "root_url",
    "fetched_at_utc",
    "source_event_sequence",
]

EPISODE_INDEX_COLUMNS = [
    "fernsehserien_de_id",
    "program_name",
    "index_url",
    "page_number",
    "fetched_at_utc",
    "source_event_sequence",
]

EPISODE_URL_COLUMNS = [
    "fernsehserien_de_id",
    "program_name",
    "episode_url",
    "discovery_path",
    "discovered_at_utc",
    "source_event_sequence",
]

EPISODE_METADATA_DISCOVERED_COLUMNS = [
    "fernsehserien_de_id",
    "program_name",
    "episode_url",
    "episode_title_raw",
    "duration_raw",
    "description_raw_text",
    "description_source_raw",
    "premiere_date_raw",
    "premiere_broadcaster_raw",
    "raw_extra_json",
    "parsed_at_utc",
    "parser_rule",
    "confidence",
    "source_event_sequence",
]

EPISODE_GUESTS_DISCOVERED_COLUMNS = [
    "fernsehserien_de_id",
    "program_name",
    "episode_url",
    "guest_name_raw",
    "guest_role_raw",
    "guest_description_raw",
    "guest_url_raw",
    "guest_image_url_raw",
    "guest_order",
    "parsed_at_utc",
    "parser_rule",
    "confidence",
    "source_event_sequence",
]

EPISODE_BROADCASTS_DISCOVERED_COLUMNS = [
    "fernsehserien_de_id",
    "program_name",
    "episode_url",
    "broadcast_start_datetime_raw",
    "broadcast_end_datetime_raw",
    "broadcast_broadcaster_raw",
    "broadcast_is_premiere_raw",
    "broadcast_order",
    "parsed_at_utc",
    "parser_rule",
    "confidence",
    "source_event_sequence",
]

EPISODE_METADATA_NORMALIZED_COLUMNS = [
    "fernsehserien_de_id",
    "program_name",
    "episode_url",
    "episode_title",
    "duration_minutes",
    "description_text",
    "description_source",
    "premiere_date",
    "premiere_broadcaster",
    "normalized_at_utc",
    "normalizer_rule",
    "source_discovered_sequence",
    "source_event_sequence",
]

EPISODE_GUESTS_NORMALIZED_COLUMNS = [
    "fernsehserien_de_id",
    "program_name",
    "episode_url",
    "guest_name",
    "guest_role",
    "guest_description",
    "guest_url",
    "guest_image_url",
    "guest_order",
    "normalized_at_utc",
    "normalizer_rule",
    "source_discovered_sequence",
    "source_event_sequence",
]

EPISODE_BROADCASTS_NORMALIZED_COLUMNS = [
    "fernsehserien_de_id",
    "program_name",
    "episode_url",
    "broadcast_date",
    "broadcast_start_time",
    "broadcast_end_date",
    "broadcast_end_time",
    "broadcast_timezone_offset",
    "broadcast_broadcaster",
    "broadcast_broadcaster_key",
    "broadcast_is_premiere",
    "broadcast_spans_next_day",
    "broadcast_order",
    "normalized_at_utc",
    "normalizer_rule",
    "source_discovered_sequence",
    "source_event_sequence",
]

PROGRAM_PAGES_HANDLER = "program_pages_handler"
EPISODE_INDEX_HANDLER = "episode_index_pages_handler"
EPISODE_URLS_HANDLER = "episode_urls_handler"
EPISODE_METADATA_DISCOVERED_HANDLER = "episode_metadata_discovered_handler"
EPISODE_GUESTS_DISCOVERED_HANDLER = "episode_guests_discovered_handler"
EPISODE_BROADCASTS_DISCOVERED_HANDLER = "episode_broadcasts_discovered_handler"
EPISODE_METADATA_NORMALIZED_HANDLER = "episode_metadata_normalized_handler"
EPISODE_GUESTS_NORMALIZED_HANDLER = "episode_guests_normalized_handler"
EPISODE_BROADCASTS_NORMALIZED_HANDLER = "episode_broadcasts_normalized_handler"

HANDLER_NAMES = {
    PROGRAM_PAGES_HANDLER,
    EPISODE_INDEX_HANDLER,
    EPISODE_URLS_HANDLER,
    EPISODE_METADATA_DISCOVERED_HANDLER,
    EPISODE_GUESTS_DISCOVERED_HANDLER,
    EPISODE_BROADCASTS_DISCOVERED_HANDLER,
    EPISODE_METADATA_NORMALIZED_HANDLER,
    EPISODE_GUESTS_NORMALIZED_HANDLER,
    EPISODE_BROADCASTS_NORMALIZED_HANDLER,
}


@dataclass(frozen=True)
class ProjectionWriteResult:
    program_pages_path: Path
    episode_index_pages_path: Path
    episode_urls_path: Path
    episode_metadata_discovered_path: Path
    episode_guests_discovered_path: Path
    episode_broadcasts_discovered_path: Path
    episode_metadata_normalized_path: Path
    episode_guests_normalized_path: Path
    episode_broadcasts_normalized_path: Path
    summary_path: Path
    summary: dict


def _to_frame(rows: list[dict], columns: list[str]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(rows).reindex(columns=columns)


def _load_existing_rows(path: Path, columns: list[str]) -> list[dict]:
    if not path.exists():
        return []
    try:
        df = pd.read_csv(path)
    except Exception:
        return []
    for column in columns:
        if column not in df.columns:
            df[column] = ""
    return df.reindex(columns=columns).to_dict(orient="records")


def _dedupe_rows(rows: list[dict], *, key_fields: list[str]) -> list[dict]:
    seen: set[tuple] = set()
    deduped: list[dict] = []
    for row in rows:
        key = tuple(row.get(field) for field in key_fields)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


def _program_identity_lookup(event_store: FernsehserienEventStore) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for event in event_store.iter_events():
        if str(event.get("event_type", "")) != "program_root_discovered":
            continue
        payload = event.get("payload", {})
        if not isinstance(payload, dict):
            continue
        program_name = str(payload.get("program_name", "")).strip()
        fernsehserien_de_id = str(payload.get("fernsehserien_de_id", "")).strip()
        if program_name and fernsehserien_de_id and program_name not in lookup:
            lookup[program_name] = fernsehserien_de_id
    return lookup


def _resolve_program_identity(payload: dict, lookup: dict[str, str]) -> tuple[str, str]:
    program_name = str(payload.get("program_name", "")).strip()
    fernsehserien_de_id = str(payload.get("fernsehserien_de_id", "")).strip()
    if not fernsehserien_de_id and program_name in lookup:
        fernsehserien_de_id = lookup[program_name]
    return fernsehserien_de_id, program_name


def build_projections(*, paths: FernsehserienPaths, event_store: FernsehserienEventStore) -> ProjectionWriteResult:
    paths.projections_dir.mkdir(parents=True, exist_ok=True)
    program_pages_path = paths.projections_dir / "program_pages.csv"
    episode_index_pages_path = paths.projections_dir / "episode_index_pages.csv"
    episode_urls_path = paths.projections_dir / "episode_urls.csv"
    episode_metadata_discovered_path = paths.projections_dir / "episode_metadata_discovered.csv"
    episode_guests_discovered_path = paths.projections_dir / "episode_guests_discovered.csv"
    episode_broadcasts_discovered_path = paths.projections_dir / "episode_broadcasts_discovered.csv"
    episode_metadata_normalized_path = paths.projections_dir / "episode_metadata_normalized.csv"
    episode_guests_normalized_path = paths.projections_dir / "episode_guests_normalized.csv"
    episode_broadcasts_normalized_path = paths.projections_dir / "episode_broadcasts_normalized.csv"
    summary_path = paths.projections_dir / "summary.json"

    last_program_pages_sequence = get_last_processed_sequence(paths.eventhandler_csv, PROGRAM_PAGES_HANDLER)
    last_episode_index_sequence = get_last_processed_sequence(paths.eventhandler_csv, EPISODE_INDEX_HANDLER)
    last_episode_urls_sequence = get_last_processed_sequence(paths.eventhandler_csv, EPISODE_URLS_HANDLER)
    last_episode_metadata_discovered_sequence = get_last_processed_sequence(paths.eventhandler_csv, EPISODE_METADATA_DISCOVERED_HANDLER)
    last_episode_guests_discovered_sequence = get_last_processed_sequence(paths.eventhandler_csv, EPISODE_GUESTS_DISCOVERED_HANDLER)
    last_episode_broadcasts_discovered_sequence = get_last_processed_sequence(paths.eventhandler_csv, EPISODE_BROADCASTS_DISCOVERED_HANDLER)
    last_episode_metadata_normalized_sequence = get_last_processed_sequence(paths.eventhandler_csv, EPISODE_METADATA_NORMALIZED_HANDLER)
    last_episode_guests_normalized_sequence = get_last_processed_sequence(paths.eventhandler_csv, EPISODE_GUESTS_NORMALIZED_HANDLER)
    last_episode_broadcasts_normalized_sequence = get_last_processed_sequence(paths.eventhandler_csv, EPISODE_BROADCASTS_NORMALIZED_HANDLER)

    keep_only_handlers(paths.eventhandler_csv, HANDLER_NAMES)

    program_pages = _load_existing_rows(program_pages_path, PROGRAM_PAGES_COLUMNS)
    episode_index_pages = _load_existing_rows(episode_index_pages_path, EPISODE_INDEX_COLUMNS)
    episode_urls = _load_existing_rows(episode_urls_path, EPISODE_URL_COLUMNS)
    episode_metadata_discovered = _load_existing_rows(episode_metadata_discovered_path, EPISODE_METADATA_DISCOVERED_COLUMNS)
    episode_guests_discovered = _load_existing_rows(episode_guests_discovered_path, EPISODE_GUESTS_DISCOVERED_COLUMNS)
    episode_broadcasts_discovered = _load_existing_rows(episode_broadcasts_discovered_path, EPISODE_BROADCASTS_DISCOVERED_COLUMNS)
    episode_metadata_normalized = _load_existing_rows(episode_metadata_normalized_path, EPISODE_METADATA_NORMALIZED_COLUMNS)
    episode_guests_normalized = _load_existing_rows(episode_guests_normalized_path, EPISODE_GUESTS_NORMALIZED_COLUMNS)
    episode_broadcasts_normalized = _load_existing_rows(episode_broadcasts_normalized_path, EPISODE_BROADCASTS_NORMALIZED_COLUMNS)
    program_identity_by_name = _program_identity_lookup(event_store)

    total_events = 0
    max_sequence = 0
    processed_events_per_handler = {
        PROGRAM_PAGES_HANDLER: 0,
        EPISODE_INDEX_HANDLER: 0,
        EPISODE_URLS_HANDLER: 0,
        EPISODE_METADATA_DISCOVERED_HANDLER: 0,
        EPISODE_GUESTS_DISCOVERED_HANDLER: 0,
        EPISODE_BROADCASTS_DISCOVERED_HANDLER: 0,
        EPISODE_METADATA_NORMALIZED_HANDLER: 0,
        EPISODE_GUESTS_NORMALIZED_HANDLER: 0,
        EPISODE_BROADCASTS_NORMALIZED_HANDLER: 0,
    }

    for event in event_store.iter_events():
        total_events += 1
        sequence_num = int(event.get("sequence_num", 0) or 0)
        if sequence_num > max_sequence:
            max_sequence = sequence_num
        event_type = str(event.get("event_type", ""))
        payload = event.get("payload", {})
        if not isinstance(payload, dict):
            continue

        if event_type == "program_root_discovered" and sequence_num > last_program_pages_sequence:
            processed_events_per_handler[PROGRAM_PAGES_HANDLER] += 1
            fernsehserien_de_id, program_name = _resolve_program_identity(payload, program_identity_by_name)
            program_pages.append(
                {
                    "fernsehserien_de_id": fernsehserien_de_id,
                    "program_name": program_name,
                    "root_url": str(payload.get("root_url", "")),
                    "fetched_at_utc": str(payload.get("fetched_at_utc", "")),
                    "source_event_sequence": sequence_num,
                }
            )
        elif event_type == "episode_index_page_discovered" and sequence_num > last_episode_index_sequence:
            processed_events_per_handler[EPISODE_INDEX_HANDLER] += 1
            fernsehserien_de_id, program_name = _resolve_program_identity(payload, program_identity_by_name)
            episode_index_pages.append(
                {
                    "fernsehserien_de_id": fernsehserien_de_id,
                    "program_name": program_name,
                    "index_url": str(payload.get("index_url", "")),
                    "page_number": payload.get("page_number", ""),
                    "fetched_at_utc": str(payload.get("fetched_at_utc", "")),
                    "source_event_sequence": sequence_num,
                }
            )
        elif event_type == "episode_url_discovered" and sequence_num > last_episode_urls_sequence:
            processed_events_per_handler[EPISODE_URLS_HANDLER] += 1
            fernsehserien_de_id, program_name = _resolve_program_identity(payload, program_identity_by_name)
            episode_urls.append(
                {
                    "fernsehserien_de_id": fernsehserien_de_id,
                    "program_name": program_name,
                    "episode_url": str(payload.get("episode_url", "")),
                    "discovery_path": str(payload.get("discovery_path", "")),
                    "discovered_at_utc": str(payload.get("discovered_at_utc", "")),
                    "source_event_sequence": sequence_num,
                }
            )
        elif event_type == "episode_description_discovered" and sequence_num > last_episode_metadata_discovered_sequence:
            processed_events_per_handler[EPISODE_METADATA_DISCOVERED_HANDLER] += 1
            fernsehserien_de_id, program_name = _resolve_program_identity(payload, program_identity_by_name)
            episode_metadata_discovered.append(
                {
                    "fernsehserien_de_id": fernsehserien_de_id,
                    "program_name": program_name,
                    "episode_url": str(payload.get("episode_url", "")),
                    "episode_title_raw": str(payload.get("episode_title_raw", "")),
                    "duration_raw": str(payload.get("duration_raw", "")),
                    "description_raw_text": str(payload.get("description_raw_text", "")),
                    "description_source_raw": str(payload.get("description_source_raw", "")),
                    "premiere_date_raw": str(payload.get("premiere_date_raw", "")),
                    "premiere_broadcaster_raw": str(payload.get("premiere_broadcaster_raw", "")),
                    "raw_extra_json": str(payload.get("raw_extra_json", "{}")),
                    "parsed_at_utc": str(payload.get("parsed_at_utc", "")),
                    "parser_rule": str(payload.get("parser_rule", "")),
                    "confidence": payload.get("confidence", ""),
                    "source_event_sequence": sequence_num,
                }
            )
        elif event_type == "episode_guest_discovered" and sequence_num > last_episode_guests_discovered_sequence:
            processed_events_per_handler[EPISODE_GUESTS_DISCOVERED_HANDLER] += 1
            fernsehserien_de_id, program_name = _resolve_program_identity(payload, program_identity_by_name)
            episode_guests_discovered.append(
                {
                    "fernsehserien_de_id": fernsehserien_de_id,
                    "program_name": program_name,
                    "episode_url": str(payload.get("episode_url", "")),
                    "guest_name_raw": str(payload.get("guest_name_raw", "")),
                    "guest_role_raw": str(payload.get("guest_role_raw", "")),
                    "guest_description_raw": str(payload.get("guest_description_raw", "")),
                    "guest_url_raw": str(payload.get("guest_url_raw", "")),
                    "guest_image_url_raw": str(payload.get("guest_image_url_raw", "")),
                    "guest_order": int(payload.get("guest_order", 0) or 0),
                    "parsed_at_utc": str(payload.get("parsed_at_utc", "")),
                    "parser_rule": str(payload.get("parser_rule", "")),
                    "confidence": payload.get("confidence", ""),
                    "source_event_sequence": sequence_num,
                }
            )
        elif event_type == "episode_broadcast_discovered" and sequence_num > last_episode_broadcasts_discovered_sequence:
            processed_events_per_handler[EPISODE_BROADCASTS_DISCOVERED_HANDLER] += 1
            fernsehserien_de_id, program_name = _resolve_program_identity(payload, program_identity_by_name)
            episode_broadcasts_discovered.append(
                {
                    "fernsehserien_de_id": fernsehserien_de_id,
                    "program_name": program_name,
                    "episode_url": str(payload.get("episode_url", "")),
                    "broadcast_start_datetime_raw": str(payload.get("broadcast_start_datetime_raw", "")),
                    "broadcast_end_datetime_raw": str(payload.get("broadcast_end_datetime_raw", "")),
                    "broadcast_broadcaster_raw": str(payload.get("broadcast_broadcaster_raw", "")),
                    "broadcast_is_premiere_raw": str(payload.get("broadcast_is_premiere_raw", "")),
                    "broadcast_order": int(payload.get("broadcast_order", 0) or 0),
                    "parsed_at_utc": str(payload.get("parsed_at_utc", "")),
                    "parser_rule": str(payload.get("parser_rule", "")),
                    "confidence": payload.get("confidence", ""),
                    "source_event_sequence": sequence_num,
                }
            )
        elif event_type == "episode_description_normalized" and sequence_num > last_episode_metadata_normalized_sequence:
            processed_events_per_handler[EPISODE_METADATA_NORMALIZED_HANDLER] += 1
            fernsehserien_de_id, program_name = _resolve_program_identity(payload, program_identity_by_name)
            episode_metadata_normalized.append(
                {
                    "fernsehserien_de_id": fernsehserien_de_id,
                    "program_name": program_name,
                    "episode_url": str(payload.get("episode_url", "")),
                    "episode_title": str(payload.get("episode_title", "")),
                    "duration_minutes": payload.get("duration_minutes", ""),
                    "description_text": str(payload.get("description_text", "")),
                    "description_source": str(payload.get("description_source", "")),
                    "premiere_date": str(payload.get("premiere_date", "")),
                    "premiere_broadcaster": str(payload.get("premiere_broadcaster", "")),
                    "normalized_at_utc": str(payload.get("normalized_at_utc", "")),
                    "normalizer_rule": str(payload.get("normalizer_rule", "")),
                    "source_discovered_sequence": int(payload.get("source_discovered_sequence", 0) or 0),
                    "source_event_sequence": sequence_num,
                }
            )
        elif event_type == "episode_guest_normalized" and sequence_num > last_episode_guests_normalized_sequence:
            processed_events_per_handler[EPISODE_GUESTS_NORMALIZED_HANDLER] += 1
            fernsehserien_de_id, program_name = _resolve_program_identity(payload, program_identity_by_name)
            episode_guests_normalized.append(
                {
                    "fernsehserien_de_id": fernsehserien_de_id,
                    "program_name": program_name,
                    "episode_url": str(payload.get("episode_url", "")),
                    "guest_name": str(payload.get("guest_name", "")),
                    "guest_role": str(payload.get("guest_role", "")),
                    "guest_description": str(payload.get("guest_description", "")),
                    "guest_url": str(payload.get("guest_url", "")),
                    "guest_image_url": str(payload.get("guest_image_url", "")),
                    "guest_order": int(payload.get("guest_order", 0) or 0),
                    "normalized_at_utc": str(payload.get("normalized_at_utc", "")),
                    "normalizer_rule": str(payload.get("normalizer_rule", "")),
                    "source_discovered_sequence": int(payload.get("source_discovered_sequence", 0) or 0),
                    "source_event_sequence": sequence_num,
                }
            )
        elif event_type == "episode_broadcast_normalized" and sequence_num > last_episode_broadcasts_normalized_sequence:
            processed_events_per_handler[EPISODE_BROADCASTS_NORMALIZED_HANDLER] += 1
            fernsehserien_de_id, program_name = _resolve_program_identity(payload, program_identity_by_name)
            episode_broadcasts_normalized.append(
                {
                    "fernsehserien_de_id": fernsehserien_de_id,
                    "program_name": program_name,
                    "episode_url": str(payload.get("episode_url", "")),
                    "broadcast_date": str(payload.get("broadcast_date", "")),
                    "broadcast_start_time": str(payload.get("broadcast_start_time", "")),
                    "broadcast_end_date": str(payload.get("broadcast_end_date", "")),
                    "broadcast_end_time": str(payload.get("broadcast_end_time", "")),
                    "broadcast_timezone_offset": str(payload.get("broadcast_timezone_offset", "")),
                    "broadcast_broadcaster": str(payload.get("broadcast_broadcaster", "")),
                    "broadcast_broadcaster_key": str(payload.get("broadcast_broadcaster_key", "")),
                    "broadcast_is_premiere": payload.get("broadcast_is_premiere", False),
                    "broadcast_spans_next_day": payload.get("broadcast_spans_next_day", False),
                    "broadcast_order": int(payload.get("broadcast_order", 0) or 0),
                    "normalized_at_utc": str(payload.get("normalized_at_utc", "")),
                    "normalizer_rule": str(payload.get("normalizer_rule", "")),
                    "source_discovered_sequence": int(payload.get("source_discovered_sequence", 0) or 0),
                    "source_event_sequence": sequence_num,
                }
            )

    episode_index_pages = _dedupe_rows(
        episode_index_pages,
        key_fields=["fernsehserien_de_id", "index_url"],
    )
    episode_urls = _dedupe_rows(
        episode_urls,
        key_fields=["fernsehserien_de_id", "episode_url"],
    )
    program_pages = _dedupe_rows(
        program_pages,
        key_fields=["fernsehserien_de_id", "root_url"],
    )
    episode_metadata_discovered = _dedupe_rows(
        episode_metadata_discovered,
        key_fields=["fernsehserien_de_id", "episode_url", "source_event_sequence"],
    )
    episode_guests_discovered = _dedupe_rows(
        episode_guests_discovered,
        key_fields=["fernsehserien_de_id", "episode_url", "guest_order", "source_event_sequence"],
    )
    episode_broadcasts_discovered = _dedupe_rows(
        episode_broadcasts_discovered,
        key_fields=["fernsehserien_de_id", "episode_url", "broadcast_order", "source_event_sequence"],
    )
    episode_metadata_normalized = _dedupe_rows(
        episode_metadata_normalized,
        key_fields=["fernsehserien_de_id", "episode_url", "source_discovered_sequence"],
    )
    episode_guests_normalized = _dedupe_rows(
        episode_guests_normalized,
        key_fields=["fernsehserien_de_id", "episode_url", "guest_order", "source_discovered_sequence"],
    )
    episode_broadcasts_normalized = _dedupe_rows(
        episode_broadcasts_normalized,
        key_fields=["fernsehserien_de_id", "episode_url", "broadcast_order", "source_discovered_sequence"],
    )

    atomic_write_csv(program_pages_path, _to_frame(program_pages, PROGRAM_PAGES_COLUMNS), index=False)
    atomic_write_csv(episode_index_pages_path, _to_frame(episode_index_pages, EPISODE_INDEX_COLUMNS), index=False)
    atomic_write_csv(episode_urls_path, _to_frame(episode_urls, EPISODE_URL_COLUMNS), index=False)
    atomic_write_csv(
        episode_metadata_discovered_path,
        _to_frame(episode_metadata_discovered, EPISODE_METADATA_DISCOVERED_COLUMNS),
        index=False,
    )
    atomic_write_csv(
        episode_guests_discovered_path,
        _to_frame(episode_guests_discovered, EPISODE_GUESTS_DISCOVERED_COLUMNS),
        index=False,
    )
    atomic_write_csv(
        episode_broadcasts_discovered_path,
        _to_frame(episode_broadcasts_discovered, EPISODE_BROADCASTS_DISCOVERED_COLUMNS),
        index=False,
    )
    atomic_write_csv(
        episode_metadata_normalized_path,
        _to_frame(episode_metadata_normalized, EPISODE_METADATA_NORMALIZED_COLUMNS),
        index=False,
    )
    atomic_write_csv(
        episode_guests_normalized_path,
        _to_frame(episode_guests_normalized, EPISODE_GUESTS_NORMALIZED_COLUMNS),
        index=False,
    )
    atomic_write_csv(
        episode_broadcasts_normalized_path,
        _to_frame(episode_broadcasts_normalized, EPISODE_BROADCASTS_NORMALIZED_COLUMNS),
        index=False,
    )

    last_program_pages_after = max(max_sequence, last_program_pages_sequence)
    last_episode_index_after = max(max_sequence, last_episode_index_sequence)
    last_episode_urls_after = max(max_sequence, last_episode_urls_sequence)
    last_episode_metadata_discovered_after = max(max_sequence, last_episode_metadata_discovered_sequence)
    last_episode_guests_discovered_after = max(max_sequence, last_episode_guests_discovered_sequence)
    last_episode_broadcasts_discovered_after = max(max_sequence, last_episode_broadcasts_discovered_sequence)
    last_episode_metadata_normalized_after = max(max_sequence, last_episode_metadata_normalized_sequence)
    last_episode_guests_normalized_after = max(max_sequence, last_episode_guests_normalized_sequence)
    last_episode_broadcasts_normalized_after = max(max_sequence, last_episode_broadcasts_normalized_sequence)

    upsert_progress(
        paths.eventhandler_csv,
        handler_name=PROGRAM_PAGES_HANDLER,
        last_processed_sequence=last_program_pages_after,
        artifact_path=str(program_pages_path),
    )
    upsert_progress(
        paths.eventhandler_csv,
        handler_name=EPISODE_INDEX_HANDLER,
        last_processed_sequence=last_episode_index_after,
        artifact_path=str(episode_index_pages_path),
    )
    upsert_progress(
        paths.eventhandler_csv,
        handler_name=EPISODE_URLS_HANDLER,
        last_processed_sequence=last_episode_urls_after,
        artifact_path=str(episode_urls_path),
    )
    upsert_progress(
        paths.eventhandler_csv,
        handler_name=EPISODE_METADATA_DISCOVERED_HANDLER,
        last_processed_sequence=last_episode_metadata_discovered_after,
        artifact_path=str(episode_metadata_discovered_path),
    )
    upsert_progress(
        paths.eventhandler_csv,
        handler_name=EPISODE_GUESTS_DISCOVERED_HANDLER,
        last_processed_sequence=last_episode_guests_discovered_after,
        artifact_path=str(episode_guests_discovered_path),
    )
    upsert_progress(
        paths.eventhandler_csv,
        handler_name=EPISODE_BROADCASTS_DISCOVERED_HANDLER,
        last_processed_sequence=last_episode_broadcasts_discovered_after,
        artifact_path=str(episode_broadcasts_discovered_path),
    )
    upsert_progress(
        paths.eventhandler_csv,
        handler_name=EPISODE_METADATA_NORMALIZED_HANDLER,
        last_processed_sequence=last_episode_metadata_normalized_after,
        artifact_path=str(episode_metadata_normalized_path),
    )
    upsert_progress(
        paths.eventhandler_csv,
        handler_name=EPISODE_GUESTS_NORMALIZED_HANDLER,
        last_processed_sequence=last_episode_guests_normalized_after,
        artifact_path=str(episode_guests_normalized_path),
    )
    upsert_progress(
        paths.eventhandler_csv,
        handler_name=EPISODE_BROADCASTS_NORMALIZED_HANDLER,
        last_processed_sequence=last_episode_broadcasts_normalized_after,
        artifact_path=str(episode_broadcasts_normalized_path),
    )

    processed_events_this_run = int(sum(processed_events_per_handler.values()))

    summary = {
        "total_events": total_events,
        "max_sequence": max_sequence,
        "processed_events_this_run": processed_events_this_run,
        "handler_progress_before": {
            PROGRAM_PAGES_HANDLER: last_program_pages_sequence,
            EPISODE_INDEX_HANDLER: last_episode_index_sequence,
            EPISODE_URLS_HANDLER: last_episode_urls_sequence,
            EPISODE_METADATA_DISCOVERED_HANDLER: last_episode_metadata_discovered_sequence,
            EPISODE_GUESTS_DISCOVERED_HANDLER: last_episode_guests_discovered_sequence,
            EPISODE_BROADCASTS_DISCOVERED_HANDLER: last_episode_broadcasts_discovered_sequence,
            EPISODE_METADATA_NORMALIZED_HANDLER: last_episode_metadata_normalized_sequence,
            EPISODE_GUESTS_NORMALIZED_HANDLER: last_episode_guests_normalized_sequence,
            EPISODE_BROADCASTS_NORMALIZED_HANDLER: last_episode_broadcasts_normalized_sequence,
        },
        "handler_progress_after": {
            PROGRAM_PAGES_HANDLER: last_program_pages_after,
            EPISODE_INDEX_HANDLER: last_episode_index_after,
            EPISODE_URLS_HANDLER: last_episode_urls_after,
            EPISODE_METADATA_DISCOVERED_HANDLER: last_episode_metadata_discovered_after,
            EPISODE_GUESTS_DISCOVERED_HANDLER: last_episode_guests_discovered_after,
            EPISODE_BROADCASTS_DISCOVERED_HANDLER: last_episode_broadcasts_discovered_after,
            EPISODE_METADATA_NORMALIZED_HANDLER: last_episode_metadata_normalized_after,
            EPISODE_GUESTS_NORMALIZED_HANDLER: last_episode_guests_normalized_after,
            EPISODE_BROADCASTS_NORMALIZED_HANDLER: last_episode_broadcasts_normalized_after,
        },
        "processed_events_per_handler": processed_events_per_handler,
        "eventhandler_path": str(paths.eventhandler_csv),
        "program_pages_rows": len(program_pages),
        "episode_index_rows": len(episode_index_pages),
        "episode_urls_rows": len(episode_urls),
        "episode_metadata_discovered_rows": len(episode_metadata_discovered),
        "episode_guests_discovered_rows": len(episode_guests_discovered),
        "episode_broadcasts_discovered_rows": len(episode_broadcasts_discovered),
        "episode_metadata_normalized_rows": len(episode_metadata_normalized),
        "episode_guests_normalized_rows": len(episode_guests_normalized),
        "episode_broadcasts_normalized_rows": len(episode_broadcasts_normalized),
    }
    atomic_write_text(summary_path, json.dumps(summary, ensure_ascii=False, indent=2) + "\n")

    return ProjectionWriteResult(
        program_pages_path=program_pages_path,
        episode_index_pages_path=episode_index_pages_path,
        episode_urls_path=episode_urls_path,
        episode_metadata_discovered_path=episode_metadata_discovered_path,
        episode_guests_discovered_path=episode_guests_discovered_path,
        episode_broadcasts_discovered_path=episode_broadcasts_discovered_path,
        episode_metadata_normalized_path=episode_metadata_normalized_path,
        episode_guests_normalized_path=episode_guests_normalized_path,
        episode_broadcasts_normalized_path=episode_broadcasts_normalized_path,
        summary_path=summary_path,
        summary=summary,
    )
