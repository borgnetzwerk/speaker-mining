"""Pure BFS tree expansion algorithm for Wikidata candidate discovery.

Implements breadth-first search expansion through entity relationships,
matching discovered entities against pre-loaded mention targets.
"""
from __future__ import annotations

from collections import deque
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .aggregates import rebuild_aggregates_from_raw
from .cache import (
	_atomic_write_text,
	_ensure_dirs,
	_wikidata_dir,
	_write_raw_query_record,
	begin_request_context,
	end_request_context,
)
from .classes import update_class_cache
from .common import canonical_qid, iter_entity_texts, normalize_text, pick_entity_label
from .entity import get_or_build_outlinks, get_or_fetch_entity, get_or_fetch_inlinks
from .inlinks import parse_inlinks_results


@dataclass(frozen=True)
class BFSConfig:
	"""Configuration for BFS tree expansion algorithm.
	
	Attributes:
		max_depth: Maximum tree expansion depth (0 = seeds only, 1 = seed neighbors, etc.).
		max_nodes: Maximum total nodes to expand before stopping.
		max_queries_per_run: Maximum network queries (entity, inlinks, SPARQL) per execution.
			Cached results do not count. Set to 0 for unlimited (not recommended).
		query_timeout_seconds: Timeout in seconds for each HTTP request. Default 30s.
		query_delay_seconds: Delay in seconds between consecutive network queries (rate limiting).
			Avoids overwhelming the Wikidata endpoint.
		inlinks_limit: Maximum inlinks to fetch per entity (SPARQL LIMIT).
		cache_max_age_days: Cache age threshold in days; older cached records are refreshed.
	"""
	max_depth: int = 2
	max_nodes: int = 500
	max_queries_per_run: int = 1  # 0 = unlimited
	query_timeout_seconds: int = 30
	query_delay_seconds: float = 1.0
	inlinks_limit: int = 200
	cache_max_age_days: int = 365
	max_neighbors_per_match: int = 200


def _match_index_path(root: Path) -> Path:
	return _wikidata_dir(root) / "match_index.json"


def _load_match_index(root: Path) -> set[str]:
	path = _match_index_path(root)
	if not path.exists():
		return set()
	try:
		payload = json.loads(path.read_text(encoding="utf-8"))
		keys = payload.get("keys", []) if isinstance(payload, dict) else []
		return {str(key) for key in keys}
	except Exception:
		return set()


def _write_match_index(root: Path, keys: set[str]) -> None:
	path = _match_index_path(root)
	_atomic_write_text(path, json.dumps({"keys": sorted(keys)}, ensure_ascii=False, indent=2))


