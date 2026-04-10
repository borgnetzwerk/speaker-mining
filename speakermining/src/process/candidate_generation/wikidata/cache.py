"""Cache and I/O utilities for Wikidata queries.

Provides atomic file writes, HTTP access, timestamp management, and cache lookups
for storing and retrieving Wikidata query results.
"""
from __future__ import annotations

import json
import hashlib
import random
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import pandas as pd

from process.io_guardrails import atomic_write_csv, atomic_write_parquet, atomic_write_text

from .contact_loader import load_contact_info, format_contact_info_for_user_agent
from .common import canonical_qid, normalize_query_budget
from .event_log import get_query_event_field, iter_query_events
from .graceful_shutdown import should_terminate


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


_REQUEST_CONTEXT: dict[str, object] | None = None
_LATEST_QUERY_EVENT_INDEX: dict[tuple[str, str, str], dict] = {}
_LATEST_QUERY_EVENT_INDEX_PRIMED: set[str] = set()


def _cache_root_key(root: Path) -> str:
	return str(Path(root).resolve())


def _latest_query_event_index_key(root: Path, source_step: str, key: str) -> tuple[str, str, str]:
	return _cache_root_key(root), str(source_step or ""), str(key or "")


def _remember_latest_cached_record(root: Path, record: dict, *, force: bool = False) -> None:
	if not isinstance(record, dict) or record.get("event_version") != "v3":
		return
	source_step = str(get_query_event_field(record, "source_step", "") or "")
	key = str(get_query_event_field(record, "key", "") or "")
	if not source_step or not key:
		return
	index_key = _latest_query_event_index_key(root, source_step, key)
	if force:
		_LATEST_QUERY_EVENT_INDEX[index_key] = dict(record)
		return
	current = _LATEST_QUERY_EVENT_INDEX.get(index_key)
	current_seq = int(current.get("sequence_num", -1) or -1) if isinstance(current, dict) else -1
	record_seq = int(record.get("sequence_num", -1) or -1)
	if current is None or record_seq >= current_seq:
		_LATEST_QUERY_EVENT_INDEX[index_key] = dict(record)


def _prime_latest_cached_record_index(root: Path) -> None:
	root_key = _cache_root_key(root)
	if root_key in _LATEST_QUERY_EVENT_INDEX_PRIMED:
		return
	latest: dict[tuple[str, str], dict] = {}
	for record in iter_query_events(Path(root)) or []:
		if not isinstance(record, dict) or record.get("event_version") != "v3":
			continue
		source_step = str(get_query_event_field(record, "source_step", "") or "")
		key = str(get_query_event_field(record, "key", "") or "")
		if not source_step or not key:
			continue
		current = latest.get((source_step, key))
		current_seq = int(current.get("sequence_num", -1) or -1) if isinstance(current, dict) else -1
		record_seq = int(record.get("sequence_num", -1) or -1)
		if current is None or record_seq >= current_seq:
			latest[(source_step, key)] = dict(record)
	for (source_step, key), record in latest.items():
		_LATEST_QUERY_EVENT_INDEX[_latest_query_event_index_key(root, source_step, key)] = record
	_LATEST_QUERY_EVENT_INDEX_PRIMED.add(root_key)


def reset_latest_cached_record_index(root: Path | None = None) -> None:
	if root is None:
		_LATEST_QUERY_EVENT_INDEX.clear()
		_LATEST_QUERY_EVENT_INDEX_PRIMED.clear()
		return
	root_key = _cache_root_key(root)
	_LATEST_QUERY_EVENT_INDEX_PRIMED.discard(root_key)
	for index_key in [key for key in list(_LATEST_QUERY_EVENT_INDEX) if key[0] == root_key]:
		_LATEST_QUERY_EVENT_INDEX.pop(index_key, None)


