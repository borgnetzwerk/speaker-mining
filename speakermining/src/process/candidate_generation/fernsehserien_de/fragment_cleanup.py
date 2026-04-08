from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
import shutil
from urllib.parse import urlsplit, urlunsplit

import pandas as pd

from process.io_guardrails import atomic_write_csv

from .event_store import FernsehserienEventStore
from .paths import FernsehserienPaths


def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _canonicalize_url(url: str) -> str:
    split = urlsplit(str(url or "").strip())
    return urlunsplit((split.scheme, split.netloc, split.path, split.query, ""))


def _fragment_of(url: str) -> str:
    return urlsplit(str(url or "").strip()).fragment.strip()


def _cache_path_for_url(paths: FernsehserienPaths, url: str) -> Path:
    key = hashlib.md5(str(url).encode("utf-8")).hexdigest()
    return paths.cache_pages_dir / f"{key}.html"


def apply_fragment_url_cleanup(*, paths: FernsehserienPaths, event_store: FernsehserienEventStore) -> dict:
    """Archive and remove fragment URL cache artifacts; promote canonical cache when missing.

    This cleanup is safe for append-only event history: events are not deleted. Instead,
    cache and projections are repaired so fragment duplicates do not keep propagating.
    """
    affected_network_events: list[dict] = []
    observed_fragments: set[str] = set()

    for event in event_store.iter_events():
        event_type = str(event.get("event_type", ""))
        if event_type not in {"network_request_performed", "network_request_skipped_cache_hit"}:
            continue
        payload = event.get("payload", {})
        if not isinstance(payload, dict):
            continue
        raw_url = str(payload.get("url", "")).strip()
        fragment = _fragment_of(raw_url)
        if not fragment:
            continue
        observed_fragments.add(fragment)
        affected_network_events.append(
            {
                "sequence_num": int(event.get("sequence_num", 0) or 0),
                "event_type": event_type,
                "url": raw_url,
                "canonical_url": _canonicalize_url(raw_url),
                "fragment": fragment,
                "cache_path": str(payload.get("cache_path", "")).strip(),
            }
        )

    if not affected_network_events:
        return {
            "affected_network_events": 0,
            "fragments": [],
            "archive_dir": "",
            "manifest_path": "",
            "promoted_to_canonical": 0,
            "removed_fragment_cache_files": 0,
        }

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive_dir = paths.runtime_root / "archive" / "fragment_cache" / ts
    archive_dir.mkdir(parents=True, exist_ok=True)

    manifest_rows: list[dict] = []
    promoted_to_canonical = 0
    removed_fragment_cache_files = 0

    for item in affected_network_events:
        cache_path_str = str(item.get("cache_path", "")).strip()
        cache_path = Path(cache_path_str) if cache_path_str else Path()
        canonical_cache_path = _cache_path_for_url(paths, str(item.get("canonical_url", "")))

        action = "no_cache_file"
        archived_path = ""

        if cache_path_str and cache_path.exists() and cache_path.is_file():
            archived_path_obj = archive_dir / cache_path.name
            if not archived_path_obj.exists():
                shutil.copy2(cache_path, archived_path_obj)
            archived_path = str(archived_path_obj)

            if not canonical_cache_path.exists():
                canonical_cache_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(cache_path, canonical_cache_path)
                promoted_to_canonical += 1
                action = "archived_and_promoted_to_canonical"
            else:
                action = "archived_duplicate_removed"

            cache_path.unlink(missing_ok=True)
            removed_fragment_cache_files += 1

        manifest_rows.append(
            {
                "sequence_num": int(item.get("sequence_num", 0)),
                "event_type": str(item.get("event_type", "")),
                "url": str(item.get("url", "")),
                "canonical_url": str(item.get("canonical_url", "")),
                "fragment": str(item.get("fragment", "")),
                "cache_path": cache_path_str,
                "canonical_cache_path": str(canonical_cache_path),
                "archived_path": archived_path,
                "action": action,
                "cleaned_at_utc": _iso_now(),
            }
        )

    diagnostics_dir = paths.runtime_root / "diagnostics"
    diagnostics_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = diagnostics_dir / f"url_fragment_cleanup_{ts}.csv"
    atomic_write_csv(manifest_path, pd.DataFrame(manifest_rows), index=False)

    event_store.append(
        event_type="url_fragment_cleanup_applied",
        payload={
            "cleaned_at_utc": _iso_now(),
            "affected_network_events": int(len(affected_network_events)),
            "fragments": sorted(observed_fragments),
            "archive_dir": str(archive_dir),
            "manifest_path": str(manifest_path),
            "promoted_to_canonical": int(promoted_to_canonical),
            "removed_fragment_cache_files": int(removed_fragment_cache_files),
        },
    )

    return {
        "affected_network_events": int(len(affected_network_events)),
        "fragments": sorted(observed_fragments),
        "archive_dir": str(archive_dir),
        "manifest_path": str(manifest_path),
        "promoted_to_canonical": int(promoted_to_canonical),
        "removed_fragment_cache_files": int(removed_fragment_cache_files),
    }
