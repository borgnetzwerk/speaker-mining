from __future__ import annotations

from datetime import datetime, timezone
from datetime import timedelta
from pathlib import Path
import re
from urllib.parse import urljoin

import pandas as pd

from .config import FernsehserienRunConfig
from .event_store import FernsehserienEventStore
from .fetcher import FernsehserienFetcher
from .parser import (
    extract_neighbor_episode_urls,
    extract_episodenguide_urls,
    extract_first_episodenguide_url,
    extract_episode_urls,
    infer_episode_url_from_leaf_html,
    parse_episode_leaf_fields,
)
from .paths import FernsehserienPaths
from .projection import build_projections


def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _to_float_or_none(value: str) -> float | None:
    try:
        return float(value)
    except Exception:
        return None


def _is_budget_exhausted(*, max_network_calls: int, network_calls_used: int) -> bool:
    if int(max_network_calls) < 0:
        return False
    return network_calls_used >= int(max_network_calls)


def _normalize_duration_minutes(duration_raw: str) -> float | None:
    raw = str(duration_raw or "").strip().lower()
    if not raw:
        return None
    min_match = re.search(r"(\d+)\s*(min|minuten|minutes?)", raw)
    sec_match = re.search(r"(\d+)\s*(sek|sekunden|seconds?)", raw)
    if min_match:
        minutes = float(min_match.group(1))
        if sec_match:
            minutes += float(sec_match.group(1)) / 60.0
        return minutes
    only_num = re.search(r"(\d+)", raw)
    if only_num:
        return float(only_num.group(1))
    return None


def _normalize_date_german(raw_date: str) -> str:
    match = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", str(raw_date or ""))
    if not match:
        return ""
    day, month, year = match.group(1), match.group(2), match.group(3)
    return f"{year}-{month}-{day}"


def _known_episode_urls_for_program(event_store: FernsehserienEventStore, program_name: str) -> set[str]:
    known: set[str] = set()
    for event in event_store.iter_events():
        if str(event.get("event_type", "")) != "episode_url_discovered":
            continue
        payload = event.get("payload", {})
        if not isinstance(payload, dict):
            continue
        if str(payload.get("program_name", "")) != program_name:
            continue
        episode_url = str(payload.get("episode_url", "")).strip()
        if episode_url:
            known.add(episode_url)
    return known


def _already_extracted_episode_urls(event_store: FernsehserienEventStore, program_name: str) -> set[str]:
    extracted: set[str] = set()
    for event in event_store.iter_events():
        if str(event.get("event_type", "")) != "episode_description_discovered":
            continue
        payload = event.get("payload", {})
        if not isinstance(payload, dict):
            continue
        if str(payload.get("program_name", "")) != program_name:
            continue
        episode_url = str(payload.get("episode_url", "")).strip()
        if episode_url:
            extracted.add(episode_url)
    return extracted


def _import_legacy_cached_episode_urls(
    *,
    paths: FernsehserienPaths,
    event_store: FernsehserienEventStore,
    program_name: str,
    fernsehserien_de_id: str,
    known_episode_urls: set[str],
) -> int:
    imported = 0
    cache_dir = paths.cache_pages_dir
    if not cache_dir.exists():
        return imported

    slug = str(fernsehserien_de_id or "").strip("/")
    for cache_path in sorted(cache_dir.glob("*.html")):
        try:
            html = cache_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        inferred_url = infer_episode_url_from_leaf_html(html_text=html)
        if not inferred_url:
            continue
        if f"/{slug}/folgen/" not in inferred_url:
            continue
        if inferred_url in known_episode_urls:
            continue

        event_store.append(
            event_type="legacy_cache_page_imported",
            payload={
                "program_name": program_name,
                "fernsehserien_de_id": fernsehserien_de_id,
                "cache_path": str(cache_path),
                "inferred_episode_url": inferred_url,
                "imported_at_utc": _iso_now(),
            },
        )
        event_store.append(
            event_type="episode_url_discovered",
            payload={
                "program_name": program_name,
                "fernsehserien_de_id": fernsehserien_de_id,
                "episode_url": inferred_url,
                "discovery_path": "legacy_cache_import",
                "discovered_at_utc": _iso_now(),
            },
        )
        known_episode_urls.add(inferred_url)
        imported += 1

    return imported


