"""Single-entity full fetch: all claims with qualifiers and references.

full_fetch is the heavyweight fetch used for seeds and high-priority candidates.
It extracts all outgoing triples, recording qualifier PIDs and reference PIDs
for each claim.
"""
from __future__ import annotations

from pathlib import Path
from urllib.parse import urlencode

from .cache import _entity_from_payload, _http_get_json, _latest_cached_record
from .common import (
    DEFAULT_WIKIDATA_FALLBACK_LANGUAGE,
    canonical_pid,
    canonical_qid,
    pick_entity_label,
)
from .event_log import (
    build_entity_fetched_event,
    build_query_event,
    build_triple_discovered_event,
    get_query_event_response_data,
)
from .event_writer import get_event_store


def _build_full_fetch_url(qid: str, languages: list[str]) -> str:
    lang_set = set(languages)
    lang_set.add(DEFAULT_WIKIDATA_FALLBACK_LANGUAGE)
    params = {
        "action": "wbgetentities",
        "format": "json",
        "ids": qid,
        "props": "labels|descriptions|aliases|claims",
        "languages": "|".join(sorted(lang_set)),
        "languagefallback": "0",
    }
    return f"https://www.wikidata.org/w/api.php?{urlencode(params)}"


def _extract_qualifier_pids(snak_group: dict) -> list[str]:
    qualifiers = snak_group.get("qualifiers", {})
    if not isinstance(qualifiers, dict):
        return []
    pids = []
    for pid_raw in qualifiers:
        pid = canonical_pid(str(pid_raw))
        if pid:
            pids.append(pid)
    return sorted(set(pids))


def _extract_reference_pids(snak_group: dict) -> list[str]:
    references = snak_group.get("references", [])
    if not isinstance(references, list):
        return []
    pids: set[str] = set()
    for ref in references:
        snaks = ref.get("snaks", {})
        if isinstance(snaks, dict):
            for pid_raw in snaks:
                pid = canonical_pid(str(pid_raw))
                if pid:
                    pids.add(pid)
    return sorted(pids)


def _iter_triples(entity_doc: dict, subject_qid: str):
    """Yield (predicate_pid, object_qid, qualifier_pids, reference_pids) for all claims."""
    claims = entity_doc.get("claims", {})
    if not isinstance(claims, dict):
        return
    for pid_raw, snak_groups in claims.items():
        pid = canonical_pid(str(pid_raw))
        if not pid or not isinstance(snak_groups, list):
            continue
        for snak_group in snak_groups:
            try:
                mainsnak = snak_group.get("mainsnak", {})
                if mainsnak.get("snaktype") != "value":
                    continue
                datavalue = mainsnak.get("datavalue", {})
                if datavalue.get("type") != "wikibase-entityid":
                    continue
                obj_raw = datavalue["value"]["id"]
                obj_qid = canonical_qid(str(obj_raw))
                if not obj_qid:
                    continue
            except (KeyError, TypeError):
                continue
            qualifier_pids = _extract_qualifier_pids(snak_group)
            reference_pids = _extract_reference_pids(snak_group)
            yield pid, obj_qid, qualifier_pids, reference_pids


def full_fetch(
    qid: str,
    *,
    repo_root: Path,
    depth: int,
    languages: list[str] | None = None,
    event_store=None,
    max_cache_age_days: int = 365,
) -> dict | None:
    """Fetch all claims for a single entity and emit domain events.

    Emits:
    - one entity_fetched event
    - one triple_discovered event per outgoing QID-valued claim

    Returns the entity document dict, or None if the fetch fails.
    """
    repo_root = Path(repo_root)
    qid = canonical_qid(str(qid or ""))
    if not qid:
        return None
    if languages is None:
        languages = ["de", "en"]

    store = event_store or get_event_store(repo_root)

    # Check entity cache first (B2: skip cache if older than max_cache_age_days)
    cached = _latest_cached_record(repo_root, "entity", qid)
    if cached is not None:
        record, age_days = cached
        if age_days is not None and age_days > max_cache_age_days:
            cached = None
    if cached is not None:
        record, _age = cached
        response_data = get_query_event_response_data(record)
        entity_doc = _entity_from_payload({"entities": response_data.get("entities", {})}, qid)
        if entity_doc:
            source = "entity_cache"
        else:
            entity_doc = None
    else:
        entity_doc = None
        source = "network"

    if entity_doc is None:
        url = _build_full_fetch_url(qid, languages)
        try:
            response = _http_get_json(url)
        except Exception:
            return None

        entities_block = response.get("entities", {}) if isinstance(response, dict) else {}
        event = build_query_event(
            endpoint="wikidata_api",
            normalized_query=url,
            source_step="entity_fetch",
            status="success",
            key=qid,
            payload={"entities": entities_block},
            http_status=200,
            error=None,
        )
        store.append_event(event)
        entity_doc = _entity_from_payload({"entities": entities_block}, qid)
        if not entity_doc:
            return None
        source = "network"

    label = pick_entity_label(entity_doc)
    triples = list(_iter_triples(entity_doc, qid))

    # Extract description (first available language)
    description = ""
    for lang in languages:
        desc = entity_doc.get("descriptions", {}).get(lang, {})
        if isinstance(desc, dict) and desc.get("value"):
            description = desc["value"]
            break

    # Extract aliases for all requested languages
    aliases: list[str] = []
    for lang in languages:
        for entry in entity_doc.get("aliases", {}).get(lang, []):
            if isinstance(entry, dict) and entry.get("value"):
                aliases.append(entry["value"])

    # Emit entity_fetched
    store.append_event(build_entity_fetched_event(
        qid=qid,
        label=label,
        description=description,
        aliases=aliases,
        depth=depth,
        triple_count=len(triples),
    ))

    # Emit triple_discovered for each outgoing QID claim
    for pid, obj_qid, qualifier_pids, reference_pids in triples:
        store.append_event(build_triple_discovered_event(
            subject_qid=qid,
            predicate_pid=pid,
            object_qid=obj_qid,
            source_step="entity_fetch",
            payload={
                "depth": depth,
                "qualifier_pids": qualifier_pids,
                "reference_pids": reference_pids,
            },
        ))

    return entity_doc
