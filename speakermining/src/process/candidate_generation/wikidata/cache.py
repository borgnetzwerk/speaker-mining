"""Cache and I/O utilities for Wikidata queries.

Provides atomic file writes, HTTP access, timestamp management, and cache lookups
for storing and retrieving Wikidata query results.
"""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

import pandas as pd


WIKIDATA_API_BASE = "https://www.wikidata.org/wiki/Special:EntityData"
WIKIDATA_SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
USER_AGENT = "speaker-mining/0.1 (candidate-generation)"


_REQUEST_CONTEXT: dict[str, float | int] | None = None


def begin_request_context(max_queries_per_run: int, query_delay_seconds: float) -> None:
	"""Initialize process-local HTTP request budget and delay context.

	Args:
		max_queries_per_run: Maximum allowed network requests for this run.
			Use 0 for unlimited.
		query_delay_seconds: Minimum delay between network requests.
	"""
	global _REQUEST_CONTEXT
	_REQUEST_CONTEXT = {
		"max_queries_per_run": int(max_queries_per_run),
		"query_delay_seconds": float(query_delay_seconds),
		"network_queries": 0,
		"last_query_time": 0.0,
	}


def end_request_context() -> int:
	"""Clear request context and return number of network requests consumed."""
	global _REQUEST_CONTEXT
	if _REQUEST_CONTEXT is None:
		return 0
	used = int(_REQUEST_CONTEXT.get("network_queries", 0))
	_REQUEST_CONTEXT = None
	return used


def _now_utc() -> datetime:
	"""Get current UTC time."""
	return datetime.now(tz=timezone.utc)


def _iso_utc(dt: datetime) -> str:
	"""Format a datetime as ISO 8601 UTC string (YYYY-MM-DDTHH:MM:SSZ)."""
	return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _safe_token(value: str) -> str:
	"""Sanitize a string for safe filename use.
	
	Replaces non-alphanumeric characters (except . and -) with underscores.
	
	Args:
		value: Input string.
	
	Returns:
		Safe token suitable for filenames.
	"""
	token = re.sub(r"[^a-zA-Z0-9_.-]+", "_", str(value or "").strip())
	return token.strip("_") or "na"


def _phase_dir(root: Path) -> Path:
	"""Get the Phase 2 (candidate generation) output directory."""
	return root / "data" / "20_candidate_generation"


def _wikidata_dir(root: Path) -> Path:
	"""Get the Wikidata-specific subdirectory."""
	return _phase_dir(root) / "wikidata"


def _raw_dir(root: Path) -> Path:
	"""Get the directory storing raw per-query cache files."""
	return _wikidata_dir(root) / "raw_queries"


def _ensure_dirs(root: Path) -> None:
	"""Ensure all required directories exist."""
	_raw_dir(root).mkdir(parents=True, exist_ok=True)


def _atomic_write_text(path: Path, text: str) -> None:
	"""Write text atomically via temp file + rename.
	
	Prevents corruption if process crashes mid-write.
	
	Args:
		path: Target file path.
		text: Content to write.
	"""
	path.parent.mkdir(parents=True, exist_ok=True)
	tmp_path = path.with_suffix(path.suffix + ".tmp")
	tmp_path.write_text(text, encoding="utf-8")
	tmp_path.replace(path)


def _atomic_write_df(path: Path, df: pd.DataFrame) -> None:
	"""Write DataFrame atomically via temp file + rename.
	
	Args:
		path: Target CSV file path.
		df: DataFrame to write.
	"""
	path.parent.mkdir(parents=True, exist_ok=True)
	tmp_path = path.with_suffix(path.suffix + ".tmp")
	df.to_csv(tmp_path, index=False)
	tmp_path.replace(path)


