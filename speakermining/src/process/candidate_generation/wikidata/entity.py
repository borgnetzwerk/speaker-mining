"""Fetch and cache Wikidata entities and their relationships.

Provides cache-first functions to retrieve entity documents, inlinks, and outlinks
from Wikidata, falling back to network requests when cache is stale or empty.
"""
from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

from .cache import (
	WIKIDATA_API_BASE,
	WIKIDATA_SPARQL_ENDPOINT,
	_entity_from_payload,
	_http_get_json,
	_latest_cached_record,
	_write_raw_query_record,
)
from .common import canonical_qid
from .inlinks import build_inlinks_query, parse_inlinks_results
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
		_write_raw_query_record(root, "entity", qid, payload, source="wikidata_api")
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
	cache_key = f"{qid}_limit{int(inlinks_limit)}"
	cached = _latest_cached_record(root, "inlinks", cache_key)
	if cached and cached[1] <= cache_max_age_days:
		return cached[0].get("payload", {})

	query = build_inlinks_query(qid, inlinks_limit)
	encoded_query = quote(query, safe="")
	url = f"{WIKIDATA_SPARQL_ENDPOINT}?format=json&query={encoded_query}"
	try:
		payload = _http_get_json(url, accept="application/sparql-results+json", timeout=timeout)
		_write_raw_query_record(root, "inlinks", cache_key, payload, source="wikidata_sparql")
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
	_write_raw_query_record(root, "outlinks", qid, outlinks_payload, source="derived_from_entity")
	return outlinks_payload
