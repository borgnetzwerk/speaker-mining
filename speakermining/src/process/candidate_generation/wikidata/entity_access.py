"""Public entity access API for downstream phases (Phase 5+).

Access tiers (F25 interface contract):

  get_cached_entity_doc(qid, repo_root)
      Returns the best available raw Wikidata entity document from the event log
      cache (full_fetch preferred, basic_fetch fallback).  O(1) after first call
      on a given repo_root (index is primed once).  Returns None if not cached.

  ensure_basic_fetch(qid, repo_root, languages)
      Cache hit → same as get_cached_entity_doc.  Miss → issues a network call,
      stores the result in the event log cache, then returns the doc.  Retrieves
      labels + P31/P279 only — NOT sufficient for property analysis (P21, P106,
      P102, P108, P569, P19).  Use all_outlink_fetch for those.

  all_outlink_fetch(qid, repo_root, languages)
      Cache hit → same as get_cached_entity_doc.  Miss → fetches the entity's
      full claims from Wikidata (all outlink properties: P21, P106, P102, P108,
      P569, P19, etc.) and stores the result in the event log cache.  Does NOT
      trigger inlinks expansion or recursive graph traversal.  This is the
      correct tier for Phase 5 property retrieval over manually reconciled QIDs.
      Requires an active request context (begin_request_context must be called
      before any batch that may trigger network calls).

  load_core_entities(repo_root, class_filename)
      Reads a core_<class_filename>.json handover file from the projections
      directory and returns it as {QID: entity_doc}.  Returns {} if the file is
      missing or empty.

Request context (required before network calls):

  begin_request_context(budget_remaining, query_delay_seconds, ...)
      Initialize the Phase 2 network guardrail before a batch of all_outlink_fetch
      calls that may hit the network.  budget_remaining=-1 means unlimited.
      query_delay_seconds controls the minimum inter-request delay.

  end_request_context() -> int
      Tear down the request context.  Returns the number of network requests
      consumed.  Always call this in a finally block after begin_request_context.
"""
from __future__ import annotations

import json
from pathlib import Path

from .cache import begin_request_context, end_request_context  # noqa: F401 — re-exported for Phase 5 callers


def get_cached_entity_doc(qid: str, repo_root: Path) -> dict | None:
    """Return the best available cached Wikidata entity doc for qid, or None.

    Checks full_fetch (entity) cache first, falls back to basic_fetch.
    O(1) per call after the index is primed on first use.
    """
    from .cache import _entity_from_payload, _latest_cached_record
    from .common import canonical_qid as _cqid
    from .event_log import get_query_event_response_data

    qid = _cqid(str(qid or ""))
    if not qid:
        return None
    for source_step in ("entity", "basic_fetch"):
        cached = _latest_cached_record(Path(repo_root), source_step, qid)
        if cached is not None:
            record, _ = cached
            response_data = get_query_event_response_data(record)
            doc = _entity_from_payload({"entities": response_data.get("entities", {})}, qid)
            if doc:
                return doc
    return None


def ensure_basic_fetch(
    qid: str,
    repo_root: Path,
    *,
    languages: list[str] | None = None,
) -> dict | None:
    """Return cached entity doc for qid, fetching from Wikidata if not cached.

    Uses the basic_fetch tier (labels + P31/P279 claims).  For richer data
    (full claims), prefer get_cached_entity_doc which will return a full_fetch
    doc if one exists.

    Returns None only if the network call fails or the QID is not found.
    """
    from .basic_fetch import basic_fetch_batch
    from .common import canonical_qid as _cqid

    qid = _cqid(str(qid or ""))
    if not qid:
        return None
    cached = get_cached_entity_doc(qid, repo_root)
    if cached is not None:
        return cached
    results = basic_fetch_batch([qid], repo_root=Path(repo_root), languages=languages)
    if qid not in results:
        return None
    # basic_fetch_batch returns {label, p31_qids, p279_qids, source}; the raw doc
    # is now in the event log cache — retrieve it via the standard path.
    return get_cached_entity_doc(qid, repo_root)


def all_outlink_fetch(
    qid: str,
    repo_root: Path,
    *,
    languages: list[str] | None = None,
) -> dict | None:
    """Return full entity doc for qid, fetching all outlink claims if not cached.

    Cache-first: returns immediately if a full entity doc already exists in the
    event log.  On cache miss, fetches the entity's complete claims from Wikidata
    (P21, P106, P102, P108, P569, P19, and all other outlink properties) via one
    HTTP request and stores the result in the event log cache.

    Does NOT trigger inlinks expansion or recursive entity graph traversal.
    This is the correct tier for Phase 5 property retrieval over manually
    reconciled QIDs that were not covered by the Phase 2 hydration run.
    Callers should never call full_fetch.full_fetch() directly — use this
    function instead.

    Returns:
        Entity doc dict with full claims, or None if not found / fetch failed.
    """
    from .full_fetch import full_fetch as _full_fetch
    from .common import canonical_qid as _cqid

    qid = _cqid(str(qid or ""))
    if not qid:
        return None
    cached = get_cached_entity_doc(qid, repo_root)
    if cached is not None:
        return cached
    return _full_fetch(qid, repo_root=Path(repo_root), depth=0, languages=languages)


def load_core_entities(repo_root: Path, class_filename: str) -> dict[str, dict]:
    """Load core_<class_filename>.json from the projections directory.

    Returns {QID: entity_doc} where entity_doc is raw Wikidata JSON.
    Returns {} if the file does not exist or is empty.
    """
    from .schemas import canonical_class_filename

    try:
        filename = canonical_class_filename(str(class_filename or ""))
    except ValueError:
        filename = str(class_filename or "").strip().lower()

    path = (
        Path(repo_root)
        / "data"
        / "20_candidate_generation"
        / "wikidata"
        / "projections"
        / f"core_{filename}.json"
    )
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def load_all_core_entities(repo_root: Path) -> dict[str, dict]:
    """Load all core_*.json files and merge into a single {QID: entity_doc} dict.

    If the same QID appears in multiple core class files (cross-class entities),
    the full_fetch doc (more complete) takes precedence over basic_fetch docs.
    """
    from .schemas import canonical_class_filename

    proj_dir = (
        Path(repo_root) / "data" / "20_candidate_generation" / "wikidata" / "projections"
    )
    merged: dict[str, dict] = {}
    for path in sorted(proj_dir.glob("core_*.json")):
        if path.stem.startswith("not_relevant_core_"):
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        for qid, doc in data.items():
            if qid not in merged:
                merged[qid] = doc
    return merged
