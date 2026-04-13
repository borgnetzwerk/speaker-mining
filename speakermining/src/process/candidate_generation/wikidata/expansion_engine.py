from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
from time import perf_counter
from uuid import uuid4

import pandas as pd

from .bootstrap import ensure_output_bootstrap, initialize_bootstrap_files, load_core_classes, load_seed_instances
from .cache import _atomic_write_df, _entity_from_payload, _latest_cached_record
from .cache import begin_request_context, end_request_context
from .class_resolver import RecoveredLineageEvidence, load_recovered_class_hierarchy, resolve_class_path
from .checkpoint import (
    CheckpointManifest,
    decide_resume_mode,
    restore_checkpoint_snapshot,
    write_checkpoint_manifest,
)
from .common import canonical_qid, effective_core_class_qids, iter_entity_texts, normalize_query_budget, normalize_text, pick_entity_label
from .entity import get_or_build_outlinks, get_or_fetch_entities_batch, get_or_fetch_entity, get_or_fetch_inlinks, get_or_fetch_property
from .graceful_shutdown import should_terminate
from .inlinks import parse_inlinks_results
from .materializer import materialize_final
from .node_store import flush_node_store, get_item, iter_items, upsert_discovered_item, upsert_discovered_property, upsert_expanded_item
from .event_log import (
    build_class_membership_resolved_event,
    build_entity_discovered_event,
    build_entity_expanded_event,
    build_expansion_decision_event,
)
from .phase_contracts import PhaseContract, phase_contract_payload, phase_outcome_payload
from .schemas import build_artifact_paths
from .triple_store import record_item_edges
from .triple_store import flush_triple_events
from ...notebook_event_log import NOTEBOOK_21_ID, get_or_create_notebook_logger


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
    hydrate_class_chains_for_discovered_entities: bool = False


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


def _shutdown_path(repo_root: Path) -> Path:
    return build_artifact_paths(Path(repo_root)).wikidata_dir / ".shutdown"


def _termination_requested(repo_root: Path) -> bool:
    return should_terminate(_shutdown_path(Path(repo_root)))


def _is_termination_runtime_error(exc: RuntimeError) -> bool:
    return "Termination requested" in str(exc)


def _lineage_resolution_policy() -> str:
    policy = str(os.getenv("WIKIDATA_LINEAGE_RESOLUTION_POLICY", "runtime_then_recovered_then_network") or "").strip()
    return policy or "runtime_then_recovered_then_network"


def _load_recovered_lineage_evidence(repo_root: Path) -> tuple[RecoveredLineageEvidence | None, str]:
    reverse_engineering_path = (
        Path(repo_root)
        / "data"
        / "20_candidate_generation"
        / "wikidata"
        / "reverse_engineering_potential"
        / "class_hierarchy.csv"
    )
    if reverse_engineering_path.exists():
        return load_recovered_class_hierarchy(reverse_engineering_path), "reverse_engineering_potential"

    projection_path = build_artifact_paths(Path(repo_root)).class_hierarchy_csv
    if projection_path.exists():
        return load_recovered_class_hierarchy(projection_path), "projection_cache"

    return None, "none"


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
    event_emitter=None,
    event_phase: str | None = None,
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
        event_emitter=event_emitter,
        event_phase=event_phase,
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
    if not bool(config.hydrate_class_chains_for_discovered_entities):
        return

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
            event_emitter=None,
            event_phase=None,
        )

        for parent_qid in sorted(_claim_qids(class_doc, "P279")):
            if parent_qid and parent_qid not in seen_class_qids:
                class_queue.append(parent_qid)


def is_expandable_target(
    candidate_qid: str,
    *,
    seed_qids: set[str],
    relevant_qids: set[str],
    seed_neighbor_degree: int | None,
    direct_or_subclass_core_match: bool,
    is_class_node: bool,
) -> bool:
    qid = canonical_qid(candidate_qid)
    if not qid or is_class_node:
        return False
    if qid in relevant_qids:
        return True
    if qid in seed_qids:
        return True
    if not direct_or_subclass_core_match:
        return False
    if seed_neighbor_degree is None:
        return False
    return int(seed_neighbor_degree) in {1, 2}


