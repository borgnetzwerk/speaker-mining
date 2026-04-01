from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from uuid import uuid4

import pandas as pd

from .bootstrap import ensure_output_bootstrap, initialize_bootstrap_files, load_core_classes, load_seed_instances
from .cache import _atomic_write_df, _entity_from_payload, _latest_cached_record
from .cache import begin_request_context, end_request_context
from .class_resolver import resolve_class_path
from .checkpoint import (
    CheckpointManifest,
    clear_runtime_artifacts,
    decide_resume_mode,
    delete_checkpoint,
    restore_checkpoint_snapshot,
    write_checkpoint_manifest,
)
from .common import canonical_qid, effective_core_class_qids, iter_entity_texts, normalize_query_budget, normalize_text, pick_entity_label
from .entity import get_or_build_outlinks, get_or_fetch_entity, get_or_fetch_inlinks, get_or_fetch_property
from .inlinks import parse_inlinks_results
from .materializer import materialize_checkpoint, materialize_final
from .node_store import get_item, iter_items, upsert_discovered_item, upsert_discovered_property, upsert_expanded_item
from .triple_store import record_item_edges


@dataclass(frozen=True)
class ExpansionConfig:
    max_depth: int = 2
    max_nodes: int = 500
    total_query_budget: int = 0
    per_seed_query_budget: int = 0
    query_timeout_seconds: int = 30
    query_delay_seconds: float = 1.0
    inlinks_limit: int = 200
    cache_max_age_days: int = 365
    max_neighbors_per_node: int = 200
    network_progress_every: int = 50


@dataclass(frozen=True)
class GraphExpansionResult:
    discovered_candidates: list[dict]
    resolved_target_ids: set[str]
    unresolved_targets: list[dict]
    newly_discovered_qids: set[str]
    expanded_qids: set[str]
    checkpoint_stats: dict


def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _claim_qids(entity_doc: dict, pid: str) -> set[str]:
    claims = entity_doc.get("claims", {}) if isinstance(entity_doc.get("claims"), dict) else {}
    out: set[str] = set()
    for claim in claims.get(pid, []) or []:
        mainsnak = claim.get("mainsnak", {}) if isinstance(claim, dict) else {}
        value = (mainsnak.get("datavalue", {}) or {}).get("value")
        if isinstance(value, dict) and value.get("entity-type") == "item":
            qid = canonical_qid(value.get("id", ""))
            if qid:
                out.add(qid)
    return out


def _entity_is_class_node(entity_doc: dict) -> bool:
    return bool(_claim_qids(entity_doc, "P279"))


def _entity_p31_core_match(entity_doc: dict, core_class_qids: set[str]) -> bool:
    if not core_class_qids:
        return False
    return bool(_claim_qids(entity_doc, "P31") & core_class_qids)


def _record_outlinks_for_discovered_item(
    repo_root: Path,
    *,
    qid: str,
    entity_payload: dict,
    cache_max_age_days: int,
    discovered_at_utc: str,
    source_query_file: str,
) -> dict:
    outlinks_payload = get_or_build_outlinks(
        repo_root,
        qid,
        entity_payload,
        cache_max_age_days,
    )
    record_item_edges(
        repo_root,
        qid,
        outlinks_payload.get("edges", []),
        discovered_at_utc=discovered_at_utc,
        source_query_file=source_query_file,
    )
    return outlinks_payload


def _discover_class_chain_for_entity(
    repo_root: Path,
    *,
    entity_doc: dict,
    discovered_qids: set[str],
    config: ExpansionConfig,
    source_query_file: str,
) -> None:
    class_queue = deque(sorted(_claim_qids(entity_doc, "P31") | _claim_qids(entity_doc, "P279")))
    seen_class_qids: set[str] = set()

    while class_queue:
        class_qid = canonical_qid(class_queue.popleft())
        if not class_qid or class_qid in seen_class_qids:
            continue
        seen_class_qids.add(class_qid)

        class_payload = get_or_fetch_entity(
            repo_root,
            class_qid,
            config.cache_max_age_days,
            timeout=config.query_timeout_seconds,
        )
        class_doc = class_payload.get("entities", {}).get(class_qid, {})
        if not isinstance(class_doc, dict) or not class_doc:
            continue

        class_timestamp = _iso_now()
        upsert_discovered_item(repo_root, class_qid, class_doc, class_timestamp)
        discovered_qids.add(class_qid)
        _record_outlinks_for_discovered_item(
            repo_root,
            qid=class_qid,
            entity_payload=class_payload,
            cache_max_age_days=config.cache_max_age_days,
            discovered_at_utc=class_timestamp,
            source_query_file=source_query_file,
        )

        for parent_qid in sorted(_claim_qids(class_doc, "P279")):
            if parent_qid and parent_qid not in seen_class_qids:
                class_queue.append(parent_qid)


