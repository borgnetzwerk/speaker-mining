"""Batch wbgetentities fetch for label, P31 (instance-of), and P279 (subclass-of).

basic_fetch is the lightweight alternative to full_fetch — it fetches only the
fields needed for class hierarchy resolution and relevancy classification.
"""
from __future__ import annotations

from pathlib import Path
from urllib.parse import urlencode

from .cache import _entity_from_payload, _http_get_json, _latest_cached_record
from .common import DEFAULT_WIKIDATA_FALLBACK_LANGUAGE, canonical_qid, pick_entity_label
from .event_log import build_query_event, get_query_event_response_data
from .event_writer import get_event_store


_BATCH_SIZE = 50


def _build_batch_url(qids: list[str], languages: list[str]) -> str:
    lang_set = set(languages)
    lang_set.add(DEFAULT_WIKIDATA_FALLBACK_LANGUAGE)
    params = {
        "action": "wbgetentities",
        "format": "json",
        "ids": "|".join(qids),
        "props": "labels|claims",
        "languages": "|".join(sorted(lang_set)),
        "languagefallback": "0",
    }
    return f"https://www.wikidata.org/w/api.php?{urlencode(params)}"


def _extract_pid_qids(entity_doc: dict, pid: str) -> list[str]:
    """Return all QID values for a direct claim under pid."""
    if not isinstance(entity_doc, dict):
        return []
    claims = entity_doc.get("claims", {})
    if not isinstance(claims, dict):
        return []
    result = []
    for snak in claims.get(pid, []):
        try:
            value = snak["mainsnak"]["datavalue"]["value"]["id"]
            qid = canonical_qid(str(value))
            if qid:
                result.append(qid)
        except (KeyError, TypeError):
            continue
    return result


def _result_from_entity_doc(entity_doc: dict) -> dict:
    return {
        "label": pick_entity_label(entity_doc),
        "p31_qids": _extract_pid_qids(entity_doc, "P31"),
        "p279_qids": _extract_pid_qids(entity_doc, "P279"),
    }


def _try_entity_cache(root: Path, qid: str) -> dict | None:
    """Check the entity_fetch cache for a QID. Returns result dict or None."""
    cached = _latest_cached_record(root, "entity", qid)
    if cached is None:
        return None
    record, _age = cached
    response_data = get_query_event_response_data(record)
    entity_doc = _entity_from_payload({"entities": response_data.get("entities", {})}, qid)
    if not entity_doc:
        return None
    result = _result_from_entity_doc(entity_doc)
    result["source"] = "entity_cache"
    return result


def basic_fetch_batch(
    qids: list[str],
    *,
    repo_root: Path,
    languages: list[str] | None = None,
) -> dict[str, dict]:
    """Fetch label/P31/P279 for a list of QIDs, using entity cache where possible.

    Returns:
        {qid: {"label": str, "p31_qids": list[str], "p279_qids": list[str], "source": str}}
        source is "entity_cache" for cache hits, "network" for live fetches.
        QIDs that could not be fetched are absent from the result.
    """
    repo_root = Path(repo_root)
    if languages is None:
        languages = ["de", "en"]

    results: dict[str, dict] = {}
    to_fetch: list[str] = []

    for qid in qids:
        qid = canonical_qid(str(qid or ""))
        if not qid:
            continue
        cached = _try_entity_cache(repo_root, qid)
        if cached is not None:
            results[qid] = cached
        else:
            to_fetch.append(qid)

    if not to_fetch:
        return results

    store = get_event_store(repo_root)

    for batch_start in range(0, len(to_fetch), _BATCH_SIZE):
        batch = to_fetch[batch_start : batch_start + _BATCH_SIZE]
        url = _build_batch_url(batch, languages)
        try:
            response = _http_get_json(url)
        except Exception:
            continue

        entities_block = response.get("entities", {}) if isinstance(response, dict) else {}

        event = build_query_event(
            endpoint="wikidata_api",
            normalized_query=url,
            source_step="basic_fetch",
            status="success",
            key=batch[0],
            payload={"entities": entities_block},
            http_status=200,
            error=None,
        )
        store.append_event(event)

        for qid in batch:
            entity_doc = _entity_from_payload({"entities": entities_block}, qid)
            if not entity_doc:
                continue
            result = _result_from_entity_doc(entity_doc)
            result["source"] = "network"
            results[qid] = result

    return results
