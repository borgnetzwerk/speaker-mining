"""Fetch and cache Wikidata entities and their relationships.

Provides cache-first functions to retrieve entity documents, inlinks, and outlinks
from Wikidata, falling back to network requests when cache is stale or empty.
"""
from __future__ import annotations

from pathlib import Path
from urllib.parse import quote, urlencode

from .cache import (
	WIKIDATA_SPARQL_ENDPOINT,
	_entity_from_payload,
	_http_get_json,
	_latest_cached_record,
)
from .event_log import get_query_event_response_data, write_query_event
from .common import (
	DEFAULT_WIKIDATA_FALLBACK_LANGUAGE,
	active_wikidata_languages_with_default,
	canonical_pid,
	canonical_qid,
	get_active_wikidata_languages,
)
from .inlinks import build_inlinks_query
from .outlinks import extract_outlinks


def _language_filter_set() -> set[str]:
	return {str(lang).strip().lower() for lang in active_wikidata_languages_with_default() if str(lang).strip()}


def _requested_literal_languages() -> set[str]:
	return {str(lang).strip().lower() for lang in get_active_wikidata_languages() if str(lang).strip()}


def _build_wbgetentities_url(entity_id: str, *, languages: set[str], include_claims: bool) -> str:
	props = "labels|descriptions|aliases"
	if include_claims:
		props = f"{props}|claims"
	language_tokens = set(languages)
	language_tokens.add(DEFAULT_WIKIDATA_FALLBACK_LANGUAGE)
	params = {
		"action": "wbgetentities",
		"format": "json",
		"ids": str(entity_id),
		"props": props,
		"languages": "|".join(sorted(language_tokens)),
		"languagefallback": "0",
	}
	return f"https://www.wikidata.org/w/api.php?{urlencode(params)}"


def _copy_entity_payload(payload: dict) -> dict:
	if not isinstance(payload, dict):
		return {}
	entities = payload.get("entities", {})
	if not isinstance(entities, dict):
		return {"entities": {}}
	return {"entities": {str(entity_id): dict(entity_doc) for entity_id, entity_doc in entities.items()}}


def _coverage_field_for_kind(kind: str) -> str:
	return "_fetched_literal_languages" if kind == "entity" else "_fetched_literal_languages_property"


def _covered_literal_languages(entity_doc: dict, *, kind: str) -> set[str]:
	covered: set[str] = set()
	if not isinstance(entity_doc, dict):
		return covered
	coverage_field = _coverage_field_for_kind(kind)
	for token in entity_doc.get(coverage_field, []) or []:
		lang = str(token or "").strip().lower()
		if lang:
			covered.add(lang)
	for block_name in ("labels", "descriptions", "aliases"):
		block = entity_doc.get(block_name, {})
		if not isinstance(block, dict):
			continue
		for lang in block.keys():
			lang_token = str(lang or "").strip().lower()
			if lang_token and lang_token != DEFAULT_WIKIDATA_FALLBACK_LANGUAGE:
				covered.add(lang_token)
	return covered


def _ensure_literal_coverage_marker(entity_doc: dict, *, kind: str, requested_languages: set[str]) -> None:
	if not isinstance(entity_doc, dict):
		return
	coverage_field = _coverage_field_for_kind(kind)
	covered = _covered_literal_languages(entity_doc, kind=kind)
	covered.update({str(lang).strip().lower() for lang in requested_languages if str(lang).strip()})
	entity_doc[coverage_field] = sorted(covered)


def _missing_literal_languages(entity_doc: dict, *, kind: str, requested_languages: set[str]) -> set[str]:
	covered = _covered_literal_languages(entity_doc, kind=kind)
	return {lang for lang in requested_languages if lang not in covered}


def _merge_multilang_block(base: object, patch: object, *, expect_list: bool) -> dict:
	base_dict = dict(base) if isinstance(base, dict) else {}
	patch_dict = dict(patch) if isinstance(patch, dict) else {}
	merged = dict(base_dict)
	for lang, value in patch_dict.items():
		lang_key = str(lang or "").strip().lower()
		if expect_list:
			if isinstance(value, list):
				merged[lang_key] = value
		else:
			if isinstance(value, dict):
				merged[lang_key] = value
	return merged


def _merge_entity_docs(base_doc: dict, patch_doc: dict, *, kind: str, requested_languages: set[str]) -> dict:
	merged = dict(base_doc or {})
	patch = dict(patch_doc or {})
	if patch.get("id"):
		merged["id"] = patch.get("id")
	merged["labels"] = _merge_multilang_block(merged.get("labels", {}), patch.get("labels", {}), expect_list=False)
	merged["descriptions"] = _merge_multilang_block(merged.get("descriptions", {}), patch.get("descriptions", {}), expect_list=False)
	merged["aliases"] = _merge_multilang_block(merged.get("aliases", {}), patch.get("aliases", {}), expect_list=True)
	if isinstance(patch.get("claims"), dict):
		merged["claims"] = patch.get("claims")
	elif "claims" not in merged:
		merged["claims"] = {}
	_ensure_literal_coverage_marker(merged, kind=kind, requested_languages=requested_languages)
	return merged


def _payload_from_entity_doc(entity_id: str, entity_doc: dict) -> dict:
	return {"entities": {str(entity_id): dict(entity_doc or {})}}


def _filter_multilang_block(block: dict, allowed_languages: set[str], expect_list: bool) -> dict:
	if not isinstance(block, dict):
		return {}
	filtered: dict = {}
	for lang, value in block.items():
		lang_key = str(lang or "").strip().lower()
		if lang_key not in allowed_languages:
			continue
		if expect_list:
			if isinstance(value, list):
				filtered[lang_key] = value
		else:
			if isinstance(value, dict):
				filtered[lang_key] = value
	return filtered


