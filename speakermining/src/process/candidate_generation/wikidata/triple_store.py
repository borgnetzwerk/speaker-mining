from __future__ import annotations

import json
from pathlib import Path

from .cache import _atomic_write_text
from .common import canonical_pid, canonical_qid
from .event_log import build_triple_discovered_event
from .schemas import build_artifact_paths


_TRIPLE_EVENTS_CACHE: dict[str, list[dict]] = {}
_TRIPLE_EVENTS_DIRTY: set[str] = set()


def _load_events(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    return payload if isinstance(payload, list) else []


def _cache_key(path: Path) -> str:
    return str(Path(path).resolve())


def _cached_events(path: Path) -> list[dict]:
    cache_key = _cache_key(path)
    events = _TRIPLE_EVENTS_CACHE.get(cache_key)
    if events is None:
        events = _load_events(path)
        _TRIPLE_EVENTS_CACHE[cache_key] = events
    return events


def _mark_dirty(path: Path) -> None:
    _TRIPLE_EVENTS_DIRTY.add(_cache_key(path))


def flush_triple_events(repo_root: Path) -> None:
    paths = build_artifact_paths(Path(repo_root))
    cache_key = _cache_key(paths.triples_events_json)
    if cache_key not in _TRIPLE_EVENTS_DIRTY:
        return
    events = _TRIPLE_EVENTS_CACHE.get(cache_key)
    if events is None:
        return
    _atomic_write_text(paths.triples_events_json, json.dumps(events, ensure_ascii=False, indent=2))
    _TRIPLE_EVENTS_DIRTY.discard(cache_key)


def reset_triple_store_cache(repo_root: Path | None = None) -> None:
    if repo_root is None:
        _TRIPLE_EVENTS_CACHE.clear()
        _TRIPLE_EVENTS_DIRTY.clear()
        return
    paths = build_artifact_paths(Path(repo_root))
    cache_key = _cache_key(paths.triples_events_json)
    _TRIPLE_EVENTS_CACHE.pop(cache_key, None)
    _TRIPLE_EVENTS_DIRTY.discard(cache_key)


def record_item_edges(
    repo_root: Path,
    subject_qid: str,
    edges: list[dict],
    discovered_at_utc: str,
    source_query_file: str,
    event_emitter=None,
    event_phase: str | None = None,
) -> None:
    paths = build_artifact_paths(Path(repo_root))
    subject_qid = canonical_qid(subject_qid)
    if not subject_qid:
        return

    events = _cached_events(paths.triples_events_json)
    for edge in edges:
        pid = canonical_pid(edge.get("pid", ""))
        obj = canonical_qid(edge.get("to_qid", edge.get("object", "")))
        if not pid or not obj:
            continue
        events.append(
            {
                "subject": subject_qid,
                "predicate": pid,
                "object": obj,
                "discovered_at_utc": discovered_at_utc,
                "source_query_file": source_query_file,
            }
        )
        if callable(event_emitter):
            event_emitter(
                event_type="triple_discovered",
                phase=event_phase,
                message=f"triple discovered: {subject_qid} {pid} {obj}",
                entity={"qid": subject_qid},
                extra=build_triple_discovered_event(
                    subject_qid=subject_qid,
                    predicate_pid=pid,
                    object_qid=obj,
                    source_step="outlinks_build",
                    payload={"source_query_file": str(source_query_file or "")},
                ).get("payload", {}),
            )

    _mark_dirty(paths.triples_events_json)


def iter_unique_triples(repo_root: Path):
    paths = build_artifact_paths(Path(repo_root))
    events = _cached_events(paths.triples_events_json)
    dedup: dict[tuple[str, str, str], dict] = {}
    for event in events:
        key = (event.get("subject", ""), event.get("predicate", ""), event.get("object", ""))
        if key not in dedup:
            dedup[key] = event
    for key in sorted(dedup):
        yield dedup[key]


def has_direct_link_to_any_seed(repo_root: Path, candidate_qid: str, seed_qids: set[str]) -> bool:
    candidate = canonical_qid(candidate_qid)
    seeds = {canonical_qid(qid) for qid in (seed_qids or set()) if canonical_qid(qid)}
    if not candidate or not seeds:
        return False
    if candidate in seeds:
        return True

    for triple in iter_unique_triples(repo_root):
        subj = canonical_qid(triple.get("subject", ""))
        obj = canonical_qid(triple.get("object", ""))
        if not subj or not obj:
            continue
        if subj == candidate and obj in seeds:
            return True
        if obj == candidate and subj in seeds:
            return True
    return False