def is_expandable_target(
    candidate_qid: str,
    *,
    seed_qids: set[str],
    has_direct_link_to_seed: bool,
    p31_core_match: bool,
    is_class_node: bool,
) -> bool:
    qid = canonical_qid(candidate_qid)
    if not qid or is_class_node:
        return False
    if qid in seed_qids:
        return True
    return has_direct_link_to_seed and p31_core_match


def _scope_allows(mention_type: str, class_scope_hints: dict[str, set[str]], p31_values: set[str]) -> bool:
    expected = class_scope_hints.get(mention_type, set())
    if not expected:
        return True
    return bool(expected & p31_values)


def _resolve_targets_against_discovered_items(
    repo_root: Path,
    *,
    targets: list[dict],
    class_scope_hints: dict[str, set[str]],
) -> tuple[list[dict], set[str]]:
    label_index: dict[str, list[dict]] = {}
    for item in iter_items(repo_root):
        qid = canonical_qid(item.get("id", ""))
        if not qid:
            continue
        p31_values = _claim_qids(item, "P31")
        is_class = _entity_is_class_node(item)
        signatures = {normalize_text(text) for text in iter_entity_texts(item)}
        preferred = normalize_text(pick_entity_label(item))
        if preferred:
            signatures.add(preferred)
        signatures.discard("")
        if not signatures:
            continue
        candidate = {
            "qid": qid,
            "label": pick_entity_label(item) or qid,
            "p31": p31_values,
            "is_class_node": is_class,
        }
        for signature in signatures:
            label_index.setdefault(signature, []).append(candidate)

    discovered_candidates: list[dict] = []
    resolved_target_ids: set[str] = set()
    for target in targets:
        mention_id = str(target.get("mention_id", "") or "")
        mention_type = str(target.get("mention_type", "") or "")
        mention_label_raw = str(target.get("mention_label", "") or "")
        mention_label = normalize_text(mention_label_raw)
        if not mention_id or not mention_type or not mention_label:
            continue

        matched_any = False
        for candidate in sorted(label_index.get(mention_label, []), key=lambda row: row.get("qid", "")):
            if not _scope_allows(mention_type, class_scope_hints, set(candidate.get("p31", set()))):
                continue
            discovered_candidates.append(
                {
                    "mention_id": mention_id,
                    "mention_type": mention_type,
                    "mention_label": mention_label_raw,
                    "candidate_id": candidate.get("qid", ""),
                    "candidate_label": candidate.get("label", candidate.get("qid", "")),
                    "source": "graph_stage",
                    "context": str(target.get("context", "") or ""),
                }
            )
            matched_any = True

        if matched_any:
            resolved_target_ids.add(mention_id)

    dedup: dict[tuple[str, str], dict] = {}
    for row in discovered_candidates:
        dedup[(row["mention_id"], row["candidate_id"])] = row
    deduped_candidates = [dedup[key] for key in sorted(dedup)]

    return deduped_candidates, resolved_target_ids


def _write_graph_stage_handoff(repo_root: Path, discovered_candidates: list[dict], unresolved_targets: list[dict]) -> None:
    from .schemas import build_artifact_paths

    paths = build_artifact_paths(repo_root)
    resolved_columns = ["mention_id", "mention_type", "mention_label", "candidate_id", "candidate_label", "source", "context"]
    unresolved_columns = ["mention_id", "mention_type", "mention_label", "context"]

    resolved_df = pd.DataFrame(discovered_candidates) if discovered_candidates else pd.DataFrame(columns=resolved_columns)
    unresolved_df = pd.DataFrame(unresolved_targets) if unresolved_targets else pd.DataFrame(columns=unresolved_columns)

    for col in resolved_columns:
        if col not in resolved_df.columns:
            resolved_df[col] = ""
    for col in unresolved_columns:
        if col not in unresolved_df.columns:
            unresolved_df[col] = ""

    _atomic_write_df(paths.graph_stage_resolved_targets_csv, resolved_df[resolved_columns])
    _atomic_write_df(paths.graph_stage_unresolved_targets_csv, unresolved_df[unresolved_columns])