def _emit_normalized_events(*, event_store: FernsehserienEventStore) -> int:
    description_discovered: dict[tuple[str, str], tuple[int, dict]] = {}
    guest_discovered: dict[tuple[str, str, int], tuple[int, dict]] = {}
    broadcast_discovered: dict[tuple[str, str, int], tuple[int, dict]] = {}

    description_normalized_sources: set[int] = set()
    guest_normalized_sources: set[int] = set()
    broadcast_normalized_sources: set[int] = set()

    for event in event_store.iter_events():
        sequence_num = int(event.get("sequence_num", 0) or 0)
        event_type = str(event.get("event_type", ""))
        payload = event.get("payload", {})
        if not isinstance(payload, dict):
            continue

        if event_type == "episode_description_discovered":
            key = (str(payload.get("program_name", "")), str(payload.get("episode_url", "")))
            description_discovered[key] = (sequence_num, payload)
        elif event_type == "episode_guest_discovered":
            key = (
                str(payload.get("program_name", "")),
                str(payload.get("episode_url", "")),
                int(payload.get("guest_order", 0) or 0),
            )
            guest_discovered[key] = (sequence_num, payload)
        elif event_type == "episode_broadcast_discovered":
            key = (
                str(payload.get("program_name", "")),
                str(payload.get("episode_url", "")),
                int(payload.get("broadcast_order", 0) or 0),
            )
            broadcast_discovered[key] = (sequence_num, payload)
        elif event_type == "episode_description_normalized":
            description_normalized_sources.add(int(payload.get("source_discovered_sequence", 0) or 0))
        elif event_type == "episode_guest_normalized":
            guest_normalized_sources.add(int(payload.get("source_discovered_sequence", 0) or 0))
        elif event_type == "episode_broadcast_normalized":
            broadcast_normalized_sources.add(int(payload.get("source_discovered_sequence", 0) or 0))

    emitted = 0

    for (_, _), (source_sequence, payload) in sorted(description_discovered.items(), key=lambda x: x[1][0]):
        if source_sequence in description_normalized_sources:
            continue
        duration_minutes = _normalize_duration_minutes(str(payload.get("duration_raw", "")))
        event_store.append(
            event_type="episode_description_normalized",
            payload={
                "program_name": str(payload.get("program_name", "")),
                "episode_url": str(payload.get("episode_url", "")),
                "episode_title": str(payload.get("episode_title_raw", "")).strip(),
                "duration_minutes": duration_minutes if duration_minutes is not None else "",
                "description_text": str(payload.get("description_raw_text", "")).strip(),
                "description_source": str(payload.get("description_source_raw", "")).strip(),
                "premiere_date": _normalize_date_german(str(payload.get("premiere_date_raw", ""))),
                "premiere_broadcaster": str(payload.get("premiere_broadcaster_raw", "")).strip(),
                "normalized_at_utc": _iso_now(),
                "normalizer_rule": "episode_description_norm_v1",
                "source_discovered_sequence": source_sequence,
            },
        )
        emitted += 1

    for (_, _, _), (source_sequence, payload) in sorted(guest_discovered.items(), key=lambda x: x[1][0]):
        if source_sequence in guest_normalized_sources:
            continue
        raw_url = str(payload.get("guest_url_raw", "")).strip()
        guest_url = urljoin("https://www.fernsehserien.de", raw_url) if raw_url else ""
        event_store.append(
            event_type="episode_guest_normalized",
            payload={
                "program_name": str(payload.get("program_name", "")),
                "episode_url": str(payload.get("episode_url", "")),
                "guest_name": str(payload.get("guest_name_raw", "")).strip(),
                "guest_role": str(payload.get("guest_role_raw", "")).strip(),
                "guest_description": str(payload.get("guest_description_raw", "")).strip(),
                "guest_url": guest_url,
                "guest_image_url": str(payload.get("guest_image_url_raw", "")).strip(),
                "guest_order": int(payload.get("guest_order", 0) or 0),
                "normalized_at_utc": _iso_now(),
                "normalizer_rule": "episode_guest_norm_v1",
                "source_discovered_sequence": source_sequence,
            },
        )
        emitted += 1

    for (_, _, _), (source_sequence, payload) in sorted(broadcast_discovered.items(), key=lambda x: x[1][0]):
        if source_sequence in broadcast_normalized_sources:
            continue
        start_dt = str(payload.get("broadcast_start_datetime_raw", "")).strip()
        end_dt = str(payload.get("broadcast_end_datetime_raw", "")).strip()
        start_date = ""
        start_time = ""
        end_date = ""
        end_time = ""
        tz_offset = ""
        spans_next_day = False
        try:
            start_obj = datetime.fromisoformat(start_dt)
            start_date = start_obj.date().isoformat()
            start_time = start_obj.strftime("%H:%M")
            tz_offset = start_obj.strftime("%z")
            if len(tz_offset) == 5:
                tz_offset = f"{tz_offset[:3]}:{tz_offset[3:]}"
            if end_dt:
                end_obj = datetime.fromisoformat(end_dt)
                if end_obj <= start_obj:
                    end_obj = end_obj + timedelta(days=1)
                    spans_next_day = True
                end_date = end_obj.date().isoformat()
                end_time = end_obj.strftime("%H:%M")
        except Exception:
            start_match = re.match(r"(?P<date>\d{4}-\d{2}-\d{2})T(?P<time>\d{2}:\d{2}):\d{2}(?P<tz>[+-]\d{2}:\d{2})", start_dt)
            end_match = re.match(r"(?P<date>\d{4}-\d{2}-\d{2})T(?P<time>\d{2}:\d{2}):\d{2}(?P<tz>[+-]\d{2}:\d{2})", end_dt)
            if start_match:
                start_date = start_match.group("date")
                start_time = start_match.group("time")
                tz_offset = start_match.group("tz")
            if end_match:
                end_date = end_match.group("date")
                end_time = end_match.group("time")
            if start_date and end_date and end_date > start_date:
                spans_next_day = True

        broadcaster_raw = str(payload.get("broadcast_broadcaster_raw", "")).strip()
        event_store.append(
            event_type="episode_broadcast_normalized",
            payload={
                "program_name": str(payload.get("program_name", "")),
                "episode_url": str(payload.get("episode_url", "")),
                "broadcast_date": start_date,
                "broadcast_start_time": start_time,
                "broadcast_end_date": end_date,
                "broadcast_end_time": end_time,
                "broadcast_timezone_offset": tz_offset,
                "broadcast_broadcaster": broadcaster_raw,
                "broadcast_broadcaster_key": broadcaster_raw.lower(),
                "broadcast_is_premiere": str(payload.get("broadcast_is_premiere_raw", "")).strip() != "",
                "broadcast_spans_next_day": spans_next_day,
                "broadcast_order": int(payload.get("broadcast_order", 0) or 0),
                "normalized_at_utc": _iso_now(),
                "normalizer_rule": "episode_broadcast_norm_v1",
                "source_discovered_sequence": source_sequence,
            },
        )
        emitted += 1

    return emitted