def _load_relevant_qids_from_projection(repo_root: Path) -> set[str]:
    paths = build_artifact_paths(Path(repo_root))
    if not paths.relevancy_csv.exists() or paths.relevancy_csv.stat().st_size == 0:
        return set()
    try:
        frame = pd.read_csv(paths.relevancy_csv)
    except Exception:
        return set()
    if frame.empty:
        return set()

    out: set[str] = set()
    for row in frame.to_dict(orient="records"):
        qid = canonical_qid(str(row.get("qid", "") or ""))
        if not qid:
            continue
        token = str(row.get("relevant", "") or "").strip().lower()
        if token in {"1", "true", "yes", "y", "on"}:
            out.add(qid)
    return out


def _entity_subclass_core_match(
    entity_doc: dict,
    core_class_qids: set[str],
    get_entity,
    *,
    recovered_lineage: RecoveredLineageEvidence | None = None,
    resolution_policy: str = "runtime_then_recovered_then_network",
) -> bool:
    if not core_class_qids:
        return False
    if not isinstance(entity_doc, dict) or not entity_doc:
        return False
    resolution = resolve_class_path(
        entity_doc,
        core_class_qids,
        get_entity,
        recovered_lineage=recovered_lineage,
        resolution_policy=resolution_policy,
    )
    return bool(resolution.get("subclass_of_core_class", False))


def _resolve_direct_or_subclass_core_match(
    repo_root: Path,
    *,
    entity_doc: dict,
    core_class_qids: set[str],
    cache_max_age_days: int,
    timeout_seconds: int,
    discovered_qids: set[str] | None = None,
    recovered_lineage: RecoveredLineageEvidence | None = None,
    resolution_policy: str = "runtime_then_recovered_then_network",
) -> bool:
    if _entity_p31_core_match(entity_doc, core_class_qids):
        return True

    local_cache: dict[str, dict] = {}

    def _lookup_entity(qid: str) -> dict | None:
        qid_norm = canonical_qid(qid)
        if not qid_norm:
            return None
        if qid_norm in local_cache:
            return local_cache[qid_norm]

        local = get_item(repo_root, qid_norm)
        if isinstance(local, dict) and local:
            local_cache[qid_norm] = local
            return local

        try:
            payload = get_or_fetch_entity(
                repo_root,
                qid_norm,
                cache_max_age_days,
                timeout=timeout_seconds,
            )
        except Exception:
            return None
        fetched = payload.get("entities", {}).get(qid_norm, {}) if isinstance(payload, dict) else {}
        if isinstance(fetched, dict) and fetched:
            upsert_discovered_item(repo_root, qid_norm, fetched, _iso_now())
            if discovered_qids is not None:
                discovered_qids.add(qid_norm)
            local_cache[qid_norm] = fetched
            return fetched
        return None

    return _entity_subclass_core_match(
        entity_doc,
        core_class_qids,
        _lookup_entity,
        recovered_lineage=recovered_lineage,
        resolution_policy=resolution_policy,
    )


def resolve_direct_or_subclass_core_match_for_entity(
    repo_root: Path,
    *,
    entity_doc: dict,
    core_class_qids: set[str],
    cache_max_age_days: int,
    timeout_seconds: int,
    discovered_qids: set[str] | None = None,
    recovered_lineage: RecoveredLineageEvidence | None = None,
    resolution_policy: str | None = None,
) -> bool:
    """Public wrapper used by non-Stage-A paths for canonical class matching."""
    return _resolve_direct_or_subclass_core_match(
        repo_root,
        entity_doc=entity_doc,
        core_class_qids=core_class_qids,
        cache_max_age_days=cache_max_age_days,
        timeout_seconds=timeout_seconds,
        discovered_qids=discovered_qids,
        recovered_lineage=(
            recovered_lineage
            if recovered_lineage is not None
            else _load_recovered_lineage_evidence(repo_root)[0]
        ),
        resolution_policy=(resolution_policy or _lineage_resolution_policy()),
    )