def run_seed_expansion(
    repo_root: Path,
    *,
    seed: dict,
    seed_qids: set[str],
    core_class_qids: set[str],
    total_budget_remaining: int,
    config: ExpansionConfig,
    resume_inlinks_cursor: dict | None = None,
) -> dict:
    seed_qid = canonical_qid(seed.get("wikidata_id", ""))
    if not seed_qid:
        return {
            "seed_qid": "",
            "discovered_qids": set(),
            "expanded_qids": set(),
            "network_queries": 0,
            "stop_reason": "seed_complete",
            "inlinks_cursor": None,
        }

    per_seed_budget = normalize_query_budget(config.per_seed_query_budget)
    total_budget_remaining = normalize_query_budget(total_budget_remaining)
    if per_seed_budget == 0 or total_budget_remaining == 0:
        seed_budget = 0
    elif per_seed_budget == -1:
        seed_budget = total_budget_remaining
    elif total_budget_remaining == -1:
        seed_budget = per_seed_budget
    else:
        seed_budget = min(per_seed_budget, total_budget_remaining)

    begin_request_context(
        budget_remaining=seed_budget,
        query_delay_seconds=config.query_delay_seconds,
        progress_every_calls=int(config.network_progress_every),
        context_label=f"graph_seed:{seed_qid}",
    )

    queue: deque[tuple[str, int]] = deque([(seed_qid, 0)])
    seen: set[str] = set()
    discovered_qids: set[str] = set()
    expanded_qids: set[str] = set()
    direct_link_to_seed: set[str] = set()
    inlinks_cursor: dict | None = None
    resume_cursor_consumed = False
    stop_reason = "seed_complete"
    seed_progress_last_emit = perf_counter()
    seed_progress_interval_seconds = 60.0

    try:
        while queue and len(expanded_qids) < int(config.max_nodes):
            now_progress = perf_counter()
            if now_progress - seed_progress_last_emit >= seed_progress_interval_seconds:
                print(
                    (
                        f"[graph_seed:{seed_qid}] heartbeat: queue={len(queue)} seen={len(seen)} "
                        f"discovered={len(discovered_qids)} expanded={len(expanded_qids)} depth_limit={int(config.max_depth)}"
                    ),
                    flush=True,
                )
                seed_progress_last_emit = now_progress
            qid, depth = queue.popleft()
            qid = canonical_qid(qid)
            if not qid or qid in seen or depth > int(config.max_depth):
                continue
            seen.add(qid)

            try:
                entity_payload = get_or_fetch_entity(
                    repo_root,
                    qid,
                    config.cache_max_age_days,
                    timeout=config.query_timeout_seconds,
                )
                entity_doc = entity_payload.get("entities", {}).get(qid, {})
                timestamp_utc = _iso_now()
                upsert_discovered_item(repo_root, qid, entity_doc, timestamp_utc)
                upsert_expanded_item(repo_root, qid, entity_doc, timestamp_utc)
                discovered_qids.add(qid)
                expanded_qids.add(qid)

                _discover_class_chain_for_entity(
                    repo_root,
                    entity_doc=entity_doc,
                    discovered_qids=discovered_qids,
                    config=config,
                    source_query_file="derived_local_outlinks_class_chain",
                )

                outlinks_payload = _record_outlinks_for_discovered_item(
                    repo_root,
                    qid=qid,
                    entity_payload=entity_payload,
                    cache_max_age_days=config.cache_max_age_days,
                    discovered_at_utc=timestamp_utc,
                    source_query_file="derived_local_outlinks",
                )

                for pid in outlinks_payload.get("property_ids", []):
                    prop_payload = get_or_fetch_property(
                        repo_root,
                        pid,
                        config.cache_max_age_days,
                        timeout=config.query_timeout_seconds,
                    )
                    prop_doc = prop_payload.get("entities", {}).get(pid, {})
                    upsert_discovered_property(repo_root, pid, prop_doc, timestamp_utc)

                inlink_rows_all: list[dict[str, str]] = []
                offset = 0
                page_index = 0
                if (
                    not resume_cursor_consumed
                    and isinstance(resume_inlinks_cursor, dict)
                    and canonical_qid(resume_inlinks_cursor.get("seed_qid", "")) == seed_qid
                    and canonical_qid(resume_inlinks_cursor.get("target_qid", "")) == qid
                    and not bool(resume_inlinks_cursor.get("exhausted", False))
                ):
                    # Continue after the last fully materialized inlinks page.
                    offset = max(0, int(resume_inlinks_cursor.get("offset", 0)) + int(config.inlinks_limit))
                    page_index = max(0, int(resume_inlinks_cursor.get("page_index", 0)) + 1)
                    resume_cursor_consumed = True
                while True:
                    inlinks_payload = get_or_fetch_inlinks(
                        repo_root,
                        qid,
                        config.cache_max_age_days,
                        config.inlinks_limit,
                        offset=offset,
                        timeout=config.query_timeout_seconds,
                    )
                    page_rows = parse_inlinks_results(inlinks_payload)
                    if page_rows:
                        inlink_rows_all.extend(page_rows)
                        last = page_rows[-1]
                        inlinks_cursor = {
                            "target_qid": qid,
                            "seed_qid": seed_qid,
                            "page_index": page_index,
                            "offset": offset,
                            "last_source_qid": last.get("source_qid"),
                            "last_pid": last.get("pid"),
                            "page_size": int(config.inlinks_limit),
                            "exhausted": False,
                        }
                    if len(page_rows) < int(config.inlinks_limit):
                        if inlinks_cursor is not None:
                            inlinks_cursor["exhausted"] = True
                        break
                    page_index += 1
                    offset += int(config.inlinks_limit)

                neighbor_qids: set[str] = set()
                for out in outlinks_payload.get("linked_qids", []):
                    nq = canonical_qid(out)
                    if nq:
                        neighbor_qids.add(nq)
                        if qid in seed_qids or nq in seed_qids:
                            direct_link_to_seed.add(qid)
                            direct_link_to_seed.add(nq)

                for row in inlink_rows_all:
                    source_qid = canonical_qid(row.get("source_qid", ""))
                    pid = row.get("pid", "")
                    if not source_qid:
                        continue
                    neighbor_qids.add(source_qid)
                    if qid in seed_qids or source_qid in seed_qids:
                        direct_link_to_seed.add(qid)
                        direct_link_to_seed.add(source_qid)
                    record_item_edges(
                        repo_root,
                        source_qid,
                        [{"pid": pid, "to_qid": qid}],
                        discovered_at_utc=timestamp_utc,
                        source_query_file=f"inlinks_target_{qid}",
                    )

                capped_neighbors = sorted(neighbor_qids)[: max(0, int(config.max_neighbors_per_node))]
                for candidate_qid in capped_neighbors:
                    candidate_payload = get_or_fetch_entity(
                        repo_root,
                        candidate_qid,
                        config.cache_max_age_days,
                        timeout=config.query_timeout_seconds,
                    )
                    candidate_doc = candidate_payload.get("entities", {}).get(candidate_qid, {})
                    upsert_discovered_item(repo_root, candidate_qid, candidate_doc, _iso_now())
                    discovered_qids.add(candidate_qid)

                    _record_outlinks_for_discovered_item(
                        repo_root,
                        qid=candidate_qid,
                        entity_payload=candidate_payload,
                        cache_max_age_days=config.cache_max_age_days,
                        discovered_at_utc=_iso_now(),
                        source_query_file="derived_local_outlinks_discovered_candidate",
                    )
                    _discover_class_chain_for_entity(
                        repo_root,
                        entity_doc=candidate_doc,
                        discovered_qids=discovered_qids,
                        config=config,
                        source_query_file="derived_local_outlinks_class_chain",
                    )

                    has_direct = candidate_qid in direct_link_to_seed

                    can_expand = is_expandable_target(
                        candidate_qid,
                        seed_qids=seed_qids,
                        has_direct_link_to_seed=has_direct,
                        p31_core_match=_entity_p31_core_match(candidate_doc, core_class_qids),
                        is_class_node=_entity_is_class_node(candidate_doc),
                    )
                    if can_expand and candidate_qid not in seen and depth < int(config.max_depth):
                        queue.append((candidate_qid, depth + 1))
            except RuntimeError as exc:
                if str(exc) == "Network query budget hit":
                    stop_reason = "per_seed_budget_exhausted"
                    break
                raise
            except Exception:
                stop_reason = "crash_recovery"
                break
    finally:
        network_queries = int(end_request_context())

    # Distinguish a fully processed seed frontier from other completion cases.
    if stop_reason == "seed_complete" and not queue:
        stop_reason = "queue_exhausted"

    return {
        "seed_qid": seed_qid,
        "discovered_qids": discovered_qids,
        "expanded_qids": expanded_qids,
        "network_queries": network_queries,
        "stop_reason": stop_reason,
        "inlinks_cursor": inlinks_cursor,
    }