def _load_programs(repo_root: Path) -> pd.DataFrame:
    path = repo_root / "data" / "00_setup" / "broadcasting_programs.csv"
    if not path.exists():
        raise FileNotFoundError(f"Missing required input: {path}")
    programs = pd.read_csv(path)
    required_cols = {"wikibase_id", "wikidata_id", "fernsehserien_de_id"}
    missing = sorted(required_cols - set(programs.columns))
    if missing:
        raise ValueError(f"Missing required columns in broadcasting_programs.csv: {missing}")

    # The setup table currently uses label/filename fields; normalize a canonical name.
    if "name" not in programs.columns:
        if "label" in programs.columns:
            programs["name"] = programs["label"]
        elif "filename" in programs.columns:
            programs["name"] = programs["filename"]
        else:
            raise ValueError("broadcasting_programs.csv must include one of: name, label, filename")

    programs = programs.copy()
    programs["fernsehserien_de_id"] = programs["fernsehserien_de_id"].fillna("").astype(str).str.strip()
    programs = programs[programs["fernsehserien_de_id"] != ""]
    programs = programs[~programs["fernsehserien_de_id"].str.upper().isin({"NONE", "NULL", "NAN"})]
    return programs


def _select_programs(programs: pd.DataFrame, max_programs: int | None) -> pd.DataFrame:
    if max_programs is None:
        return programs
    return programs.head(int(max_programs))


