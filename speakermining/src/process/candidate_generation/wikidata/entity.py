"""Fetch and cache Wikidata entities and their relationships.

Provides cache-first functions to retrieve entity documents, inlinks, and outlinks
from Wikidata, falling back to network requests when cache is stale or empty.
"""
from __future__ import annotations

from pathlib import Path
from urllib.parse import quote, urlencode

from .cache import (
	WIKIDATA_API_BASE,
	WIKIDATA_SPARQL_ENDPOINT,
	_entity_from_payload,
	_http_get_json,
	_latest_cached_record,
)
from .event_log import write_query_event
from .common import canonical_pid, canonical_qid
from .inlinks import build_inlinks_query
from .outlinks import extract_outlinks


def get_or_fetch_entity(
	root: Path | str,
	qid: str,
	cache_max_age_days: int,
	timeout: int = 30,
) -> dict:
	"""Fetch an entity document, using cache when available.
	
	Cache-first strategy: checks local cache before hitting Wikidata API.
	If cached result is fresh (age <= cache_max_age_days), returns it immediately.
	Otherwise, fetches from API and stores result in cache.
	
	Args:
		root: Repository root path.
		qid: Entity Q-ID.
		cache_max_age_days: Maximum cache age in days; older cached records are refreshed.
		timeout: Request timeout in seconds.
	
	Returns:
		Wikidata API payload dict (containing entities field).
		On network error, falls back to cached result if available, else raises.
	"""
	root = Path(root)
	qid = canonical_qid(qid)
	cached = _latest_cached_record(root, "entity", qid)
	if cached and cached[1] <= cache_max_age_days:
		return cached[0].get("payload", {})

	url = f"{WIKIDATA_API_BASE}/{qid}.json"
	try:
		payload = _http_get_json(url, timeout=timeout)
		write_query_event(
			root,
			endpoint="wikidata_api",
			normalized_query=f"entity:{qid}",
			source_step="entity_fetch",
			status="success",
			key=qid,
			payload=payload,
			http_status=200,
			error=None,
		)
		return payload
	except Exception:
		if cached:
			return cached[0].get("payload", {})
		raise


def get_or_fetch_property(
	root: Path | str,
	pid: str,
	cache_max_age_days: int,
	timeout: int = 30,
) -> dict:
	"""Fetch a property document, using cache-first behavior."""
	root = Path(root)
	pid = canonical_pid(pid)
	cached = _latest_cached_record(root, "property", pid)
	if cached and cached[1] <= cache_max_age_days:
		return cached[0].get("payload", {})

	url = f"{WIKIDATA_API_BASE}/{pid}.json"
	try:
		payload = _http_get_json(url, timeout=timeout)
		write_query_event(
			root,
			endpoint="wikidata_api",
			normalized_query=f"property:{pid}",
			source_step="property_fetch",
			status="success",
			key=pid,
			payload=payload,
			http_status=200,
			error=None,
		)
		return payload
	except Exception:
		if cached:
			return cached[0].get("payload", {})
		raise