def _http_get_json(url: str, accept: str = "application/json", timeout: int = 30) -> dict:
	"""Fetch JSON from HTTP endpoint with User-Agent.
	
	Args:
		url: Full URL to fetch.
		accept: Accept header value.
		timeout: Request timeout in seconds. Default 30.
	
	Returns:
		Parsed JSON response.
	
	Raises:
		urllib.error.URLError: If request fails.
		RuntimeError: If configured per-run query budget is exhausted.
	"""
	global _REQUEST_CONTEXT
	if _REQUEST_CONTEXT is not None:
		max_queries = int(_REQUEST_CONTEXT.get("max_queries_per_run", 0))
		used_queries = int(_REQUEST_CONTEXT.get("network_queries", 0))
		if max_queries > 0 and used_queries >= max_queries:
			raise RuntimeError("Network query budget hit")

		delay_seconds = float(_REQUEST_CONTEXT.get("query_delay_seconds", 0.0))
		last_query_time = float(_REQUEST_CONTEXT.get("last_query_time", 0.0))
		now = time.time()
		time_since_last = now - last_query_time
		if time_since_last < delay_seconds:
			time.sleep(delay_seconds - time_since_last)
		_REQUEST_CONTEXT["last_query_time"] = time.time()
		_REQUEST_CONTEXT["network_queries"] = used_queries + 1

	req = Request(url, headers={"Accept": accept, "User-Agent": USER_AGENT})
	with urlopen(req, timeout=timeout) as response:
		payload = response.read().decode("utf-8")
	return json.loads(payload)


def _raw_record_path(raw_dir: Path, query_type: str, key: str, stamp: datetime) -> Path:
	"""Construct timestamped raw query record pathname.
	
	Format: {TIMESTAMP}__{QUERY_TYPE}__{KEY}.json
	Example: 20260326T115830000000Z__entity__Q1499182.json
	
	Args:
		raw_dir: Directory to store in.
		query_type: Type of query (entity, inlinks, outlinks, candidate_match, etc.).
		key: Query identifier (Q-ID, cache key, etc.).
		stamp: Timestamp of query execution.
	
	Returns:
		Full Path object.
	"""
	ts = stamp.strftime("%Y%m%dT%H%M%S%fZ")
	return raw_dir / f"{ts}__{_safe_token(query_type)}__{_safe_token(key)}.json"


def _write_raw_query_record(root: Path, query_type: str, key: str, payload: dict, source: str) -> Path:
	"""Write a raw query result to cache.
	
	Creates a timestamped JSON record containing the query metadata and response payload.
	Used for cache-first design: one file per query result.
	
	Args:
		root: Repository root path.
		query_type: Type of query (entity, inlinks, outlinks, candidate_match).
		key: Query identifier (Q-ID, cache key, mention_id, etc.).
		payload: Response payload (API response or derived data).
		source: Source of payload (wikidata_api, wikidata_sparql, derived_from_entity, matching_scan).
	
	Returns:
		Path to created file.
	"""
	stamp = _now_utc()
	record = {
		"query_type": query_type,
		"key": key,
		"requested_at_utc": _iso_utc(stamp),
		"source": source,
		"payload": payload,
	}
	path = _raw_record_path(_raw_dir(root), query_type, key, stamp)
	_atomic_write_text(path, json.dumps(record, ensure_ascii=False, indent=2))
	return path


def _load_raw_record(path: Path) -> dict | None:
	"""Load a raw query record from JSON file.
	
	Args:
		path: Path to JSON record file.
	
	Returns:
		Parsed record dict, or None if file cannot be read/parsed.
	"""
	try:
		return json.loads(path.read_text(encoding="utf-8"))
	except Exception:
		return None


def _latest_cached_record(root: Path, query_type: str, key: str) -> tuple[dict, float] | None:
	"""Find most recent cached record matching query type and key.
	
	Searches raw_queries/ directory for timestamped records matching the pattern.
	Returns most recent match with its age in days.
	
	Args:
		root: Repository root path.
		query_type: Query type to search for (entity, inlinks, etc.).
		key: Query key to search for (Q-ID, cache key, etc.).
	
	Returns:
		Tuple of (record_dict, age_days) where age_days is computed from requested_at_utc,
		or None if no matching file exists or all matches are unparseable.
	"""
	pattern = f"*__{_safe_token(query_type)}__{_safe_token(key)}.json"
	files = sorted(_raw_dir(root).glob(pattern), reverse=True)
	for path in files:
		record = _load_raw_record(path)
		if not record:
			continue
		ts = record.get("requested_at_utc", "")
		try:
			dt = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
		except Exception:
			continue
		age_days = (_now_utc() - dt).total_seconds() / 86400.0
		return record, age_days
	return None


def _entity_from_payload(payload: dict, qid: str) -> dict:
	"""Extract entity document from Wikidata API payload.
	
	The API returns a dict with an 'entities' key mapping Q-ID → entity doc.
	This function extracts the entity for a given Q-ID.
	
	Args:
		payload: Wikidata API JSON response.
		qid: Entity Q-ID to extract.
	
	Returns:
		Entity document dict (may be empty if Q-ID not in payload).
	"""
	entities = payload.get("entities", {})
	return entities.get(qid, {})