def run_fernsehserien_extraction_phase(
    *,
    config: FernsehserienRunConfig,
    notebook_logger=None,
) -> dict:
    """Run extraction/discovery phase and emit *_discovered events."""
    repo_root = Path(config.repo_root)
    paths = FernsehserienPaths(repo_root=repo_root)
    paths.ensure()

    event_store = FernsehserienEventStore(paths)
    fetcher = FernsehserienFetcher(
        config=config,
        paths=paths,
        event_store=event_store,
        notebook_logger=notebook_logger,
    )

    event_store.append(
        event_type="eventstore_opened",
        payload={
            "opened_at_utc": _iso_now(),
            "phase": "extraction",
            "max_network_calls": int(config.max_network_calls),
            "max_programs": config.max_programs,
        },
    )

    programs = _load_programs(repo_root)
    selected = _select_programs(programs, config.max_programs)

    for _, row in selected.iterrows():
        program_name = str(row.get("name", "")).strip()
        fernsehserien_de_id = str(row.get("fernsehserien_de_id", "")).strip()
        root_url = f"https://www.fernsehserien.de/{fernsehserien_de_id}/"

        fetch = fetcher.fetch_url(
            url=root_url,
            phase="program_root_discovery",
            request_kind="program_root_html",
        )
        if fetch.status not in {"success", "cache_hit"}:
            continue

        root_event = event_store.append(
            event_type="program_root_discovered",
            payload={
                "program_name": program_name,
                "fernsehserien_de_id": fernsehserien_de_id,
                "root_url": root_url,
                "fetched_at_utc": fetch.fetched_at_utc,
            },
        )

        index_url = extract_first_episodenguide_url(html_text=fetch.content, root_url=root_url)
        if not index_url:
            continue

        seen_index_urls: set[str] = set()
        queue_index_urls: list[str] = [index_url]
        seen_episode_urls: set[str] = set(_known_episode_urls_for_program(event_store, program_name))
        _import_legacy_cached_episode_urls(
            paths=paths,
            event_store=event_store,
            program_name=program_name,
            fernsehserien_de_id=fernsehserien_de_id,
            known_episode_urls=seen_episode_urls,
        )
        parsed_episode_urls: set[str] = set(_already_extracted_episode_urls(event_store, program_name))
        fallback_pending = False

        # Priority-based loop: parse discovered episodes before discovering more.
        # This ensures leaf data extraction happens before discovery exhausts the budget.
        while True:
            # PRIORITY 1: Parse any discovered episodes that haven't been parsed yet.
            unparsed_urls = sorted(seen_episode_urls - parsed_episode_urls)
            for episode_url in unparsed_urls:
                if _is_budget_exhausted(max_network_calls=config.max_network_calls, network_calls_used=fetcher.network_calls_used):
                    break
                leaf_fetch = fetcher.fetch_url(
                    url=episode_url,
                    phase="episode_leaf_parsing",
                    request_kind="episode_leaf_html",
                )
                if leaf_fetch.status in {"success", "cache_hit"}:
                    parsed = parse_episode_leaf_fields(html_text=leaf_fetch.content)
                    event_store.append(
                        event_type="episode_description_discovered",
                        payload={
                            "program_name": program_name,
                            "episode_url": episode_url,
                            "episode_title_raw": str(parsed.get("episode_title_raw", parsed.get("episode_label", ""))),
                            "duration_raw": str(parsed.get("duration_raw", "")),
                            "description_raw_text": str(parsed.get("description_raw_text", parsed.get("description_text", ""))),
                            "description_source_raw": str(parsed.get("description_source_raw", "")),
                            "premiere_date_raw": str(parsed.get("premiere_date_raw", parsed.get("publication_text", ""))),
                            "premiere_broadcaster_raw": str(parsed.get("premiere_broadcaster_raw", "")),
                            "raw_extra_json": str(parsed.get("raw_extra_json", "{}")),
                            "parsed_at_utc": _iso_now(),
                            "parser_rule": str(parsed.get("parser_rule", "")),
                            "confidence": parsed.get("confidence", ""),
                        },
                    )

                    for guest in parsed.get("guests_raw", []):
                        if not isinstance(guest, dict):
                            continue
                        event_store.append(
                            event_type="episode_guest_discovered",
                            payload={
                                "program_name": program_name,
                                "episode_url": episode_url,
                                "guest_name_raw": str(guest.get("guest_name_raw", "")),
                                "guest_role_raw": str(guest.get("guest_role_raw", "")),
                                "guest_description_raw": str(guest.get("guest_description_raw", "")),
                                "guest_url_raw": str(guest.get("guest_url_raw", "")),
                                "guest_image_url_raw": str(guest.get("guest_image_url_raw", "")),
                                "guest_order": int(guest.get("guest_order", 0) or 0),
                                "parsed_at_utc": _iso_now(),
                                "parser_rule": str(parsed.get("parser_rule", "")),
                                "confidence": guest.get("confidence", parsed.get("confidence", "")),
                            },
                        )

                    for broadcast in parsed.get("broadcasts_raw", []):
                        if not isinstance(broadcast, dict):
                            continue
                        event_store.append(
                            event_type="episode_broadcast_discovered",
                            payload={
                                "program_name": program_name,
                                "episode_url": episode_url,
                                "broadcast_start_datetime_raw": str(broadcast.get("broadcast_start_datetime_raw", "")),
                                "broadcast_end_datetime_raw": str(broadcast.get("broadcast_end_datetime_raw", "")),
                                "broadcast_broadcaster_raw": str(broadcast.get("broadcast_broadcaster_raw", "")),
                                "broadcast_is_premiere_raw": str(broadcast.get("broadcast_is_premiere_raw", "")),
                                "broadcast_order": int(broadcast.get("broadcast_order", 0) or 0),
                                "parsed_at_utc": _iso_now(),
                                "parser_rule": str(parsed.get("parser_rule", "")),
                                "confidence": broadcast.get("confidence", parsed.get("confidence", "")),
                            },
                        )

                    if str(config.fallback_traversal_policy).strip().lower() == "on_gap":
                        for neighbor_url in extract_neighbor_episode_urls(html_text=leaf_fetch.content, base_url=episode_url):
                            if neighbor_url in seen_episode_urls:
                                continue
                            seen_episode_urls.add(neighbor_url)
                            fallback_pending = True
                            event_store.append(
                                event_type="episode_url_discovered",
                                payload={
                                    "program_name": program_name,
                                    "episode_url": neighbor_url,
                                    "discovery_path": "episode_chain_fallback",
                                    "discovered_at_utc": _iso_now(),
                                },
                            )
                parsed_episode_urls.add(episode_url)

            # Stop if out of budget.
            if _is_budget_exhausted(max_network_calls=config.max_network_calls, network_calls_used=fetcher.network_calls_used):
                break

            # PRIORITY 2: Discover more episodes only if parsing is caught up.
            if not queue_index_urls:
                break

            current_index_url = queue_index_urls.pop(0)
            if current_index_url in seen_index_urls:
                continue
            seen_index_urls.add(current_index_url)

            index_fetch = fetcher.fetch_url(
                url=current_index_url,
                phase="episode_index_discovery",
                request_kind="episodenguide_html",
            )
            if index_fetch.status not in {"success", "cache_hit"}:
                continue

            event_store.append(
                event_type="episode_index_page_discovered",
                payload={
                    "program_name": program_name,
                    "index_url": current_index_url,
                    "page_number": 1,
                    "fetched_at_utc": index_fetch.fetched_at_utc,
                    "discovery_path": "episodenguide_traversal",
                    "source_program_root_sequence": int(root_event.get("sequence_num", 0)),
                },
            )

            for episode_url in extract_episode_urls(html_text=index_fetch.content, base_url=current_index_url):
                if episode_url not in seen_episode_urls:
                    seen_episode_urls.add(episode_url)
                    event_store.append(
                        event_type="episode_url_discovered",
                        payload={
                            "program_name": program_name,
                            "episode_url": episode_url,
                            "discovery_path": "episodenguide",
                            "discovered_at_utc": _iso_now(),
                        },
                    )

            for next_index_url in extract_episodenguide_urls(html_text=index_fetch.content, base_url=current_index_url):
                if next_index_url not in seen_index_urls:
                    queue_index_urls.append(next_index_url)

            if fallback_pending:
                fallback_pending = False

    projection_result = build_projections(paths=paths, event_store=event_store)
    event_store.append(
        event_type="projection_checkpoint_written",
        payload={
            "written_at_utc": _iso_now(),
            "phase": "extraction",
            "summary_path": str(projection_result.summary_path),
            "summary": projection_result.summary,
        },
    )
    event_store.append(
        event_type="eventstore_closed",
        payload={
            "closed_at_utc": _iso_now(),
            "phase": "extraction",
            "network_calls_used": fetcher.network_calls_used,
        },
    )

    final_projection = build_projections(paths=paths, event_store=event_store)
    return {
        "phase": "extraction",
        "runtime_root": str(paths.runtime_root),
        "chunk_path": str(event_store.chunk_path),
        "summary_path": str(final_projection.summary_path),
        "summary": final_projection.summary,
        "network_calls_used": fetcher.network_calls_used,
        "max_network_calls": int(config.max_network_calls),
        "programs_processed": int(len(selected)),
    }


