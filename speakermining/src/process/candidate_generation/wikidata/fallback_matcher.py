from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

import pandas as pd

from .cache import _atomic_write_df
from .cache import begin_request_context, end_request_context
from .common import canonical_qid, effective_core_class_qids, normalize_query_budget, normalize_text, pick_entity_label
from .entity import (
    get_or_fetch_entity,
    get_or_search_entities_by_label,
    get_or_search_entities_by_label_in_class_ranked,
)
from .expansion_engine import is_expandable_target, resolve_direct_or_subclass_core_match_for_entity
from .event_log import write_candidate_matched_event, build_entity_discovered_event, build_expansion_decision_event
from .graceful_shutdown import should_terminate
from .node_store import flush_node_store, get_item, iter_items
from .node_store import upsert_discovered_item
from .phase_contracts import PhaseContract, phase_contract_payload, phase_outcome_payload
from .schemas import build_artifact_paths
from .triple_store import flush_triple_events, seed_neighbor_degrees
from ...notebook_event_log import NOTEBOOK_21_ID, get_or_create_notebook_logger


@dataclass(frozen=True)
class FallbackMatchResult:
    fallback_candidates: list[dict]
    newly_discovered_qids: set[str]
    eligible_for_expansion_qids: set[str]
    ineligible_qids: set[str]
    class_scoped_search_queries: int = 0
    generic_search_queries: int = 0
    class_scoped_hits: int = 0
    generic_hits: int = 0


def merge_stage_candidates(graph_candidates: list[dict], fallback_candidates: list[dict]) -> list[dict]:
    """Merge stage outputs while preserving graph-stage authority.

    Graph-stage rows are always kept. Fallback rows are appended only when they do
    not duplicate an existing (mention_id, candidate_id) pair.
    """
    merged: dict[tuple[str, str], dict] = {}
    for row in graph_candidates or []:
        key = (str(row.get("mention_id", "")), str(row.get("candidate_id", "")))
        if all(key):
            merged[key] = dict(row)
    for row in fallback_candidates or []:
        key = (str(row.get("mention_id", "")), str(row.get("candidate_id", "")))
        if not all(key):
            continue
        merged.setdefault(key, dict(row))
    return [merged[key] for key in sorted(merged)]


def _scope_allows(mention_type: str, class_scope_hints: dict, candidate: dict) -> bool:
    if not class_scope_hints:
        return True
    expected = set(class_scope_hints.get(mention_type, []))
    if not expected:
        return True
    p31_values = set(candidate.get("p31", []))
    return bool(expected & p31_values)


def _load_relevant_qids(repo_root: Path) -> set[str]:
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
    for row in frame.fillna("").to_dict(orient="records"):
        qid = canonical_qid(str(row.get("qid", "") or ""))
        if not qid:
            continue
        if str(row.get("relevant", "")).strip().lower() in {"1", "true", "yes", "y", "on"}:
            out.add(qid)
    return out


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


def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _shutdown_path(repo_root: Path) -> Path:
    return build_artifact_paths(Path(repo_root)).wikidata_dir / ".shutdown"


def _termination_requested(repo_root: Path) -> bool:
    return should_terminate(_shutdown_path(Path(repo_root)))


def _is_termination_runtime_error(exc: RuntimeError) -> bool:
    return "Termination requested" in str(exc)


def _candidate_from_item(item: dict) -> dict | None:
    qid = canonical_qid(item.get("id", ""))
    if not qid:
        return None
    return {
        "qid": qid,
        "label": pick_entity_label(item) or qid,
        "p31": sorted(_claim_qids(item, "P31")),
        "is_class_node": bool(_claim_qids(item, "P279")),
    }


def _index_candidate(label_index: dict[str, list[dict]], candidate: dict) -> None:
    label = normalize_text(candidate.get("label", ""))
    if not label:
        return
    bucket = label_index.setdefault(label, [])
    if all(existing.get("qid", "") != candidate.get("qid", "") for existing in bucket):
        bucket.append(candidate)