def _filter_seed_instances_by_broadcasting_program(
    repo_root: Path,
    *,
    seeds: list[dict],
    expected_class_qid: str | None,
    cache_max_age_days: int,
    timeout_seconds: int,
    request_budget_remaining: int,
    query_delay_seconds: float,
    network_progress_every: int,
) -> tuple[list[dict], list[dict], int]:
    expected_qid = canonical_qid(expected_class_qid or "")
    if not expected_qid:
        return seeds, [], 0

    accepted: list[dict] = []
    skipped: list[dict] = []

    def _local_entity(qid: str) -> dict:
        entity_qid = canonical_qid(qid)
        if not entity_qid:
            return {}
        node = get_item(repo_root, entity_qid)
        if isinstance(node, dict) and node:
            return node
        cached = _latest_cached_record(repo_root, "entity", entity_qid)
        if not cached:
            return {}
        return _entity_from_payload(cached[0].get("payload", {}), entity_qid)

    def _cached_seed_entity(seed_qid: str) -> dict | None:
        entity_doc = _local_entity(seed_qid)
        return entity_doc or None

    begin_request_context(
        budget_remaining=normalize_query_budget(request_budget_remaining),
        query_delay_seconds=float(query_delay_seconds),
        progress_every_calls=int(network_progress_every),
        context_label="seed_filter:class_prefetch",
    )

    def _get_class_entity_for_filter(class_qid: str) -> dict:
        class_doc = _local_entity(class_qid)
        if class_doc:
            return class_doc
        try:
            payload = get_or_fetch_entity(
                repo_root,
                class_qid,
                cache_max_age_days,
                timeout=timeout_seconds,
            )
        except Exception:
            return {}
        entity_doc = payload.get("entities", {}).get(class_qid, {}) if isinstance(payload, dict) else {}
        if isinstance(entity_doc, dict) and entity_doc:
            upsert_discovered_item(repo_root, class_qid, entity_doc, _iso_now())
            return entity_doc
        return {}

    try:
        for seed in seeds:
            seed_qid = canonical_qid(seed.get("wikidata_id", ""))
            if not seed_qid:
                skipped.append({"label": str(seed.get("label", "") or ""), "wikidata_id": str(seed.get("wikidata_id", "") or ""), "reason": "invalid_wikidata_id"})
                continue
            entity_doc = _cached_seed_entity(seed_qid)
            if not entity_doc:
                accepted.append(seed)
                continue
            p31_values = _claim_qids(entity_doc, "P31")
            if expected_qid in p31_values:
                accepted.append(seed)
                continue

            # Respect subclass paths when seed type is a subclass of broadcasting program.
            subclass_match = False
            unresolved_class_doc = False
            for class_qid in sorted(p31_values):
                class_doc = _get_class_entity_for_filter(class_qid)
                if not class_doc:
                    unresolved_class_doc = True
                    continue
                resolution = resolve_class_path(class_doc, {expected_qid}, _local_entity)
                if bool(resolution.get("subclass_of_core_class", False)):
                    subclass_match = True
                    break

            if subclass_match:
                accepted.append(seed)
                continue

            # Be conservative when class hierarchy cannot be resolved under budget/network constraints.
            if unresolved_class_doc:
                accepted.append(seed)
                continue

            skipped.append({"label": str(seed.get("label", "") or ""), "wikidata_id": seed_qid, "reason": "not_broadcasting_program_instance"})
    finally:
        network_queries = int(end_request_context())

    return accepted, skipped, network_queries