def _infer_network_metadata(url: str) -> tuple[str, str, str, str]:
	"""Infer endpoint, request kind, query identity, and entity id from URL."""
	parsed = urlparse(str(url or ""))
	host = (parsed.netloc or "").lower()
	path = parsed.path or ""
	query_map = parse_qs(parsed.query or "")
	is_wikidata_api = (
		"wikidata.org" in host
		and (
			"Special:EntityData" in path
			or path.rstrip("/").endswith("/w/api.php")
		)
	)
	endpoint = "wikidata_api" if is_wikidata_api else "wikidata_sparql"
	request_kind = "sparql_query"
	query_identity = parsed.query or path
	entity_qid = ""

	if endpoint == "wikidata_api":
		action = str(query_map.get("action", [""])[0] or "").strip().lower()
		ids_raw = str(query_map.get("ids", [""])[0] or "").strip()
		id_token = ids_raw.split("|")[0] if ids_raw else ""
		qid_from_ids = canonical_qid(id_token)
		if action == "wbgetentities":
			request_kind = "entity_or_property_by_id"
			entity_qid = qid_from_ids
			if entity_qid.startswith("Q"):
				request_kind = "entity_by_qid"
			elif str(id_token).upper().startswith("P"):
				request_kind = "property_by_pid"
			query_identity = parsed.query or path
		elif action == "wbsearchentities":
			request_kind = "label_search"
			query_identity = parsed.query or path
		else:
			request_kind = "entity_or_property_by_id"
			last_token = path.rstrip("/").split("/")[-1]
			if last_token.endswith(".json"):
				last_token = last_token[:-5]
			entity_qid = canonical_qid(last_token)
			if entity_qid.startswith("Q"):
				request_kind = "entity_by_qid"
			elif entity_qid.startswith("P"):
				request_kind = "property_by_pid"
			query_identity = entity_qid or last_token or parsed.query or path
	else:
		raw_query = ""
		if "query" in query_map and query_map.get("query"):
			raw_query = str(query_map.get("query", [""])[0])
		query_identity = raw_query or parsed.query or path

	query_hash = hashlib.md5(f"{endpoint}|{query_identity}".encode("utf-8")).hexdigest()
	return endpoint, request_kind, query_hash, entity_qid


def _emit_request_event(event_type: str, payload: dict) -> None:
	"""Emit a structured request event when an emitter is configured."""
	if _REQUEST_CONTEXT is None:
		return
	emitter = _REQUEST_CONTEXT.get("event_emitter")
	if not callable(emitter):
		return
	phase = str(_REQUEST_CONTEXT.get("event_phase", _REQUEST_CONTEXT.get("context_label", "wikidata")) or "wikidata")
	event_payload = {
		"event_type": str(event_type or "unknown"),
		"phase": phase,
	}
	event_payload.update(payload if isinstance(payload, dict) else {})
	emitter(**event_payload)