def run_fallback_string_matching_stage(
    repo_root: Path,
    *,
    unresolved_targets: list[dict],
    seeds: set[str] | None = None,
    core_class_qids: set[str],
    class_scope_hints: dict,
    config: dict,
) -> FallbackMatchResult:
    stage_t0 = perf_counter()
    notebook_logger = get_or_create_notebook_logger(repo_root, NOTEBOOK_21_ID)
    contract = PhaseContract(
        phase="stage_b_fallback_matching",
        owner="fallback_matcher",
        input_contract="unresolved_targets + class_scope_hints + runtime_config",
        output_contract="fallback_candidates + eligibility_sets + stage_artifacts",
    )
    notebook_logger.append_event(
        event_type="phase_contract_declared",
        phase="stage_b_fallback_matching",
        message="phase contract declared",
        extra={"phase_contract": phase_contract_payload(contract)},
    )
    notebook_logger.log_phase_started("stage_b_fallback_matching", message="fallback string matching started")
    print("[fallback_stage] Starting fallback string matching", flush=True)
    fallback_candidates: list[dict] = []
    newly_discovered_qids: set[str] = set()
    eligible_for_expansion_qids: set[str] = set()
    ineligible_qids: set[str] = set()
    seed_qids = {canonical_qid(qid) for qid in (seeds or set()) if canonical_qid(qid)}
    relevant_qids = _load_relevant_qids(repo_root)
    relevant_qids.update(seed_qids)
    effective_core_classes = effective_core_class_qids(core_class_qids)
    seed_neighbor_degree_map = seed_neighbor_degrees(repo_root, seed_qids, max_degree=2)

    # Deterministic in-memory index over discovered nodes.
    label_index: dict[str, list[dict]] = {}
    index_t0 = perf_counter()
    for item in iter_items(repo_root):
        candidate = _candidate_from_item(item)
        if candidate:
            _index_candidate(label_index, candidate)
    print(
        f"[fallback_stage] Built local label index in {perf_counter() - index_t0:.2f}s",
        flush=True,
    )

    search_cache_max_age_days = int(config.get("cache_max_age_days", 365))
    search_timeout = int(config.get("query_timeout_seconds", 30))
    search_limit = int(config.get("fallback_search_limit", 10))
    scoped_search_limit = int(config.get("fallback_class_scoped_search_limit", search_limit))
    search_languages = config.get("fallback_search_languages", ["de", "en"])
    prefer_class_scoped_search = bool(config.get("fallback_prefer_class_scoped_search", False))
    allow_generic_after_class_scoped = bool(config.get("fallback_allow_generic_search_after_class_scoped", True))
    has_explicit_budget = "network_budget_remaining" in config or "max_queries_per_run" in config
    search_query_budget = normalize_query_budget(
        config.get("network_budget_remaining", config.get("max_queries_per_run", 0))
    )
    query_delay_seconds = float(config.get("query_delay_seconds", 1.0) or 0.0)
    progress_every_calls = int(config.get("network_progress_every", 50) or 0)
    if not isinstance(search_languages, list) or not search_languages:
        search_languages = ["de", "en"]

    allowed_mention_types = {
        "person",
        "organization",
        "episode",
        "season",
        "topic",
        "broadcasting_program",
    }
    raw_enabled_mention_types = config.get("fallback_enabled_mention_types")
    if raw_enabled_mention_types is None:
        raise ValueError(
            "config['fallback_enabled_mention_types'] is required. "
            "Pass the resolved list from notebook Step 2 via config['fallback_enabled_mention_types_resolved']."
        )

    if isinstance(raw_enabled_mention_types, dict):
        normalized_enabled = {
            str(name).strip().lower()
            for name, is_enabled in raw_enabled_mention_types.items()
            if str(name).strip() and bool(is_enabled)
        }
    elif isinstance(raw_enabled_mention_types, (list, tuple, set)):
        normalized_enabled = {
            str(value).strip().lower()
            for value in raw_enabled_mention_types
            if str(value).strip()
        }
    else:
        raise ValueError(
            "config['fallback_enabled_mention_types'] must be a dict or list/tuple/set of mention types."
        )

    unknown_mention_types = normalized_enabled - allowed_mention_types
    if unknown_mention_types:
        raise ValueError(
            "config['fallback_enabled_mention_types'] contains unsupported mention types: "
            f"{sorted(unknown_mention_types)}. Allowed: {sorted(allowed_mention_types)}"
        )

    enabled_mention_types = set(normalized_enabled)
    budget_label = "unlimited"
    if has_explicit_budget:
        budget_label = "unlimited" if search_query_budget == -1 else str(search_query_budget)
    print(
        (
            f"[fallback_stage] config: budget={budget_label} "
            f"languages={search_languages} search_limit={search_limit} "
            f"enabled_mention_types={sorted(enabled_mention_types)}"
        ),
        flush=True,
    )

    searched_labels: set[str] = set()
    searched_scoped_labels: set[tuple[str, str]] = set()
    class_scoped_search_queries = 0
    generic_search_queries = 0
    class_scoped_hits = 0
    generic_hits = 0
    endpoint_budget_exhausted = bool(has_explicit_budget and search_query_budget == 0)
    if endpoint_budget_exhausted:
        print("[fallback_stage] Endpoint search disabled because explicit network budget is 0", flush=True)

    begin_request_context(
        budget_remaining=search_query_budget,
        query_delay_seconds=query_delay_seconds,
        progress_every_calls=progress_every_calls,
        context_label="fallback_stage",
        event_emitter=notebook_logger.append_event,
        event_phase="stage_b_fallback_matching",
    )
    try:
        processed = 0
        heartbeat_last_emit = perf_counter()
        heartbeat_interval_seconds = 60.0
        for target in unresolved_targets:
            if _termination_requested(repo_root):
                break
            now_progress = perf_counter()
            if now_progress - heartbeat_last_emit >= heartbeat_interval_seconds:
                print(
                    (
                        "[fallback_stage] heartbeat: "
                        f"processed_targets={processed} cached_labels={len(label_index)} "
                        f"searched_labels={len(searched_labels)} candidates={len(fallback_candidates)} "
                        f"eligible={len(eligible_for_expansion_qids)}"
                    ),
                    flush=True,
                )
                heartbeat_last_emit = now_progress
            mention_id = str(target.get("mention_id", "") or "")
            mention_type = str(target.get("mention_type", ""))
            mention_type_norm = mention_type.strip().lower()
            mention_label = normalize_text(target.get("mention_label", ""))
            if not mention_id or not mention_type or not mention_label:
                continue
            if mention_type_norm not in enabled_mention_types:
                continue
            processed += 1
            scope_qids = sorted(canonical_qid(qid) for qid in class_scope_hints.get(mention_type_norm, []) if canonical_qid(qid))
            scoped_lookup_key = (mention_label, mention_type_norm)
            did_class_scoped_search = False
            found_class_scoped_results = False

            if (
                not endpoint_budget_exhausted
                and mention_label not in label_index
                and scope_qids
                and prefer_class_scoped_search
                and scoped_lookup_key not in searched_scoped_labels
            ):
                searched_scoped_labels.add(scoped_lookup_key)
                did_class_scoped_search = True
                original_label = str(target.get("mention_label", "") or "")
                for scope_qid in scope_qids:
                    if endpoint_budget_exhausted:
                        break
                    for language in [str(lang).strip().lower() for lang in search_languages if str(lang).strip()]:
                        if _termination_requested(repo_root):
                            endpoint_budget_exhausted = True
                            break
                        try:
                            class_scoped_search_queries += 1
                            search_payload = get_or_search_entities_by_label_in_class_ranked(
                                repo_root,
                                original_label,
                                scope_qid,
                                search_cache_max_age_days,
                                language=language,
                                limit=scoped_search_limit,
                                timeout=search_timeout,
                            )
                        except RuntimeError as exc:
                            if str(exc) == "Network query budget hit":
                                endpoint_budget_exhausted = True
                                break
                            if _is_termination_runtime_error(exc) or _termination_requested(repo_root):
                                endpoint_budget_exhausted = True
                                break
                            raise

                        hits = search_payload.get("search", []) or []
                        class_scoped_hits += int(len(hits))
                        if hits:
                            found_class_scoped_results = True
                        for hit in hits:
                            if _termination_requested(repo_root):
                                endpoint_budget_exhausted = True
                                break
                            qid = canonical_qid(hit.get("id", ""))
                            if not qid:
                                continue
                            try:
                                entity_payload = get_or_fetch_entity(
                                    repo_root,
                                    qid,
                                    search_cache_max_age_days,
                                    timeout=search_timeout,
                                )
                            except RuntimeError as exc:
                                if str(exc) == "Network query budget hit":
                                    endpoint_budget_exhausted = True
                                    break
                                if _is_termination_runtime_error(exc) or _termination_requested(repo_root):
                                    endpoint_budget_exhausted = True
                                    break
                                raise

                            entity_doc = entity_payload.get("entities", {}).get(qid, {})
                            upsert_discovered_item(repo_root, qid, entity_doc, _iso_now())
                            candidate = _candidate_from_item(entity_doc)
                            if candidate:
                                _index_candidate(label_index, candidate)
                                entity_label = pick_entity_label(entity_doc)
                                notebook_logger.append_event(
                                    event_type="entity_discovered",
                                    phase="stage_b_fallback_matching",
                                    message=(
                                        "entity discovered via class-scoped fallback match: "
                                        f"{qid} ({entity_label})"
                                    ),
                                    entity={"qid": qid, "label": entity_label},
                                    extra=build_entity_discovered_event(
                                        qid=qid,
                                        label=entity_label,
                                        source_step="class_scoped_search",
                                        discovery_method="class_scoped_fallback_match",
                                    ).get("payload", {}),
                                )

                        if endpoint_budget_exhausted:
                            break

            # For unresolved labels that are absent locally, perform bounded endpoint search.
            if (
                not endpoint_budget_exhausted
                and mention_label not in label_index
                and mention_label not in searched_labels
                and (
                    not did_class_scoped_search
                    or (allow_generic_after_class_scoped and not found_class_scoped_results)
                )
            ):
                searched_labels.add(mention_label)
                original_label = str(target.get("mention_label", "") or "")
                for language in [str(lang).strip().lower() for lang in search_languages if str(lang).strip()]:
                    if _termination_requested(repo_root):
                        endpoint_budget_exhausted = True
                        break
                    try:
                        generic_search_queries += 1
                        search_payload = get_or_search_entities_by_label(
                            repo_root,
                            original_label,
                            search_cache_max_age_days,
                            language=language,
                            limit=search_limit,
                            timeout=search_timeout,
                        )
                    except RuntimeError as exc:
                        if str(exc) == "Network query budget hit":
                            endpoint_budget_exhausted = True
                            break
                        if _is_termination_runtime_error(exc) or _termination_requested(repo_root):
                            endpoint_budget_exhausted = True
                            break
                        raise

                    generic_hits += int(len(search_payload.get("search", []) or []))
                    for hit in search_payload.get("search", []) or []:
                        if _termination_requested(repo_root):
                            endpoint_budget_exhausted = True
                            break
                        qid = canonical_qid(hit.get("id", ""))
                        if not qid:
                            continue
                        try:
                            entity_payload = get_or_fetch_entity(
                                repo_root,
                                qid,
                                search_cache_max_age_days,
                                timeout=search_timeout,
                            )
                        except RuntimeError as exc:
                            if str(exc) == "Network query budget hit":
                                endpoint_budget_exhausted = True
                                break
                            if _is_termination_runtime_error(exc) or _termination_requested(repo_root):
                                endpoint_budget_exhausted = True
                                break
                            raise

                        entity_doc = entity_payload.get("entities", {}).get(qid, {})
                        upsert_discovered_item(repo_root, qid, entity_doc, _iso_now())
                        candidate = _candidate_from_item(entity_doc)
                        if candidate:
                            _index_candidate(label_index, candidate)
                            
                            # Emit domain event for discovery via fallback matching
                            entity_label = pick_entity_label(entity_doc)
                            notebook_logger.append_event(
                                event_type="entity_discovered",
                                phase="stage_b_fallback_matching",
                                message=f"entity discovered via fallback match: {qid} ({entity_label})",
                                entity={"qid": qid, "label": entity_label},
                                extra=build_entity_discovered_event(
                                    qid=qid,
                                    label=entity_label,
                                    source_step="derived_local",
                                    discovery_method="fallback_match",
                                ).get("payload", {}),
                            )

                    if endpoint_budget_exhausted:
                        break

            for candidate in sorted(label_index.get(mention_label, []), key=lambda row: row.get("qid", "")):
                if _termination_requested(repo_root):
                    endpoint_budget_exhausted = True
                    break
                if not _scope_allows(mention_type, class_scope_hints, candidate):
                    continue
                qid = candidate.get("qid", "")
                fallback_candidates.append(
                    {
                        "mention_id": mention_id,
                        "mention_type": mention_type,
                        "mention_label": str(target.get("mention_label", "") or ""),
                        "candidate_id": qid,
                        "candidate_label": candidate.get("label", qid),
                        "source": "fallback_string",
                        "context": str(target.get("context", "") or ""),
                    }
                )
                write_candidate_matched_event(
                    repo_root,
                    mention_id=mention_id,
                    mention_type=mention_type,
                    mention_label=str(target.get("mention_label", "") or ""),
                    candidate_id=qid,
                    candidate_label=str(candidate.get("label", qid) or qid),
                    source="fallback_string",
                    context=str(target.get("context", "") or ""),
                )
                newly_discovered_qids.add(qid)
                seed_neighbor_degree = seed_neighbor_degree_map.get(qid)
                entity_doc_for_match = get_item(repo_root, qid)
                if not isinstance(entity_doc_for_match, dict):
                    entity_doc_for_match = {}
                direct_or_subclass_core_match = resolve_direct_or_subclass_core_match_for_entity(
                    repo_root,
                    entity_doc=entity_doc_for_match,
                    core_class_qids=effective_core_classes,
                    cache_max_age_days=search_cache_max_age_days,
                    timeout_seconds=search_timeout,
                    discovered_qids=None,
                )
                can_expand = is_expandable_target(
                    qid,
                    seed_qids=seed_qids,
                    relevant_qids=relevant_qids,
                    seed_neighbor_degree=seed_neighbor_degree,
                    direct_or_subclass_core_match=direct_or_subclass_core_match,
                    is_class_node=bool(candidate.get("is_class_node", False)),
                )
                notebook_logger.append_event(
                    event_type="expansion_decision",
                    phase="stage_b_fallback_matching",
                    message=f"fallback expansion decision for {qid}: {'queue_for_expansion' if can_expand else 'skip_expansion'}",
                    entity={"qid": qid, "label": str(candidate.get("label", qid) or qid)},
                    extra=build_expansion_decision_event(
                        qid=qid,
                        label=str(candidate.get("label", qid) or qid),
                        decision="queue_for_expansion" if can_expand else "skip_expansion",
                        decision_reason="fallback_eligible" if can_expand else "fallback_ineligible",
                        eligibility={
                            "has_direct_link_to_seed": bool(seed_neighbor_degree == 1),
                            "seed_neighbor_degree": seed_neighbor_degree,
                            "direct_or_subclass_core_match": bool(direct_or_subclass_core_match),
                            "p31_core_match": bool(set(candidate.get("p31", [])) & effective_core_classes),
                            "is_class_node": bool(candidate.get("is_class_node", False)),
                        },
                    ).get("payload", {}),
                )
                if can_expand:
                    eligible_for_expansion_qids.add(qid)
                else:
                    ineligible_qids.add(qid)
            if _termination_requested(repo_root):
                break
    finally:
        end_request_context()

    # Deduplicate by (mention_id, candidate_id).
    dedup: dict[tuple[str, str], dict] = {}
    for row in fallback_candidates:
        dedup[(row["mention_id"], row["candidate_id"])] = row
    fallback_candidates = [dedup[key] for key in sorted(dedup)]

    paths = build_artifact_paths(Path(repo_root))
    # `fallback_stage_candidates.csv` is handler-owned and derived from
    # candidate_matched events. Trigger incremental handler materialization here
    # so fallback artifacts remain up to date without direct dual-writes.
    from .handlers.orchestrator import run_handlers

    run_handlers(repo_root, materialization_mode="incremental")

    eligible_df = pd.DataFrame({"candidate_id": sorted(eligible_for_expansion_qids)})
    ineligible_df = pd.DataFrame({"candidate_id": sorted(ineligible_qids)})
    _atomic_write_df(paths.fallback_stage_eligible_for_expansion_csv, eligible_df)
    _atomic_write_df(paths.fallback_stage_ineligible_csv, ineligible_df)
    flush_node_store(repo_root)
    flush_triple_events(repo_root)
    elapsed = perf_counter() - stage_t0
    print(
        (
            f"[fallback_stage] Completed in {elapsed:.2f}s "
            f"processed_targets={processed} candidates={len(fallback_candidates)} "
            f"eligible={len(eligible_for_expansion_qids)} "
            f"class_scoped_queries={class_scoped_search_queries} generic_queries={generic_search_queries}"
        ),
        flush=True,
    )
    notebook_logger.log_phase_finished(
        "stage_b_fallback_matching",
        message="fallback string matching finished",
        extra={
            "elapsed_seconds": round(elapsed, 3),
            "processed_targets": int(processed),
            "candidates": int(len(fallback_candidates)),
            "eligible": int(len(eligible_for_expansion_qids)),
            "phase_contract": phase_contract_payload(contract),
            "fallback_mode_counts": {
                "class_scoped_search_queries": int(class_scoped_search_queries),
                "generic_search_queries": int(generic_search_queries),
                "class_scoped_hits": int(class_scoped_hits),
                "generic_hits": int(generic_hits),
            },
            "phase_outcome": phase_outcome_payload(
                phase="stage_b_fallback_matching",
                work_label="run_fallback_string_matching_stage",
                status="completed",
                details={
                    "elapsed_seconds": round(elapsed, 3),
                    "processed_targets": int(processed),
                    "candidates": int(len(fallback_candidates)),
                    "eligible": int(len(eligible_for_expansion_qids)),
                },
            ),
        },
    )

    return FallbackMatchResult(
        fallback_candidates=fallback_candidates,
        newly_discovered_qids=newly_discovered_qids,
        eligible_for_expansion_qids=eligible_for_expansion_qids,
        ineligible_qids=ineligible_qids,
        class_scoped_search_queries=int(class_scoped_search_queries),
        generic_search_queries=int(generic_search_queries),
        class_scoped_hits=int(class_scoped_hits),
        generic_hits=int(generic_hits),
    )


