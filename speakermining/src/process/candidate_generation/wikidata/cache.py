"""Cache and I/O utilities for Wikidata queries.

Provides atomic file writes, HTTP access, timestamp management, and cache lookups
for storing and retrieving Wikidata query results.
"""
from __future__ import annotations

import json
import random
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import pandas as pd

from .contact_loader import load_contact_info, format_contact_info_for_user_agent
from .common import normalize_query_budget


WIKIDATA_API_BASE = "https://www.wikidata.org/wiki/Special:EntityData"
WIKIDATA_SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
_PYTHON_VERSION = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

# Load contact information and build User-Agent with contact disclosure
try:
	_CONTACT_INFO = load_contact_info()
	_CONTACT_STRING = format_contact_info_for_user_agent(_CONTACT_INFO)
	USER_AGENT = (
		"speaker-mining/0.1 "
		f"(https://github.com/borgnetzwerk/speaker-mining; {_CONTACT_STRING}) "
		f"python/{_PYTHON_VERSION} urllib/{_PYTHON_VERSION}"
	)
except (FileNotFoundError, ValueError) as exc:
	# Re-raise with additional context about where contact file should be
	import sys as _sys
	_sys.stderr.write(f"\nERROR: Failed to initialize Wikidata contact information:\n{exc}\n")
	raise


_REQUEST_CONTEXT: dict[str, float | int | str] | None = None


def begin_request_context(
	*,
	budget_remaining: int,
	query_delay_seconds: float,
	progress_every_calls: int = 50,
	context_label: str = "wikidata",
) -> None:
	"""Initialize process-local HTTP request budget and delay context.

	Args:
		budget_remaining: Maximum allowed network requests for this run.
			Use -1 for unlimited.
		query_delay_seconds: Minimum delay between network requests.
		progress_every_calls: Emit progress output after this many calls.
			Set 0 to disable progress output.
		context_label: Human-readable stage label for progress output.
	"""
	global _REQUEST_CONTEXT
	budget_remaining = normalize_query_budget(budget_remaining)
	progress_every_calls = max(0, int(progress_every_calls))
	context_label = str(context_label or "wikidata").strip() or "wikidata"
	_REQUEST_CONTEXT = {
		"budget_remaining": budget_remaining,
		"query_delay_seconds": float(query_delay_seconds),
		"network_queries": 0,
		"last_query_time": 0.0,
		"progress_every_calls": progress_every_calls,
		"context_label": context_label,
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


def _http_get_json(
	url: str,
	accept: str = "application/json",
	timeout: int = 30,
	max_retries: int = 4,
	backoff_base_seconds: float = 1.0,
) -> dict:
	"""Fetch JSON from HTTP endpoint with User-Agent.
	
	Args:
		url: Full URL to fetch.
		accept: Accept header value.
		timeout: Request timeout in seconds. Default 30.
		max_retries: Maximum retry attempts for transient/service-load errors.
		backoff_base_seconds: Base delay for exponential backoff.
	
	Returns:
		Parsed JSON response.
	
	Raises:
		urllib.error.URLError: If request fails after retries.
		RuntimeError: If configured per-run query budget is exhausted.
	"""
	global _REQUEST_CONTEXT
	if _REQUEST_CONTEXT is None:
		raise RuntimeError(
			"Network request guard rails not initialized: begin_request_context must be called with explicit budget_remaining"
		)

	for attempt in range(max_retries + 1):
		max_queries = normalize_query_budget(_REQUEST_CONTEXT.get("budget_remaining", 0))
		used_queries = int(_REQUEST_CONTEXT.get("network_queries", 0))
		if max_queries >= 0 and used_queries >= max_queries:
			raise RuntimeError("Network query budget hit")

		delay_seconds = float(_REQUEST_CONTEXT.get("query_delay_seconds", 0.0))
		last_query_time = float(_REQUEST_CONTEXT.get("last_query_time", 0.0))
		now = time.time()
		time_since_last = now - last_query_time
		if time_since_last < delay_seconds:
			time.sleep(delay_seconds - time_since_last)

		queries_after_this_call = used_queries + 1
		_REQUEST_CONTEXT["last_query_time"] = time.time()
		_REQUEST_CONTEXT["network_queries"] = queries_after_this_call

		progress_every = int(_REQUEST_CONTEXT.get("progress_every_calls", 0) or 0)
		if progress_every > 0 and queries_after_this_call % progress_every == 0:
			context_label = str(_REQUEST_CONTEXT.get("context_label", "wikidata") or "wikidata")
			budget_label = "unlimited" if max_queries == -1 else str(max_queries)
			print(
				f"[{context_label}] Network calls used: {queries_after_this_call} / {budget_label}",
				flush=True,
			)

		try:
			req = Request(url, headers={"Accept": accept, "User-Agent": USER_AGENT})
			with urlopen(req, timeout=timeout) as response:
				payload = response.read().decode("utf-8")
			return json.loads(payload)
		except (HTTPError, URLError) as exc:
			if attempt >= max_retries:
				raise

			# Retry only transient/service-load failures with exponential backoff + jitter.
			retriable = True
			if isinstance(exc, HTTPError):
				status_code = int(getattr(exc, "code", 0) or 0)
				retriable = status_code in {429, 500, 502, 503, 504}

			if not retriable:
				raise

			sleep_seconds = (backoff_base_seconds * (2 ** attempt)) + random.uniform(0.0, 0.25)
			time.sleep(sleep_seconds)

	# Defensive fallback (unreachable under normal flow)
	raise RuntimeError("HTTP request loop exited unexpectedly")


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
	"""Compatibility wrapper that emits only canonical v2 query events.

	This function writes canonical raw event records only.
	"""
	from .event_log import write_query_event

	query_type = str(query_type or "").strip().lower()
	endpoint = "derived_local"
	source_step = "materialization_support"
	normalized_query = f"derived:{query_type}:{key}"

	if query_type == "entity":
		endpoint = "wikidata_api"
		source_step = "entity_fetch"
		normalized_query = f"entity:{key}"
	elif query_type == "property":
		endpoint = "wikidata_api"
		source_step = "property_fetch"
		normalized_query = f"property:{key}"
	elif query_type == "inlinks":
		endpoint = "wikidata_sparql"
		source_step = "inlinks_fetch"
		normalized_query = f"inlinks:{key}"
	elif query_type == "outlinks":
		source_step = "outlinks_build"
		normalized_query = f"outlinks_from_entity:{key}"

	return write_query_event(
		root,
		endpoint=endpoint,
		normalized_query=normalized_query,
		source_step=source_step,
		status="success",
		key=key,
		payload=payload if isinstance(payload, dict) else {},
		http_status=200 if endpoint != "derived_local" else None,
		error=None,
	)


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
		Tuple of (record_dict, age_days) where age_days is computed from timestamp_utc,
		or None if no matching file exists or all matches are unparseable.
	"""
	mapping = {
		"entity": "entity_fetch",
		"property": "property_fetch",
		"inlinks": "inlinks_fetch",
		"outlinks": "outlinks_build",
		"label_search": "entity_fetch",
	}
	step = mapping.get(str(query_type or "").strip().lower(), "")
	files = sorted(_raw_dir(root).glob("*.json"), reverse=True)
	for path in files:
		record = _load_raw_record(path)
		if not record:
			continue
		if record.get("event_version") != "v2":
			continue
		if record.get("source_step") != step:
			continue
		if str(record.get("key", "")) != str(key):
			continue
		ts = record.get("timestamp_utc", "")
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