def get_or_fetch_inlinks(
	root: Path | str,
	qid: str,
	cache_max_age_days: int,
	inlinks_limit: int,
	offset: int = 0,
	timeout: int = 30,
) -> dict:
	"""Fetch inlinks for an entity, using cache when available.
	
	Inlinks are entities that point to the given entity via their claims.
	Cache-first strategy: checks local cache before hitting Wikidata SPARQL endpoint.
	If cached result is fresh (age <= cache_max_age_days), returns it immediately.
	Otherwise, executes SPARQL query and stores result in cache.
	
	Args:
		root: Repository root path.
		qid: Target entity Q-ID.
		cache_max_age_days: Maximum cache age in days; older cached records are refreshed.
		inlinks_limit: Maximum number of inlink results to request from SPARQL.
		timeout: Request timeout in seconds.
	
	Returns:
		Dict with SPARQL response structure (containing results.bindings).
		On network error, falls back to cached result if available, else raises.
	"""
	root = Path(root)
	qid = canonical_qid(qid)
	offset = max(0, int(offset))
	cache_key = f"{qid}_limit{int(inlinks_limit)}_offset{offset}"
	cached = _latest_cached_record(root, "inlinks", cache_key)
	if cached and cached[1] <= cache_max_age_days:
		return cached[0].get("payload", {})

	query = build_inlinks_query(qid, limit=inlinks_limit, offset=offset)
	encoded_query = quote(query, safe="")
	url = f"{WIKIDATA_SPARQL_ENDPOINT}?format=json&query={encoded_query}"
	try:
		payload = _http_get_json(url, accept="application/sparql-results+json", timeout=timeout)
		write_query_event(
			root,
			endpoint="wikidata_sparql",
			normalized_query=f"inlinks:target={qid};page_size={int(inlinks_limit)};offset={offset};order=source_prop",
			source_step="inlinks_fetch",
			status="success",
			key=cache_key,
			payload=payload,
			http_status=200,
			error=None,
		)
		return payload
	except Exception:
		if cached:
			return cached[0].get("payload", {})
		raise


def get_or_build_outlinks(
	root: Path | str, qid: str, entity_payload: dict, cache_max_age_days: int
) -> dict:
	"""Build or fetch cached outlinks from entity claims.
	
	Outlinks are other entities (Q-IDs) and properties (P-IDs) referenced by the entity's claims.
	Since outlinks are derived from the entity document (no separate network call),
	this function checks cache for the derived outlinks data, then extracts from
	entity payload if not cached or cache is stale.
	
	Args:
		root: Repository root path.
		qid: Source entity Q-ID.
		entity_payload: Wikidata API payload dict (from get_or_fetch_entity).
		cache_max_age_days: Maximum cache age in days for the derived outlinks data.
	
	Returns:
		Dict with keys: qid, property_ids (sorted list), linked_qids (sorted list), edges.
	"""
	root = Path(root)
	qid = canonical_qid(qid)
	cached = _latest_cached_record(root, "outlinks", qid)
	if cached and cached[1] <= cache_max_age_days:
		return cached[0].get("payload", {})

	entity_doc = _entity_from_payload(entity_payload, qid)
	outlinks_payload = extract_outlinks(qid, entity_doc)
	write_query_event(
		root,
		endpoint="derived_local",
		normalized_query=f"outlinks_from_entity:{qid}",
		source_step="outlinks_build",
		status="success",
		key=qid,
		payload=outlinks_payload,
		http_status=None,
		error=None,
	)
	return outlinks_payload


def get_or_search_entities_by_label(
	root: Path | str,
	label: str,
	cache_max_age_days: int,
	*,
	language: str = "de",
	limit: int = 10,
	timeout: int = 30,
) -> dict:
	"""Search entities by label via wbsearchentities, with cache-first behavior.

	The fallback stage uses this to discover candidates that are not yet present in
	the discovered node store.
	"""
	root = Path(root)
	query = str(label or "").strip()
	language = str(language or "de").strip().lower() or "de"
	limit = max(1, int(limit))
	cache_key = f"{language}|{limit}|{query}"

	cached = _latest_cached_record(root, "label_search", cache_key)
	if cached and cached[1] <= cache_max_age_days:
		return cached[0].get("payload", {})

	params = {
		"action": "wbsearchentities",
		"format": "json",
		"language": language,
		"type": "item",
		"limit": str(limit),
		"search": query,
	}
	url = f"https://www.wikidata.org/w/api.php?{urlencode(params)}"
	try:
		payload = _http_get_json(url, timeout=timeout)
		write_query_event(
			root,
			endpoint="wikidata_api",
			normalized_query=f"wbsearchentities:language={language};limit={limit};search={query}",
			source_step="entity_fetch",
			status="success",
			key=cache_key,
			payload=payload,
			http_status=200,
			error=None,
		)
		return payload
	except Exception:
		if cached:
			return cached[0].get("payload", {})
		raise