def run_graph_expansion_stage(
    repo_root: Path,
    *,
    seeds: list[dict],
    targets: list[dict],
    core_class_qids: set[str],
    config: ExpansionConfig,
    requested_mode: str | None = None,
) -> GraphExpansionResult:
    repo_root = Path(repo_root)
    stage_t0 = perf_counter()
    print("[graph_stage] Starting graph expansion stage", flush=True)
    resume_info = decide_resume_mode(repo_root, requested_mode)

    if resume_info["mode"] == "restart":
        clear_runtime_artifacts(repo_root)
        resume_info = decide_resume_mode(repo_root, "append")
    elif resume_info["mode"] == "revert" and resume_info.get("has_checkpoint"):
        latest_path = resume_info.get("latest_checkpoint_path", "")
        previous_path = resume_info.get("previous_checkpoint_path", "")
        if latest_path:
            delete_checkpoint(Path(latest_path))
        if previous_path:
            restore_checkpoint_snapshot(repo_root, Path(previous_path))
        else:
            clear_runtime_artifacts(repo_root)
        resume_info = decide_resume_mode(repo_root, "append")

    ensure_output_bootstrap(repo_root)
    print(
        f"[graph_stage] Resume mode={resume_info.get('mode')} has_checkpoint={bool(resume_info.get('has_checkpoint'))}",
        flush=True,
    )

    setup_core_classes = load_core_classes(repo_root)
    setup_seeds, skipped_seed_rows = load_seed_instances(repo_root)
    initialize_bootstrap_files(repo_root, setup_core_classes, setup_seeds)

    if not seeds:
        seeds = setup_seeds

    class_rows = setup_core_classes
    class_by_filename = {
        str(row.get("filename", "")): canonical_qid(row.get("wikidata_id", ""))
        for row in class_rows
        if canonical_qid(row.get("wikidata_id", ""))
    }
    prefilter_budget_remaining = normalize_query_budget(config.total_query_budget)
    seeds, skipped_non_instance, prefilter_network_queries = _filter_seed_instances_by_broadcasting_program(
        repo_root,
        seeds=seeds,
        expected_class_qid=class_by_filename.get("broadcasting_programs", ""),
        cache_max_age_days=config.cache_max_age_days,
        timeout_seconds=config.query_timeout_seconds,
        request_budget_remaining=prefilter_budget_remaining,
        query_delay_seconds=config.query_delay_seconds,
        network_progress_every=config.network_progress_every,
    )

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid4().hex[:8]
    start_timestamp = _iso_now()
    if resume_info["mode"] == "append" and resume_info.get("has_checkpoint"):
        latest = resume_info.get("latest_checkpoint") or {}
        run_id = str(latest.get("run_id", "") or run_id)
        start_timestamp = str(latest.get("start_timestamp", "") or start_timestamp)

    total_queries_used = int(prefilter_network_queries)
    if resume_info["mode"] == "append" and resume_info.get("has_checkpoint"):
        latest = resume_info.get("latest_checkpoint") or {}
        total_queries_used = max(0, int(latest.get("total_queries", 0) or 0))
    initial_total_queries_used = int(total_queries_used)

    seed_qids = [canonical_qid(seed.get("wikidata_id", "")) for seed in seeds]
    seed_qids = [qid for qid in seed_qids if qid]
    seed_set = set(seed_qids)

    if not core_class_qids:
        core_class_qids = {canonical_qid(row.get("wikidata_id", "")) for row in setup_core_classes if canonical_qid(row.get("wikidata_id", ""))}
    core_class_qids = effective_core_class_qids(core_class_qids)

    class_scope_hints = {
        "person": {class_by_filename.get("persons", "")},
        "organization": {class_by_filename.get("organizations", "")},
        "episode": {class_by_filename.get("episodes", "")},
        "season": {class_by_filename.get("series", "")},
        "topic": {class_by_filename.get("topics", "")},
        "broadcasting_program": {class_by_filename.get("broadcasting_programs", "")},
    }
    class_scope_hints = {k: {qid for qid in v if qid} for k, v in class_scope_hints.items()}

    total_budget_remaining = normalize_query_budget(config.total_query_budget)
    if total_budget_remaining > 0:
        total_budget_remaining = max(0, total_budget_remaining - int(prefilter_network_queries))
    discovered_candidates: list[dict] = []
    resolved_target_ids: set[str] = set()
    newly_discovered_qids: set[str] = set()
    expanded_qids: set[str] = set()
    checkpoint_stats: dict = {
        "run_id": run_id,
        "skipped_seed_rows": int(len(skipped_seed_rows)),
        "skipped_non_broadcasting_instance_rows": int(len(skipped_non_instance)),
        "seed_filter_network_queries": int(prefilter_network_queries),
    }
    last_stop_reason = "seed_complete"
    last_cursor = None

    # Execute seed-by-seed in CSV order.
    seeds_done = 0
    seeds_processed_this_run = 0
    start_seed_index = 0
    resume_cursor = None
    if resume_info["mode"] == "append" and resume_info["has_checkpoint"]:
        latest = resume_info.get("latest_checkpoint") or {}
        start_seed_index = max(0, int(latest.get("seeds_completed", 0) or 0))
        resume_cursor = latest.get("inlinks_cursor")
        if latest.get("stop_reason", "") == "seed_complete":
            resume_cursor = None

    start_seed_index = min(start_seed_index, len(seeds))

    seeds_done = start_seed_index
    for local_seed_offset, seed in enumerate(seeds[start_seed_index:]):
        if total_budget_remaining == 0:
            last_stop_reason = "total_query_budget_exhausted"
            break
        seeds_processed_this_run += 1
        seed_index = start_seed_index + local_seed_offset
        seed_qid = canonical_qid(seed.get("wikidata_id", ""))
        seed_t0 = perf_counter()
        print(
            f"[graph_stage] Seed {seed_index + 1}/{len(seeds)} start qid={seed_qid or 'NA'}",
            flush=True,
        )
        seed_resume_cursor = resume_cursor if local_seed_offset == 0 else None
        seed_summary = run_seed_expansion(
            repo_root,
            seed=seed,
            seed_qids=seed_set,
            core_class_qids=core_class_qids,
            total_budget_remaining=total_budget_remaining,
            config=config,
            resume_inlinks_cursor=seed_resume_cursor,
        )
        newly_discovered_qids |= set(seed_summary.get("discovered_qids", set()))
        expanded_qids |= set(seed_summary.get("expanded_qids", set()))
        used = int(seed_summary.get("network_queries", 0))
        seed_elapsed = perf_counter() - seed_t0
        print(
            (
                f"[graph_stage] Seed {seed_index + 1}/{len(seeds)} done "
                f"stop_reason={seed_summary.get('stop_reason', 'seed_complete')} "
                f"network_queries={used} elapsed={seed_elapsed:.2f}s"
            ),
            flush=True,
        )
        total_queries_used += used
        if total_budget_remaining > 0:
            total_budget_remaining = max(0, total_budget_remaining - used)
        last_stop_reason = str(seed_summary.get("stop_reason", "seed_complete"))
        last_cursor = seed_summary.get("inlinks_cursor")

        if last_stop_reason == "seed_complete":
            seeds_done = seed_index + 1
        else:
            seeds_done = seed_index

        checkpoint_ts = _iso_now()
        print("[graph_stage] Materialize checkpoint start", flush=True)
        materialize_checkpoint_t0 = perf_counter()
        materialize_stats = materialize_checkpoint(
            repo_root,
            run_id=run_id,
            checkpoint_ts=checkpoint_ts,
            seed_id=str(seed_summary.get("seed_qid", "")),
        )
        checkpoint_elapsed = perf_counter() - materialize_checkpoint_t0
        print(f"[graph_stage] Materialize checkpoint done in {checkpoint_elapsed:.2f}s", flush=True)
        manifest = CheckpointManifest(
            run_id=run_id,
            start_timestamp=start_timestamp,
            latest_checkpoint_timestamp=checkpoint_ts,
            stop_reason=last_stop_reason,
            seeds_completed=seeds_done,
            seeds_remaining=max(0, len(seed_qids) - seeds_done),
            total_nodes_discovered={"items": int(len(newly_discovered_qids))},
            total_nodes_expanded={"items": int(len(expanded_qids))},
            total_queries=total_queries_used,
            inlinks_cursor=last_cursor,
            incomplete=(last_stop_reason != "seed_complete"),
        )
        write_checkpoint_manifest(repo_root, manifest)
        checkpoint_stats = {
            **materialize_stats,
            "run_id": run_id,
            "resume_mode": resume_info["mode"],
            "resume_has_checkpoint": resume_info["has_checkpoint"],
            "seeds_completed": seeds_done,
            "seeds_remaining": max(0, len(seed_qids) - seeds_done),
            "stop_reason": last_stop_reason,
        }

        if last_stop_reason in {"per_seed_budget_exhausted", "total_query_budget_exhausted"}:
            if total_budget_remaining == 0 and normalize_query_budget(config.total_query_budget) >= 0:
                last_stop_reason = "total_query_budget_exhausted"
            break

        if total_budget_remaining == 0 and normalize_query_budget(config.total_query_budget) >= 0:
            last_stop_reason = "total_query_budget_exhausted"
            break

    print("[graph_stage] Final materialization start", flush=True)
    final_materialize_t0 = perf_counter()
    final_stats = materialize_final(repo_root, run_id=run_id)
    print(f"[graph_stage] Final materialization done in {perf_counter() - final_materialize_t0:.2f}s", flush=True)
    checkpoint_stats.update(final_stats)
    checkpoint_stats["stop_reason"] = last_stop_reason
    checkpoint_stats["total_nodes_discovered"] = int(len(newly_discovered_qids))
    checkpoint_stats["total_nodes_expanded"] = int(len(expanded_qids))
    checkpoint_stats["total_queries"] = int(total_queries_used)
    checkpoint_stats["stage_a_network_queries"] = int(total_queries_used)
    checkpoint_stats["total_queries_before_run"] = int(initial_total_queries_used)
    checkpoint_stats["stage_a_network_queries_this_run"] = int(max(0, total_queries_used - initial_total_queries_used))
    checkpoint_stats["resume_mode"] = resume_info["mode"]
    checkpoint_stats["resume_has_checkpoint"] = resume_info["has_checkpoint"]

    discovered_candidates, resolved_target_ids = _resolve_targets_against_discovered_items(
        repo_root,
        targets=targets,
        class_scope_hints=class_scope_hints,
    )
    unresolved_targets = [t for t in targets if t.get("mention_id") not in resolved_target_ids]
    _write_graph_stage_handoff(repo_root, discovered_candidates, unresolved_targets)

    if seeds_processed_this_run > 0:
        final_checkpoint_ts = _iso_now()
        final_manifest = CheckpointManifest(
            run_id=run_id,
            start_timestamp=start_timestamp,
            latest_checkpoint_timestamp=final_checkpoint_ts,
            stop_reason=last_stop_reason,
            seeds_completed=seeds_done,
            seeds_remaining=max(0, len(seed_qids) - seeds_done),
            total_nodes_discovered={"items": int(len(newly_discovered_qids))},
            total_nodes_expanded={"items": int(len(expanded_qids))},
            total_queries=total_queries_used,
            inlinks_cursor=last_cursor,
            incomplete=(last_stop_reason == "crash_recovery"),
        )
        write_checkpoint_manifest(repo_root, final_manifest)

    checkpoint_stats["start_seed_index"] = int(start_seed_index)
    checkpoint_stats["seed_count"] = int(len(seeds))
    checkpoint_stats["stage_elapsed_seconds"] = round(perf_counter() - stage_t0, 3)
    print(
        (
            "[graph_stage] Completed graph expansion stage "
            f"in {checkpoint_stats['stage_elapsed_seconds']:.2f}s "
            f"with total_queries={checkpoint_stats['total_queries']}"
        ),
        flush=True,
    )
    return GraphExpansionResult(
        discovered_candidates=discovered_candidates,
        resolved_target_ids=resolved_target_ids,
        unresolved_targets=unresolved_targets,
        newly_discovered_qids=newly_discovered_qids,
        expanded_qids=expanded_qids,
        checkpoint_stats=checkpoint_stats,
    )