def _filter_entity_payload_languages(payload: dict) -> dict:
	if not isinstance(payload, dict):
		return payload
	allowed_languages = _language_filter_set()
	entities = payload.get("entities", {})
	if not isinstance(entities, dict):
		return payload

	for _, doc in entities.items():
		if not isinstance(doc, dict):
			continue
		doc["labels"] = _filter_multilang_block(doc.get("labels", {}), allowed_languages, expect_list=False)
		doc["descriptions"] = _filter_multilang_block(doc.get("descriptions", {}), allowed_languages, expect_list=False)
		doc["aliases"] = _filter_multilang_block(doc.get("aliases", {}), allowed_languages, expect_list=True)
	return payload


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
	requested_languages = _requested_literal_languages()
	cached = _latest_cached_record(root, "entity", qid)
	if cached:
		cached_payload = _filter_entity_payload_languages(get_query_event_response_data(cached[0]))
		cached_doc = _entity_from_payload(cached_payload, qid)
		if isinstance(cached_doc, dict) and cached_doc:
			missing_languages = _missing_literal_languages(cached_doc, kind="entity", requested_languages=requested_languages)
			if not missing_languages and cached[1] <= cache_max_age_days:
				return cached_payload
			has_claims = isinstance(cached_doc.get("claims"), dict)
			if missing_languages and has_claims:
				url = _build_wbgetentities_url(qid, languages=missing_languages, include_claims=False)
				try:
					incremental_payload = _http_get_json(url, timeout=timeout)
					incremental_payload = _filter_entity_payload_languages(incremental_payload)
					incremental_doc = _entity_from_payload(incremental_payload, qid)
					merged_doc = _merge_entity_docs(
						cached_doc,
						incremental_doc if isinstance(incremental_doc, dict) else {},
						kind="entity",
						requested_languages=requested_languages,
					)
					merged_payload = _payload_from_entity_doc(qid, merged_doc)
					write_query_event(
						root,
						endpoint="wikidata_api",
						normalized_query=f"entity:{qid}:missing_literals:{'|'.join(sorted(missing_languages))}",
						source_step="entity_fetch",
						status="success",
						key=qid,
						payload=merged_payload,
						http_status=200,
						error=None,
					)
					return merged_payload
				except Exception:
					return cached_payload
			if not missing_languages:
				return cached_payload

	url = _build_wbgetentities_url(qid, languages=requested_languages, include_claims=True)
	try:
		payload = _http_get_json(url, timeout=timeout)
		payload = _filter_entity_payload_languages(payload)
		entity_doc = _entity_from_payload(payload, qid)
		if isinstance(entity_doc, dict) and entity_doc:
			_ensure_literal_coverage_marker(entity_doc, kind="entity", requested_languages=requested_languages)
			payload = _payload_from_entity_doc(qid, entity_doc)
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
			return _filter_entity_payload_languages(get_query_event_response_data(cached[0]))
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
	requested_languages = _requested_literal_languages()
	cached = _latest_cached_record(root, "property", pid)
	if cached:
		cached_payload = _filter_entity_payload_languages(get_query_event_response_data(cached[0]))
		cached_doc = _entity_from_payload(cached_payload, pid)
		if isinstance(cached_doc, dict) and cached_doc:
			missing_languages = _missing_literal_languages(cached_doc, kind="property", requested_languages=requested_languages)
			if not missing_languages and cached[1] <= cache_max_age_days:
				return cached_payload
			has_claims = isinstance(cached_doc.get("claims"), dict)
			if missing_languages and has_claims:
				url = _build_wbgetentities_url(pid, languages=missing_languages, include_claims=False)
				try:
					incremental_payload = _http_get_json(url, timeout=timeout)
					incremental_payload = _filter_entity_payload_languages(incremental_payload)
					incremental_doc = _entity_from_payload(incremental_payload, pid)
					merged_doc = _merge_entity_docs(
						cached_doc,
						incremental_doc if isinstance(incremental_doc, dict) else {},
						kind="property",
						requested_languages=requested_languages,
					)
					merged_payload = _payload_from_entity_doc(pid, merged_doc)
					write_query_event(
						root,
						endpoint="wikidata_api",
						normalized_query=f"property:{pid}:missing_literals:{'|'.join(sorted(missing_languages))}",
						source_step="property_fetch",
						status="success",
						key=pid,
						payload=merged_payload,
						http_status=200,
						error=None,
					)
					return merged_payload
				except Exception:
					return cached_payload
			if not missing_languages:
				return cached_payload

	url = _build_wbgetentities_url(pid, languages=requested_languages, include_claims=True)
	try:
		payload = _http_get_json(url, timeout=timeout)
		payload = _filter_entity_payload_languages(payload)
		property_doc = _entity_from_payload(payload, pid)
		if isinstance(property_doc, dict) and property_doc:
			_ensure_literal_coverage_marker(property_doc, kind="property", requested_languages=requested_languages)
			payload = _payload_from_entity_doc(pid, property_doc)
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
			return _filter_entity_payload_languages(get_query_event_response_data(cached[0]))
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
		return get_query_event_response_data(cached[0])

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
			return get_query_event_response_data(cached[0])
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
		return get_query_event_response_data(cached[0])

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
		return get_query_event_response_data(cached[0])

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
			return get_query_event_response_data(cached[0])
		raise
