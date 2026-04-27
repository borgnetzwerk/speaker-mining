from __future__ import annotations

from pathlib import Path

import pandas as pd

from .cache import _atomic_write_df
from .common import canonical_pid, canonical_qid
from .event_log import build_triple_discovered_event
from .schemas import build_artifact_paths


_TRIPLE_EVENTS_CACHE: dict[str, list[dict]] = {}
_TRIPLE_EVENTS_DIRTY: set[str] = set()

_TRIPLE_COLUMNS = [
    "subject",
    "predicate",
    "object",
    "discovered_at_utc",
    "source_query_file",
]


def _sanitize_events(rows: list[dict]) -> list[dict]:
    out: list[dict] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        subject = canonical_qid(row.get("subject", ""))
        predicate = canonical_pid(row.get("predicate", ""))
        obj = canonical_qid(row.get("object", ""))
        if not subject or not predicate or not obj:
            continue
        out.append(
            {
                "subject": subject,
                "predicate": predicate,
                "object": obj,
                "discovered_at_utc": str(row.get("discovered_at_utc", "") or ""),
                "source_query_file": str(row.get("source_query_file", "") or ""),
            }
        )
    return out


def _load_events(paths) -> list[dict]:
    # Projection-first storage: triples.csv is the active runtime source.
    if paths.triples_csv.exists():
        try:
            df = pd.read_csv(paths.triples_csv)
            return _sanitize_events(df.to_dict(orient="records"))
        except Exception:
            pass

    return []


def _cache_key(path: Path) -> str:
    return str(Path(path).resolve())


def _storage_path(paths) -> Path:
    return paths.triples_csv


def _cached_events(paths) -> list[dict]:
    storage_path = _storage_path(paths)
    cache_key = _cache_key(storage_path)
    events = _TRIPLE_EVENTS_CACHE.get(cache_key)
    if events is None:
        events = _load_events(paths)
        _TRIPLE_EVENTS_CACHE[cache_key] = events
    return events


def _mark_dirty(path: Path) -> None:
    _TRIPLE_EVENTS_DIRTY.add(_cache_key(path))


def flush_triple_events(repo_root: Path) -> None:
    paths = build_artifact_paths(Path(repo_root))
    storage_path = _storage_path(paths)
    cache_key = _cache_key(storage_path)
    if cache_key not in _TRIPLE_EVENTS_DIRTY:
        return
    events = _TRIPLE_EVENTS_CACHE.get(cache_key)
    if events is None:
        return
    dedup: dict[tuple[str, str, str], dict] = {}
    for event in events:
        key = (
            str(event.get("subject", "") or ""),
            str(event.get("predicate", "") or ""),
            str(event.get("object", "") or ""),
        )
        if key not in dedup:
            dedup[key] = {
                "subject": key[0],
                "predicate": key[1],
                "object": key[2],
                "discovered_at_utc": str(event.get("discovered_at_utc", "") or ""),
                "source_query_file": str(event.get("source_query_file", "") or ""),
            }

    rows = [dedup[key] for key in sorted(dedup)]
    frame = pd.DataFrame(rows, columns=_TRIPLE_COLUMNS)
    _atomic_write_df(paths.triples_csv, frame)
    _TRIPLE_EVENTS_DIRTY.discard(cache_key)


def reset_triple_store_cache(repo_root: Path | None = None) -> None:
    if repo_root is None:
        _TRIPLE_EVENTS_CACHE.clear()
        _TRIPLE_EVENTS_DIRTY.clear()
        return
    paths = build_artifact_paths(Path(repo_root))
    cache_key = _cache_key(_storage_path(paths))
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

    events = _cached_events(paths)
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

    _mark_dirty(_storage_path(paths))


def iter_unique_triples(repo_root: Path):
    paths = build_artifact_paths(Path(repo_root))
    events = _cached_events(paths)
    dedup: dict[tuple[str, str, str], dict] = {}
    for event in events:
        key = (event.get("subject", ""), event.get("predicate", ""), event.get("object", ""))
        if key not in dedup:
            dedup[key] = event
    for key in sorted(dedup):
        yield dedup[key]


def seed_neighbor_degrees(repo_root: Path, seed_qids: set[str], max_degree: int = 2) -> dict[str, int]:
    """Return minimal undirected seed-neighborhood degree per reachable QID.

    The returned map excludes seed QIDs themselves and includes only neighbors
    with degree in ``[1, max_degree]``.
    """
    seeds = {canonical_qid(qid) for qid in (seed_qids or set()) if canonical_qid(qid)}
    if not seeds or int(max_degree) < 1:
        return {}

    adjacency: dict[str, set[str]] = {}
    for triple in iter_unique_triples(repo_root):
        subj = canonical_qid(triple.get("subject", ""))
        obj = canonical_qid(triple.get("object", ""))
        if not subj or not obj:
            continue
        adjacency.setdefault(subj, set()).add(obj)
        adjacency.setdefault(obj, set()).add(subj)

    degrees: dict[str, int] = {}
    frontier = set(seeds)
    visited = set(seeds)
    for degree in range(1, int(max_degree) + 1):
        next_frontier: set[str] = set()
        for node in frontier:
            for neighbor in adjacency.get(node, set()):
                if neighbor in visited:
                    continue
                visited.add(neighbor)
                degrees[neighbor] = degree
                next_frontier.add(neighbor)
        if not next_frontier:
            break
        frontier = next_frontier

    return degrees


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