def _score_neighbor_candidate(
    repo_root: Path,
    *,
    candidate_qid: str,
    direct_link_to_seed: set[str],
    core_class_qids: set[str],
) -> int:
    score = 0
    qid = canonical_qid(candidate_qid)
    if not qid:
        return score
    if qid in direct_link_to_seed:
        score += 100

    node = get_item(repo_root, qid)
    if isinstance(node, dict) and node:
        if _entity_p31_core_match(node, core_class_qids):
            score += 80
        if _entity_subclass_core_match(node, core_class_qids, lambda class_qid: get_item(repo_root, class_qid)):
            score += 60
        discovered_at = str(node.get("discovered_at_utc", "") or "")
        expanded_at = str(node.get("expanded_at_utc", "") or "")
        if discovered_at and not expanded_at:
            score += 10
    return score


def _rank_neighbors_for_cap(
    repo_root: Path,
    *,
    neighbor_qids: set[str],
    direct_link_to_seed: set[str],
    core_class_qids: set[str],
    max_neighbors_per_node: int,
) -> list[str]:
    scored = [
        (
            canonical_qid(candidate_qid),
            _score_neighbor_candidate(
                repo_root,
                candidate_qid=candidate_qid,
                direct_link_to_seed=direct_link_to_seed,
                core_class_qids=core_class_qids,
            ),
        )
        for candidate_qid in sorted(neighbor_qids)
        if canonical_qid(candidate_qid)
    ]
    scored = sorted(scored, key=lambda pair: (-pair[1], pair[0]))
    max_neighbors = max(0, int(max_neighbors_per_node))
    if max_neighbors == 0:
        return []
    return [qid for qid, _score in scored[:max_neighbors]]


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
    flush_persistence: bool = True,
    event_emitter=None,
    event_phase: str = "stage_a_graph_expansion",
    recovered_lineage: RecoveredLineageEvidence | None = None,
    resolution_policy: str = "runtime_then_recovered_then_network",
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
        event_emitter=event_emitter,
        event_phase=event_phase,
    )

    queue: deque[tuple[str, int]] = deque([(seed_qid, 0)])
    seen: set[str] = set()
    discovered_qids: set[str] = set()
    expanded_qids: set[str] = set()
    direct_link_to_seed: set[str] = set()
    seed_neighbor_degree_by_qid: dict[str, int] = {seed_qid: 0}
    relevant_qids = _load_relevant_qids_from_projection(repo_root)
    relevant_qids.update(seed_qids)
    neighbor_prefetch_batches_attempted = 0
    neighbor_prefetch_batches_succeeded = 0
    neighbor_prefetch_candidates_total = 0
    inlinks_cursor: dict | None = None
    resume_cursor_consumed = False
    stop_reason = "seed_complete"
    seed_progress_last_emit = perf_counter()
    seed_progress_interval_seconds = 60.0

    try:
        while queue and len(expanded_qids) < int(config.max_nodes):
            if _termination_requested(repo_root):
                stop_reason = "user_interrupted"
                break
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
            known_degree = seed_neighbor_degree_by_qid.get(qid)
            if not qid or qid in seen or depth > int(config.max_depth):
                continue
            if known_degree is not None and depth > int(known_degree):
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
                
                # Emit domain events for discovery and expansion
                if callable(event_emitter):
                    entity_label = pick_entity_label(entity_doc)
                    event_emitter(
                        event_type="entity_discovered",
                        phase=event_phase,
                        message=f"entity discovered: {qid} ({entity_label})",
                        entity={"qid": qid, "label": entity_label},
                        extra=build_entity_discovered_event(
                            qid=qid,
                            label=entity_label,
                            source_step="entity_fetch",
                            discovery_method="seed_neighbor",
                        ).get("payload", {}),
                    )
                    event_emitter(
                        event_type="entity_expanded",
                        phase=event_phase,
                        message=f"entity expanded: {qid}",
                        entity={"qid": qid, "label": entity_label},
                        extra=build_entity_expanded_event(
                            qid=qid,
                            label=entity_label,
                            expansion_type="neighbors",
                        ).get("payload", {}),
                    )

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
                    event_emitter=event_emitter,
                    event_phase=event_phase,
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
                    if _termination_requested(repo_root):
                        stop_reason = "user_interrupted"
                        break
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

                if stop_reason == "user_interrupted":
                    break

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
                        event_emitter=event_emitter,
                        event_phase=event_phase,
                    )

                capped_neighbors = _rank_neighbors_for_cap(
                    repo_root,
                    neighbor_qids=neighbor_qids,
                    direct_link_to_seed=direct_link_to_seed,
                    core_class_qids=core_class_qids,
                    max_neighbors_per_node=config.max_neighbors_per_node,
                )
                if len(capped_neighbors) > 1:
                    neighbor_prefetch_batches_attempted += 1
                    neighbor_prefetch_candidates_total += len(capped_neighbors)
                    try:
                        get_or_fetch_entities_batch(
                            repo_root,
                            capped_neighbors,
                            config.cache_max_age_days,
                            timeout=config.query_timeout_seconds,
                        )
                        neighbor_prefetch_batches_succeeded += 1
                    except Exception:
                        pass
                for candidate_qid in capped_neighbors:
                    if _termination_requested(repo_root):
                        stop_reason = "user_interrupted"
                        break
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
                        event_emitter=event_emitter,
                        event_phase=event_phase,
                    )
                    _discover_class_chain_for_entity(
                        repo_root,
                        entity_doc=candidate_doc,
                        discovered_qids=discovered_qids,
                        config=config,
                        source_query_file="derived_local_outlinks_class_chain",
                    )

                    inferred_degree = int(depth) + 1
                    prior_degree = seed_neighbor_degree_by_qid.get(candidate_qid)
                    candidate_seed_neighbor_degree = inferred_degree if prior_degree is None else min(prior_degree, inferred_degree)
                    seed_neighbor_degree_by_qid[candidate_qid] = candidate_seed_neighbor_degree

                    has_direct = candidate_seed_neighbor_degree == 1
                    direct_or_subclass_core_match = _resolve_direct_or_subclass_core_match(
                        repo_root,
                        entity_doc=candidate_doc,
                        core_class_qids=core_class_qids,
                        cache_max_age_days=config.cache_max_age_days,
                        timeout_seconds=config.query_timeout_seconds,
                        discovered_qids=discovered_qids,
                        recovered_lineage=recovered_lineage,
                        resolution_policy=resolution_policy,
                    )

                    can_expand = is_expandable_target(
                        candidate_qid,
                        seed_qids=seed_qids,
                        relevant_qids=relevant_qids,
                        seed_neighbor_degree=candidate_seed_neighbor_degree,
                        direct_or_subclass_core_match=direct_or_subclass_core_match,
                        is_class_node=_entity_is_class_node(candidate_doc),
                    )
                    if callable(event_emitter):
                        decision = "queue_for_expansion" if can_expand and candidate_qid not in seen and depth < int(config.max_depth) else "skip_expansion"
                        decision_reason = "eligible_neighbor" if decision == "queue_for_expansion" else "not_expandable_or_depth_limit"
                        event_emitter(
                            event_type="expansion_decision",
                            phase=event_phase,
                            message=f"expansion decision for {candidate_qid}: {decision}",
                            entity={"qid": candidate_qid, "label": pick_entity_label(candidate_doc) or candidate_qid},
                            extra=build_expansion_decision_event(
                                qid=candidate_qid,
                                label=pick_entity_label(candidate_doc) or candidate_qid,
                                decision=decision,
                                decision_reason=decision_reason,
                                eligibility={
                                    "has_direct_link_to_seed": bool(has_direct),
                                    "seed_neighbor_degree": int(candidate_seed_neighbor_degree),
                                    "direct_or_subclass_core_match": bool(direct_or_subclass_core_match),
                                    "p31_core_match": bool(_entity_p31_core_match(candidate_doc, core_class_qids)),
                                    "is_class_node": bool(_entity_is_class_node(candidate_doc)),
                                    "depth": int(depth),
                                    "max_depth": int(config.max_depth),
                                },
                            ).get("payload", {}),
                        )
                    if can_expand and candidate_qid not in seen and depth < int(config.max_depth):
                        queue.append((candidate_qid, depth + 1))
                if stop_reason == "user_interrupted":
                    break
            except RuntimeError as exc:
                if str(exc) == "Network query budget hit":
                    stop_reason = "per_seed_budget_exhausted"
                    break
                if _is_termination_runtime_error(exc) or _termination_requested(repo_root):
                    stop_reason = "user_interrupted"
                    break
                raise
            except Exception:
                if _termination_requested(repo_root):
                    stop_reason = "user_interrupted"
                    break
                stop_reason = "crash_recovery"
                break
    finally:
        network_queries = int(end_request_context())
        if flush_persistence:
            flush_node_store(repo_root)
            flush_triple_events(repo_root)

    # Distinguish a fully processed seed frontier from other completion cases.
    if stop_reason == "seed_complete" and not queue:
        stop_reason = "queue_exhausted"

    return {
        "seed_qid": seed_qid,
        "discovered_qids": discovered_qids,
        "expanded_qids": expanded_qids,
        "network_queries": network_queries,
        "neighbor_prefetch_batches_attempted": int(neighbor_prefetch_batches_attempted),
        "neighbor_prefetch_batches_succeeded": int(neighbor_prefetch_batches_succeeded),
        "neighbor_prefetch_candidates_total": int(neighbor_prefetch_candidates_total),
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
    event_emitter=None,
    event_phase: str = "stage_a_graph_expansion",
    recovered_lineage: RecoveredLineageEvidence | None = None,
    resolution_policy: str = "runtime_then_recovered_then_network",
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
        event_emitter=event_emitter,
        event_phase=event_phase,
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
            if _termination_requested(repo_root):
                break
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
                resolution = resolve_class_path(
                    class_doc,
                    {expected_qid},
                    _local_entity,
                    on_resolved=(
                        (lambda result, class_qid=class_qid: event_emitter(
                            event_type="class_membership_resolved",
                            phase=event_phase,
                            message=f"class membership resolved for {class_qid}",
                            entity={"qid": class_qid, "label": pick_entity_label(class_doc) or class_qid},
                            extra=build_class_membership_resolved_event(
                                entity_qid=class_qid,
                                class_id=str(result.get("class_id", "") or ""),
                                path_to_core_class=str(result.get("path_to_core_class", "") or ""),
                                subclass_of_core_class=bool(result.get("subclass_of_core_class", False)),
                                is_class_node=bool(result.get("is_class_node", False)),
                                payload={"resolution_reason": str(result.get("resolution_reason", ""))},
                            ).get("payload", {}),
                        )) if callable(event_emitter) else None
                    ),
                    recovered_lineage=recovered_lineage,
                    resolution_policy=resolution_policy,
                )
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
    notebook_logger = get_or_create_notebook_logger(repo_root, NOTEBOOK_21_ID)
    contract = PhaseContract(
        phase="stage_a_graph_expansion",
        owner="expansion_engine",
        input_contract="seed_rows + targets + core_class_qids + config",
        output_contract="checkpoint_stats + discovered_candidates + unresolved_targets",
    )
    notebook_logger.append_event(
        event_type="phase_contract_declared",
        phase="stage_a_graph_expansion",
        message="phase contract declared",
        extra={"phase_contract": phase_contract_payload(contract)},
    )
    notebook_logger.log_phase_started("stage_a_graph_expansion", message="graph expansion stage started")
    stage_t0 = perf_counter()
    recovered_lineage, recovered_lineage_source = _load_recovered_lineage_evidence(repo_root)
    resolution_policy = _lineage_resolution_policy()
    print(
        f"[graph_stage] lineage policy={resolution_policy} recovered_source={recovered_lineage_source}",
        flush=True,
    )
    notebook_logger.append_event(
        event_type="lineage_resolution_config",
        phase="stage_a_graph_expansion",
        message="lineage resolution configuration",
        extra={
            "resolution_policy": resolution_policy,
            "recovered_lineage_source": recovered_lineage_source,
            "phase_contract": phase_contract_payload(contract),
        },
    )
    print("[graph_stage] Starting graph expansion stage", flush=True)
    resume_info = decide_resume_mode(repo_root, requested_mode)

    if resume_info["mode"] == "revert" and resume_info.get("has_checkpoint"):
        previous_path = resume_info.get("previous_checkpoint_path", "")
        if previous_path:
            restore_checkpoint_snapshot(repo_root, Path(previous_path))
            previous_manifest = resume_info.get("previous_checkpoint") or {}
            resume_info = {
                **resume_info,
                "mode": "append",
                "has_checkpoint": True,
                "latest_checkpoint": previous_manifest,
                "latest_checkpoint_path": str(previous_path),
            }
        else:
            print(
                "[graph_stage] revert requested but no previous checkpoint exists; continuing in append mode",
                flush=True,
            )
            resume_info = decide_resume_mode(repo_root, "append")

    ensure_output_bootstrap(repo_root)
    print(
        (
            f"[graph_stage] Resume mode={resume_info.get('mode')} has_checkpoint={bool(resume_info.get('has_checkpoint'))}; "
            f"seed scan starts at program 1 and skips completed seeds"
        ),
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
        event_emitter=notebook_logger.append_event,
        event_phase="stage_a_graph_expansion",
        recovered_lineage=recovered_lineage,
        resolution_policy=resolution_policy,
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
    stage_neighbor_prefetch_batches_attempted = 0
    stage_neighbor_prefetch_batches_succeeded = 0
    stage_neighbor_prefetch_candidates_total = 0

    # Execute seed-by-seed in CSV order.
    seeds_processed_this_run = 0

    completed_seed_count = 0
    resume_cursor = None
    if resume_info["mode"] == "append" and resume_info.get("has_checkpoint"):
        latest = resume_info.get("latest_checkpoint") or {}
        completed_seed_count = max(0, int(latest.get("seeds_completed", 0) or 0))
        resume_cursor = latest.get("inlinks_cursor")
        if latest.get("stop_reason", "") == "seed_complete":
            resume_cursor = None

    completed_seed_count = min(completed_seed_count, len(seeds))
    seeds_done = completed_seed_count
    interrupted_before_seed_loop = False
    for seed_index, seed in enumerate(seeds):
        if seed_index < completed_seed_count:
            print(
                f"[graph_stage] Seed {seed_index + 1}/{len(seeds)} already complete; skipping",
                flush=True,
            )
            continue
        if _termination_requested(repo_root):
            last_stop_reason = "user_interrupted"
            interrupted_before_seed_loop = True
            break
        if total_budget_remaining == 0:
            last_stop_reason = "total_query_budget_exhausted"
            break
        seeds_processed_this_run += 1
        seed_qid = canonical_qid(seed.get("wikidata_id", ""))
        seed_t0 = perf_counter()
        print(
            f"[graph_stage] Seed {seed_index + 1}/{len(seeds)} start qid={seed_qid or 'NA'}",
            flush=True,
        )
        seed_resume_cursor = resume_cursor if seed_index == completed_seed_count else None
        seed_summary = run_seed_expansion(
            repo_root,
            seed=seed,
            seed_qids=seed_set,
            core_class_qids=core_class_qids,
            total_budget_remaining=total_budget_remaining,
            config=config,
            resume_inlinks_cursor=seed_resume_cursor,
            event_emitter=notebook_logger.append_event,
            event_phase="stage_a_graph_expansion",
            recovered_lineage=recovered_lineage,
            resolution_policy=resolution_policy,
        )
        newly_discovered_qids |= set(seed_summary.get("discovered_qids", set()))
        expanded_qids |= set(seed_summary.get("expanded_qids", set()))
        used = int(seed_summary.get("network_queries", 0))
        stage_neighbor_prefetch_batches_attempted += int(seed_summary.get("neighbor_prefetch_batches_attempted", 0) or 0)
        stage_neighbor_prefetch_batches_succeeded += int(seed_summary.get("neighbor_prefetch_batches_succeeded", 0) or 0)
        stage_neighbor_prefetch_candidates_total += int(seed_summary.get("neighbor_prefetch_candidates_total", 0) or 0)
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

        if last_stop_reason == "user_interrupted":
            checkpoint_ts = _iso_now()
            interrupted_manifest = CheckpointManifest(
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
                incomplete=True,
            )
            write_checkpoint_manifest(repo_root, interrupted_manifest)
            checkpoint_stats = {
                **checkpoint_stats,
                "run_id": run_id,
                "resume_mode": resume_info["mode"],
                "resume_has_checkpoint": resume_info["has_checkpoint"],
                "seeds_completed": seeds_done,
                "seeds_remaining": max(0, len(seed_qids) - seeds_done),
                "stop_reason": last_stop_reason,
            }
            break

        # Persist the final seed boundary before the expensive checkpoint materialization step.
        # If materialization is interrupted, resume can still skip this completed seed.
        if seed_index + 1 == len(seeds) and last_stop_reason == "seed_complete":
            checkpoint_ts = _iso_now()
            seed_boundary_manifest = CheckpointManifest(
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
                incomplete=False,
            )
            print("[graph_stage] Final seed boundary checkpoint start", flush=True)
            write_checkpoint_manifest(repo_root, seed_boundary_manifest)

        checkpoint_ts = _iso_now()
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
            **checkpoint_stats,
            "seed_id": str(seed_summary.get("seed_qid", "")),
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

    final_stats: dict = {}
    if last_stop_reason != "user_interrupted":
        print("[graph_stage] Final materialization start", flush=True)
        final_materialize_t0 = perf_counter()
        final_stats = materialize_final(repo_root, run_id=run_id)
        print(f"[graph_stage] Final materialization done in {perf_counter() - final_materialize_t0:.2f}s", flush=True)
    else:
        print("[graph_stage] Final materialization skipped due to graceful user interruption", flush=True)
    checkpoint_stats.update(final_stats)
    checkpoint_stats["stop_reason"] = last_stop_reason
    checkpoint_stats["total_nodes_discovered"] = int(len(newly_discovered_qids))
    checkpoint_stats["total_nodes_expanded"] = int(len(expanded_qids))
    checkpoint_stats["total_queries"] = int(total_queries_used)
    checkpoint_stats["stage_a_network_queries"] = int(total_queries_used)
    checkpoint_stats["total_queries_before_run"] = int(initial_total_queries_used)
    checkpoint_stats["stage_a_network_queries_this_run"] = int(max(0, total_queries_used - initial_total_queries_used))
    checkpoint_stats["stage_a_neighbor_prefetch_batches_attempted"] = int(stage_neighbor_prefetch_batches_attempted)
    checkpoint_stats["stage_a_neighbor_prefetch_batches_succeeded"] = int(stage_neighbor_prefetch_batches_succeeded)
    checkpoint_stats["stage_a_neighbor_prefetch_candidates_total"] = int(stage_neighbor_prefetch_candidates_total)
    checkpoint_stats["resume_mode"] = resume_info["mode"]
    checkpoint_stats["resume_has_checkpoint"] = resume_info["has_checkpoint"]

    discovered_candidates, resolved_target_ids = _resolve_targets_against_discovered_items(
        repo_root,
        targets=targets,
        class_scope_hints=class_scope_hints,
    )
    unresolved_targets = [t for t in targets if t.get("mention_id") not in resolved_target_ids]
    _write_graph_stage_handoff(repo_root, discovered_candidates, unresolved_targets)

    if seeds_processed_this_run > 0 and not interrupted_before_seed_loop:
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
            incomplete=(last_stop_reason in {"crash_recovery", "user_interrupted"}),
        )
        write_checkpoint_manifest(repo_root, final_manifest)

    checkpoint_stats["completed_seed_count"] = int(completed_seed_count)
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
    notebook_logger.log_phase_finished(
        "stage_a_graph_expansion",
        message="graph expansion stage finished",
        extra={
            "elapsed_seconds": checkpoint_stats["stage_elapsed_seconds"],
            "total_queries": int(checkpoint_stats.get("total_queries", 0)),
            "stop_reason": str(last_stop_reason),
            "phase_contract": phase_contract_payload(contract),
            "phase_outcome": phase_outcome_payload(
                phase="stage_a_graph_expansion",
                work_label="run_graph_expansion_stage",
                status="completed",
                details={
                    "elapsed_seconds": checkpoint_stats["stage_elapsed_seconds"],
                    "total_queries": int(checkpoint_stats.get("total_queries", 0)),
                    "stop_reason": str(last_stop_reason),
                },
            ),
        },
    )
    return GraphExpansionResult(
        discovered_candidates=discovered_candidates,
        resolved_target_ids=resolved_target_ids,
        unresolved_targets=unresolved_targets,
        newly_discovered_qids=newly_discovered_qids,
        expanded_qids=expanded_qids,
        checkpoint_stats=checkpoint_stats,
    )