def _build_target_index(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
	"""Build normalized-text index for fast mention lookups.
	
	Creates a mapping from normalized mention labels to mention records.
	Enables O(1) candidate discovery when scanning entity text signatures.
	
	Args:
		rows: List of mention records with mention_label field.
	
	Returns:
		Dict mapping normalized_text → list of mention dicts with that label.
	"""
	index: dict[str, list[dict[str, str]]] = {}
	for row in rows:
		key = normalize_text(row.get("mention_label", ""))
		if not key:
			continue
		index.setdefault(key, []).append(row)
	return index


def _scan_entity_match_rows(
	qid: str,
	entity_payload: dict,
	outlinks_payload: dict,
	inlinks_payload: dict,
	target_index: dict[str, list[dict[str, str]]],
) -> list[dict[str, str]]:
	"""Scan an entity's signatures against mention targets.
	
	Extracts all text signatures from an entity (labels, aliases, Q-ID, linked Q-IDs, properties)
	and checks each against the mention target index. Creates candidate rows for all matches.
	
	Candidate rows are deduplicated by (mention_id, candidate_id) pair to avoid duplicates.
	
	Args:
		qid: Entity Q-ID being scanned.
		entity_payload: Wikidata API response dict.
		outlinks_payload: Output of get_or_build_outlinks (linked Q-IDs, property IDs).
		inlinks_payload: SPARQL response with incoming relationships.
		target_index: Mention target index from _build_target_index.
	
	Returns:
		List of candidate dicts with keys: mention_id, mention_type, mention_label, 
		candidate_id, candidate_label, source, context.
		Deduplicated by (mention_id, candidate_id).
	"""
	from .cache import _entity_from_payload
	
	entity_doc = _entity_from_payload(entity_payload, qid)
	candidate_label = pick_entity_label(entity_doc) or qid

	# Collect all text signatures from entity, Q-ID, linked entities, properties
	signatures: set[str] = set()
	for text in iter_entity_texts(entity_doc):
		signatures.add(normalize_text(text))

	signatures.add(normalize_text(qid))
	for linked_qid in outlinks_payload.get("linked_qids", []):
		signatures.add(normalize_text(linked_qid))
	for pid in outlinks_payload.get("property_ids", []):
		signatures.add(normalize_text(pid))
	for row in parse_inlinks_results(inlinks_payload):
		signatures.add(normalize_text(row.get("source_qid", "")))
		signatures.add(normalize_text(row.get("pid", "")))

	# Match each signature against target index
	rows: list[dict[str, str]] = []
	for signature in signatures:
		for mention in target_index.get(signature, []):
			rows.append(
				{
					"mention_id": mention["mention_id"],
					"mention_type": mention["mention_type"],
					"mention_label": mention["mention_label"],
					"candidate_id": qid,
					"candidate_label": candidate_label,
					"source": "wikidata_tree_match",
					"context": mention.get("context", ""),
				}
			)

	if not rows:
		return rows

	# Deduplicate by (mention_id, candidate_id)
	dedup: dict[tuple[str, str], dict[str, str]] = {}
	for row in rows:
		dedup[(row["mention_id"], row["candidate_id"])] = row
	return list(dedup.values())


def run_bfs_expansion(
	root: str | Path,
	seeds: list[dict],
	target_rows: list[dict],
	*,
	max_depth: int = 2,
	max_nodes: int = 500,
	max_queries_per_run: int = 1,
	query_timeout_seconds: int = 30,
	query_delay_seconds: float = 1.0,
	inlinks_limit: int = 200,
	cache_max_age_days: int = 365,
	max_neighbors_per_match: int = 200,
) -> dict[str, Any]:
	"""Execute cache-first BFS tree expansion for candidate discovery.
	
	Implements a breadth-first search algorithm:
	  1. Extract seed Q-IDs from pre-loaded seeds (already loaded by caller)
	  2. Build a normalized-text index from pre-loaded target rows
	  3. Initialize a queue with seed Q-IDs at depth 0
	  4. While queue is not empty and expanded_nodes < max_nodes:
	     a. Pop a (qid, depth) pair from the queue
	     b. Skip if already visited, depth > max_depth, or invalid Q-ID
	     c. Fetch entity, outlinks, and inlinks (cache-first strategy)
	        Request budget and delay are enforced inside the HTTP request layer
	     d. Scan entity signatures against mention targets
	     e. If matches found, record them and enqueue neighbor nodes (match-gated to conserve API calls)
	  5. Rebuild aggregate CSV outputs from all recorded raw files
	  6. Return summary of execution
	
	Cache-first design: all API responses stored as timestamped raw files,
	rebuilt into aggregate CSVs, ensuring no data loss and idempotent reruns.
	
	Args:
		root: Repository root path.
		seeds: Pre-loaded broadcasting program seed dicts with wikidata_id field.
		target_rows: Pre-loaded list of mention target dicts (union of episodes, publications, 
			seasons, persons, topics) with mention_label and mention_type fields.
		max_depth: Maximum tree expansion depth (default 2).
		max_nodes: Maximum total nodes to expand (default 500).
		max_queries_per_run: Maximum network queries (entity, inlinks, SPARQL) per execution.
			Cached results do not count. Set to 0 for unlimited (default 1).
		query_timeout_seconds: Timeout in seconds for each HTTP request (default 30).
		query_delay_seconds: Delay in seconds between consecutive network queries (default 1.0).
		inlinks_limit: Maximum inlinks per entity (default 200).
		cache_max_age_days: Cache age threshold in days (default 365).
	
	Returns:
		Dict with execution summary:
		  - seed_qids: List of seed Q-IDs extracted from input seeds
		  - expanded_nodes: Total nodes expanded
		  - network_queries: Total network query calls made (cached results do not count)
		  - discovered_candidates: Total candidate matches found
		  - budget_exhausted: True if run stopped due to request budget
		  - queued_neighbors: Count of neighbors enqueued for expansion
		  - expanded_due_to_match: Count of match events that triggered expansion
		  - skipped_duplicate_match_events: Count of candidate matches skipped as duplicates
		  - new_unique_candidates: Count of new unique candidate matches
		  - max_depth: Configured max expansion depth
		  - raw_files, candidate_rows, candidates_csv, etc. (from rebuild_aggregates_from_raw)
	"""
	repo_root = Path(root)
	_ensure_dirs(repo_root)

	config = BFSConfig(
		max_depth=max_depth,
		max_nodes=max_nodes,
		max_queries_per_run=max_queries_per_run,
		query_timeout_seconds=query_timeout_seconds,
		query_delay_seconds=query_delay_seconds,
		inlinks_limit=inlinks_limit,
		cache_max_age_days=cache_max_age_days,
		max_neighbors_per_match=max_neighbors_per_match,
	)

	# Extract seed Q-IDs from pre-loaded seeds
	seed_qids = [canonical_qid(seed.get("wikidata_id", "")) for seed in seeds]
	seed_qids = [qid for qid in seed_qids if qid]

	if not seed_qids:
		# Return early if no valid seeds
		agg_summary = rebuild_aggregates_from_raw(repo_root)
		agg_summary.update(
			{
				"seed_qids": [],
				"expanded_nodes": 0,
				"network_queries": 0,
				"discovered_candidates": 0,
				"max_depth": config.max_depth,
			}
		)
		return agg_summary

	# Build index from pre-loaded target rows
	target_index = _build_target_index(target_rows)

	# Initialize BFS queue with seeds at depth 0
	queue: deque[tuple[str, int]] = deque((qid, 0) for qid in seed_qids)
	seen: set[str] = set()
	discovered_candidates = 0
	expanded_nodes = 0
	network_queries = 0
	budget_exhausted = False
	queued_neighbors = 0
	expanded_due_to_match = 0
	skipped_duplicate_match_events = 0
	new_unique_candidates = 0
	match_index_updated = False
	emitted_match_keys = _load_match_index(repo_root)
	begin_request_context(config.max_queries_per_run, config.query_delay_seconds)

	# BFS tree expansion with match-driven recursion
	try:
		while queue and expanded_nodes < config.max_nodes:
			qid, depth = queue.popleft()
			qid = canonical_qid(qid)
			if not qid or qid in seen or depth > config.max_depth:
				continue

			seen.add(qid)
			expanded_nodes += 1

			# Fetch entity and relationships (cache-first) with timeout.
			# Delay and budget checks happen exactly at network request in _http_get_json.
			try:
				entity_payload = get_or_fetch_entity(
					repo_root,
					qid,
					config.cache_max_age_days,
					timeout=config.query_timeout_seconds,
				)

				update_class_cache(
					repo_root,
					qid,
					entity_payload,
					config.cache_max_age_days,
					timeout=config.query_timeout_seconds,
				)

				outlinks_payload = get_or_build_outlinks(
					repo_root, qid, entity_payload, config.cache_max_age_days
				)

				inlinks_payload = get_or_fetch_inlinks(
					repo_root,
					qid,
					config.cache_max_age_days,
					config.inlinks_limit,
					timeout=config.query_timeout_seconds,
				)
			except RuntimeError as exc:
				if str(exc) == "Network query budget hit":
					budget_exhausted = True
					break
				raise

			# Scan for matching mentions
			candidate_rows = _scan_entity_match_rows(
				qid,
				entity_payload,
				outlinks_payload,
				inlinks_payload,
				target_index,
			)

			if candidate_rows:
				filtered_rows: list[dict[str, str]] = []
				for row in candidate_rows:
					match_key = f"{row['mention_id']}|{row['candidate_id']}"
					if match_key in emitted_match_keys:
						skipped_duplicate_match_events += 1
						continue
					emitted_match_keys.add(match_key)
					filtered_rows.append(row)
				if filtered_rows:
					candidate_rows = filtered_rows
					match_index_updated = True
				else:
					candidate_rows = []

			# If candidates found, record them and expand neighbors (API conservation priority)
			if candidate_rows:
				discovered_candidates += len(candidate_rows)
				new_unique_candidates += len(candidate_rows)
				_write_raw_query_record(
					repo_root,
					"candidate_match",
					qid,
					{"depth": depth, "rows": candidate_rows},
					source="matching_scan",
				)

				# Match-driven recursion: expand neighbors only if current node produced candidates
				if depth < config.max_depth:
					neighbors = set(outlinks_payload.get("linked_qids", []))
					for row in parse_inlinks_results(inlinks_payload):
						src = canonical_qid(row.get("source_qid", ""))
						if src:
							neighbors.add(src)

					neighbor_list = sorted(neighbors)
					if config.max_neighbors_per_match > 0:
						neighbor_list = neighbor_list[: config.max_neighbors_per_match]
					queued_neighbors += len(neighbor_list)
					expanded_due_to_match += 1
					for neighbor in neighbor_list:
						if neighbor not in seen:
							queue.append((neighbor, depth + 1))
	finally:
		network_queries = end_request_context()
		if match_index_updated:
			_write_match_index(repo_root, emitted_match_keys)

	# Rebuild aggregate outputs and return summary
	agg_summary = rebuild_aggregates_from_raw(repo_root)
	agg_summary.update(
		{
			"seed_qids": seed_qids,
			"expanded_nodes": expanded_nodes,
			"network_queries": network_queries,
			"discovered_candidates": discovered_candidates,
			"budget_exhausted": budget_exhausted,
			"queued_neighbors": queued_neighbors,
			"expanded_due_to_match": expanded_due_to_match,
			"skipped_duplicate_match_events": skipped_duplicate_match_events,
			"new_unique_candidates": new_unique_candidates,
			"max_depth": config.max_depth,
		}
	)
	return agg_summary