def enqueue_eligible_fallback_qids(
    repo_root: Path,
    *,
    candidate_qids: set[str],
    seeds: set[str],
    core_class_qids: set[str],
    expansion_config,
) -> dict:
    from .expansion_engine import run_seed_expansion
    notebook_logger = get_or_create_notebook_logger(repo_root, NOTEBOOK_21_ID)
    contract = PhaseContract(
        phase="step_9_fallback_reentry",
        owner="fallback_matcher",
        input_contract="eligible_fallback_qids + seeds + core_class_qids + expansion_config",
        output_contract="expanded_qid_count + reentry_summary",
    )
    notebook_logger.append_event(
        event_type="phase_contract_declared",
        phase="step_9_fallback_reentry",
        message="phase contract declared",
        extra={"phase_contract": phase_contract_payload(contract)},
    )
    notebook_logger.log_phase_started(
        "step_9_fallback_reentry",
        message="fallback re-entry expansion started",
    )

    expanded = 0
    ordered = sorted(canonical_qid(qid) for qid in candidate_qids if canonical_qid(qid))
    ordered = [qid for qid in ordered if qid]
    for qid in ordered:
        result = run_seed_expansion(
            repo_root,
            seed={"wikidata_id": qid},
            seed_qids={canonical_qid(s) for s in seeds if canonical_qid(s)},
            core_class_qids={canonical_qid(c) for c in core_class_qids if canonical_qid(c)},
            total_budget_remaining=int(getattr(expansion_config, "total_query_budget", 0) or 0),
            config=expansion_config,
        )
        expanded += len(set(result.get("expanded_qids", set())))

    summary = {
        "eligible_qids": ordered,
        "expanded": expanded,
        "seed_count": len({canonical_qid(s) for s in seeds if canonical_qid(s)}),
    }
    notebook_logger.log_phase_finished(
        "step_9_fallback_reentry",
        message="fallback re-entry expansion finished",
        extra={
            "phase_contract": phase_contract_payload(contract),
            "phase_outcome": phase_outcome_payload(
                phase="step_9_fallback_reentry",
                work_label="enqueue_eligible_fallback_qids",
                status="completed",
                details={
                    "eligible_qids": int(len(ordered)),
                    "expanded": int(expanded),
                    "seed_count": int(summary["seed_count"]),
                },
            ),
        },
    )
    return summary