def run_fernsehserien_normalization_phase(*, config: FernsehserienRunConfig, notebook_logger=None) -> dict:
    """Normalize discovered events and emit *_normalized events only."""
    del notebook_logger
    repo_root = Path(config.repo_root)
    paths = FernsehserienPaths(repo_root=repo_root)
    paths.ensure()

    event_store = FernsehserienEventStore(paths)
    event_store.append(
        event_type="eventstore_opened",
        payload={
            "opened_at_utc": _iso_now(),
            "phase": "normalization",
            "max_network_calls": int(config.max_network_calls),
            "max_programs": config.max_programs,
        },
    )

    normalized_emitted = _emit_normalized_events(event_store=event_store)

    projection_result = build_projections(paths=paths, event_store=event_store)
    event_store.append(
        event_type="projection_checkpoint_written",
        payload={
            "written_at_utc": _iso_now(),
            "phase": "normalization",
            "summary_path": str(projection_result.summary_path),
            "summary": projection_result.summary,
        },
    )
    event_store.append(
        event_type="eventstore_closed",
        payload={
            "closed_at_utc": _iso_now(),
            "phase": "normalization",
            "network_calls_used": 0,
            "normalized_events_emitted": normalized_emitted,
        },
    )

    final_projection = build_projections(paths=paths, event_store=event_store)
    return {
        "phase": "normalization",
        "runtime_root": str(paths.runtime_root),
        "chunk_path": str(event_store.chunk_path),
        "summary_path": str(final_projection.summary_path),
        "summary": final_projection.summary,
        "normalized_events_emitted": normalized_emitted,
    }


def run_fernsehserien_pipeline(*, config: FernsehserienRunConfig, notebook_logger=None) -> dict:
    """Run extraction then normalization phases."""
    extraction = run_fernsehserien_extraction_phase(config=config, notebook_logger=notebook_logger)
    normalization = run_fernsehserien_normalization_phase(config=config, notebook_logger=notebook_logger)
    return {
        "phase": "pipeline",
        "extraction": extraction,
        "normalization": normalization,
        "runtime_root": normalization.get("runtime_root", extraction.get("runtime_root", "")),
        "chunk_path": normalization.get("chunk_path", extraction.get("chunk_path", "")),
        "summary_path": normalization.get("summary_path", extraction.get("summary_path", "")),
        "summary": normalization.get("summary", extraction.get("summary", {})),
        "network_calls_used": extraction.get("network_calls_used", 0),
        "max_network_calls": extraction.get("max_network_calls", int(config.max_network_calls)),
        "programs_processed": extraction.get("programs_processed", 0),
        "normalized_events_emitted": normalization.get("normalized_events_emitted", 0),
    }