def begin_request_context(
	*,
	budget_remaining: int,
	query_delay_seconds: float,
	progress_every_calls: int = 50,
	progress_every_seconds: float = 60.0,
	http_max_retries: int = 4,
	http_backoff_base_seconds: float = 1.0,
	context_label: str = "wikidata",
	event_emitter=None,
	event_phase: str | None = None,
) -> None:
	"""Initialize process-local HTTP request budget and delay context.

	Args:
		budget_remaining: Maximum allowed network requests for this run.
			Use -1 for unlimited.
		query_delay_seconds: Minimum delay between network requests.
		progress_every_calls: Emit progress output after this many calls.
			Set 0 to disable progress output.
		progress_every_seconds: Emit progress output at least once per interval
			while network calls are still being made. Set 0 to disable.
		http_max_retries: Default retry attempts for transient HTTP/network errors.
		http_backoff_base_seconds: Base delay for exponential retry backoff.
		context_label: Human-readable stage label for progress output.
	"""
	global _REQUEST_CONTEXT
	budget_remaining = normalize_query_budget(budget_remaining)
	progress_every_calls = max(0, int(progress_every_calls))
	progress_every_seconds = max(0.0, float(progress_every_seconds))
	http_max_retries = max(0, int(http_max_retries))
	http_backoff_base_seconds = max(0.0, float(http_backoff_base_seconds))
	context_label = str(context_label or "wikidata").strip() or "wikidata"
	now_ts = time.time()
	_REQUEST_CONTEXT = {
		"budget_remaining": budget_remaining,
		"query_delay_seconds": float(query_delay_seconds),
		"network_queries": 0,
		"last_query_time": 0.0,
		"progress_every_calls": progress_every_calls,
		"progress_every_seconds": progress_every_seconds,
		"http_max_retries": http_max_retries,
		"http_backoff_base_seconds": http_backoff_base_seconds,
		"started_at": now_ts,
		"last_progress_at": now_ts,
		"context_label": context_label,
		"event_emitter": event_emitter,
		"event_phase": str(event_phase or context_label or "wikidata"),
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
	atomic_write_text(path, text, encoding="utf-8")


def _atomic_write_df(path: Path, df: pd.DataFrame) -> None:
	"""Write DataFrame atomically via temp file + rename.
	
	Args:
		path: Target CSV file path.
		df: DataFrame to write.
	"""
	atomic_write_csv(path, df, index=False)


def _atomic_write_parquet_df(path: Path, df: pd.DataFrame) -> None:
	"""Write DataFrame atomically as Parquet via temp file + rename."""
	atomic_write_parquet(path, df, index=False)


def _http_get_json(
	url: str,
	accept: str = "application/json",
	timeout: int = 30,
	max_retries: int | None = None,
	backoff_base_seconds: float | None = None,
) -> dict:
	"""Fetch JSON from HTTP endpoint with User-Agent.
	
	Args:
		url: Full URL to fetch.
		accept: Accept header value.
		timeout: Request timeout in seconds. Default 30.
		max_retries: Maximum retry attempts for transient/service-load errors.
			If None, use request-context default.
		backoff_base_seconds: Base delay for exponential backoff.
			If None, use request-context default.
	
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
	if max_retries is None:
		max_retries = max(0, int(_REQUEST_CONTEXT.get("http_max_retries", 4) or 0))
	else:
		max_retries = max(0, int(max_retries))
	if backoff_base_seconds is None:
		backoff_base_seconds = max(0.0, float(_REQUEST_CONTEXT.get("http_backoff_base_seconds", 1.0) or 0.0))
	else:
		backoff_base_seconds = max(0.0, float(backoff_base_seconds))

	for attempt in range(max_retries + 1):
		if should_terminate():
			raise RuntimeError("Termination requested")
		max_queries = normalize_query_budget(_REQUEST_CONTEXT.get("budget_remaining", 0))
		used_queries = int(_REQUEST_CONTEXT.get("network_queries", 0))
		endpoint, request_kind, query_hash, entity_qid = _infer_network_metadata(url)
		if max_queries >= 0 and used_queries >= max_queries:
			_emit_request_event(
				"network_budget_blocked",
				{
					"message": "network budget exhausted before call",
					"network": {
						"endpoint": endpoint,
						"request_kind": request_kind,
						"decision": "skip_budget",
					},
					"rate_limit": {
						"query_delay_seconds_configured": float(_REQUEST_CONTEXT.get("query_delay_seconds", 0.0) or 0.0),
						"query_delay_seconds_effective": float(_REQUEST_CONTEXT.get("query_delay_seconds", 0.0) or 0.0),
						"backoff_factor": 1.0,
					},
					"budget": {
						"max_queries_per_run": int(max_queries),
						"queries_used_before": int(used_queries),
						"queries_used_after": int(used_queries),
					},
					"entity": {"qid": entity_qid} if entity_qid else None,
					"query": {"query_hash": query_hash},
					"result": {"status": "skipped"},
				},
			)
			raise RuntimeError("Network query budget hit")

		delay_seconds = float(_REQUEST_CONTEXT.get("query_delay_seconds", 0.0))
		last_query_time = float(_REQUEST_CONTEXT.get("last_query_time", 0.0))
		now = time.time()
		time_since_last = now - last_query_time
		if time_since_last < delay_seconds:
			time.sleep(delay_seconds - time_since_last)

		decision = "retry" if attempt > 0 else "call"
		_emit_request_event(
			"network_decision",
			{
				"message": "network decision taken",
				"network": {
					"endpoint": endpoint,
					"request_kind": request_kind,
					"decision": decision,
				},
				"rate_limit": {
					"query_delay_seconds_configured": float(_REQUEST_CONTEXT.get("query_delay_seconds", 0.0) or 0.0),
					"query_delay_seconds_effective": float(delay_seconds),
					"backoff_factor": 1.0,
				},
				"budget": {
					"max_queries_per_run": int(max_queries),
					"queries_used_before": int(used_queries),
					"queries_used_after": int(used_queries),
				},
				"entity": {"qid": entity_qid} if entity_qid else None,
				"query": {"query_hash": query_hash},
			},
		)

		queries_after_this_call = used_queries + 1
		_REQUEST_CONTEXT["last_query_time"] = time.time()
		_REQUEST_CONTEXT["network_queries"] = queries_after_this_call
		request_t0 = time.time()
		_emit_request_event(
			"network_call_started",
			{
				"message": "network call started",
				"network": {
					"endpoint": endpoint,
					"request_kind": request_kind,
					"decision": "call",
				},
				"rate_limit": {
					"query_delay_seconds_configured": float(_REQUEST_CONTEXT.get("query_delay_seconds", 0.0) or 0.0),
					"query_delay_seconds_effective": float(delay_seconds),
					"backoff_factor": 1.0,
				},
				"budget": {
					"max_queries_per_run": int(max_queries),
					"queries_used_before": int(used_queries),
					"queries_used_after": int(queries_after_this_call),
				},
				"entity": {"qid": entity_qid} if entity_qid else None,
				"query": {"query_hash": query_hash},
			},
		)

		progress_every = int(_REQUEST_CONTEXT.get("progress_every_calls", 0) or 0)
		progress_seconds = float(_REQUEST_CONTEXT.get("progress_every_seconds", 0.0) or 0.0)
		started_at = float(_REQUEST_CONTEXT.get("started_at", _REQUEST_CONTEXT.get("last_query_time", time.time())) or time.time())
		last_progress_at = float(_REQUEST_CONTEXT.get("last_progress_at", started_at) or started_at)
		now_progress = time.time()
		by_calls = progress_every > 0 and queries_after_this_call % progress_every == 0
		by_time = progress_seconds > 0.0 and (now_progress - last_progress_at) >= progress_seconds
		if by_calls or by_time:
			context_label = str(_REQUEST_CONTEXT.get("context_label", "wikidata") or "wikidata")
			budget_label = "unlimited" if max_queries == -1 else str(max_queries)
			elapsed_seconds = max(0.0, now_progress - started_at)
			calls_per_minute = (queries_after_this_call * 60.0 / elapsed_seconds) if elapsed_seconds > 0 else 0.0
			print(
				(
					f"[{context_label}] Network calls used: {queries_after_this_call} / {budget_label} "
					f"elapsed={elapsed_seconds:.1f}s rate={calls_per_minute:.2f}/min"
				),
				flush=True,
			)
			_REQUEST_CONTEXT["last_progress_at"] = now_progress

		try:
			req = Request(url, headers={"Accept": accept, "User-Agent": USER_AGENT})
			with urlopen(req, timeout=timeout) as response:
				http_status = int(getattr(response, "status", 200) or 200)
				payload = response.read().decode("utf-8")
			duration_ms = max(0, int((time.time() - request_t0) * 1000.0))
			_emit_request_event(
				"network_call_finished",
				{
					"message": "network call finished",
					"network": {
						"endpoint": endpoint,
						"request_kind": request_kind,
						"decision": "call",
					},
					"rate_limit": {
						"query_delay_seconds_configured": float(_REQUEST_CONTEXT.get("query_delay_seconds", 0.0) or 0.0),
						"query_delay_seconds_effective": float(delay_seconds),
						"backoff_factor": 1.0,
					},
					"budget": {
						"max_queries_per_run": int(max_queries),
						"queries_used_before": int(used_queries),
						"queries_used_after": int(queries_after_this_call),
					},
					"entity": {"qid": entity_qid} if entity_qid else None,
					"query": {"query_hash": query_hash},
					"result": {
						"status": "success",
						"http_status": int(http_status),
						"duration_ms": int(duration_ms),
					},
				},
			)
			return json.loads(payload)
		except (HTTPError, URLError, TimeoutError) as exc:
			duration_ms = max(0, int((time.time() - request_t0) * 1000.0))
			http_status = int(getattr(exc, "code", 0) or 0)
			if isinstance(exc, HTTPError):
				status_text = "http_error"
			elif isinstance(exc, TimeoutError):
				status_text = "timeout"
			else:
				status_text = "network_error"
			_emit_request_event(
				"network_error",
				{
					"message": f"network call failed: {type(exc).__name__}",
					"network": {
						"endpoint": endpoint,
						"request_kind": request_kind,
						"decision": "abort",
					},
					"rate_limit": {
						"query_delay_seconds_configured": float(_REQUEST_CONTEXT.get("query_delay_seconds", 0.0) or 0.0),
						"query_delay_seconds_effective": float(delay_seconds),
						"backoff_factor": 1.0,
					},
					"budget": {
						"max_queries_per_run": int(max_queries),
						"queries_used_before": int(used_queries),
						"queries_used_after": int(queries_after_this_call),
					},
					"entity": {"qid": entity_qid} if entity_qid else None,
					"query": {"query_hash": query_hash},
					"result": {
						"status": status_text,
						"http_status": int(http_status) if http_status > 0 else None,
						"duration_ms": int(duration_ms),
						"error": str(exc),
					},
				},
			)
			if attempt >= max_retries:
				raise

			# Retry only transient/service-load failures with exponential backoff + jitter.
			retriable = True
			if isinstance(exc, HTTPError):
				status_code = int(getattr(exc, "code", 0) or 0)
				retriable = status_code in {429, 500, 502, 503, 504}
			elif isinstance(exc, TimeoutError):
				retriable = True

			if not retriable:
				raise

			sleep_seconds = (backoff_base_seconds * (2 ** attempt)) + random.uniform(0.0, 0.25)
			configured_delay = float(_REQUEST_CONTEXT.get("query_delay_seconds", 0.0) or 0.0)
			if configured_delay > 0.0:
				backoff_factor = (configured_delay + sleep_seconds) / configured_delay
			else:
				backoff_factor = 1.0
			_emit_request_event(
				"network_backoff_applied",
				{
					"message": "transient failure; retry backoff applied",
					"network": {
						"endpoint": endpoint,
						"request_kind": request_kind,
						"decision": "retry",
					},
					"rate_limit": {
						"query_delay_seconds_configured": configured_delay,
						"query_delay_seconds_effective": configured_delay + sleep_seconds,
						"backoff_factor": float(backoff_factor),
					},
					"budget": {
						"max_queries_per_run": int(max_queries),
						"queries_used_before": int(used_queries),
						"queries_used_after": int(queries_after_this_call),
					},
					"entity": {"qid": entity_qid} if entity_qid else None,
					"query": {"query_hash": query_hash},
					"result": {
						"status": "retry",
						"http_status": int(status_code) if isinstance(exc, HTTPError) else None,
						"duration_ms": int(duration_ms),
						"error": str(exc),
					},
				},
			)
			if should_terminate():
				raise RuntimeError("Termination requested")
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

	The first lookup for a repository primes a process-local index by scanning the
	event history once. After that, repeated lookups are O(1) and avoid rescanning
	the full chunk chain.
	
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
	if not step:
		return None

	root_key = _cache_root_key(root)
	index_key = _latest_query_event_index_key(root, step, key)
	cached = _LATEST_QUERY_EVENT_INDEX.get(index_key)
	if cached is None and root_key not in _LATEST_QUERY_EVENT_INDEX_PRIMED:
		_prime_latest_cached_record_index(Path(root))
		cached = _LATEST_QUERY_EVENT_INDEX.get(index_key)
	if cached is None:
		return None

	ts = str(cached.get("timestamp_utc", "") or "")
	try:
		dt = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
	except Exception:
		return None
	age_days = (_now_utc() - dt).total_seconds() / 86400.0
	return cached, age_days


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
	response_payload = payload
	if isinstance(payload, dict) and isinstance(payload.get("response_data"), dict):
		response_payload = payload.get("response_data", {})
	entities = response_payload.get("entities", {}) if isinstance(response_payload, dict) else {}
	return entities.get(qid, {})
