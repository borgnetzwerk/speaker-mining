from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import csv
import copy
import os

from .bootstrap import load_core_classes, load_seed_instances
from .cache import begin_request_context, end_request_context
from .class_resolver import RecoveredLineageEvidence, load_recovered_class_hierarchy, resolve_class_path
from .common import (
    DEFAULT_WIKIDATA_FALLBACK_LANGUAGE,
    canonical_qid,
    effective_core_class_qids,
    get_active_wikidata_languages,
    normalize_query_budget,
    pick_entity_label,
)
from .entity import get_or_build_outlinks, get_or_fetch_entities_batch, get_or_fetch_entity
from .expansion_engine import ExpansionConfig, is_expandable_target, run_seed_expansion
from .event_log import build_entity_discovered_event, build_entity_expanded_event, build_expansion_decision_event
from .event_log import build_class_membership_resolved_event
from .event_log import build_eligibility_transition_event
from .graceful_shutdown import should_terminate
from .materializer import materialize_final
from .node_store import flush_node_store, get_item, iter_items, upsert_discovered_item
from .phase_contracts import PhaseContract, phase_contract_payload, phase_outcome_payload
from .triple_store import iter_unique_triples, record_item_edges, seed_neighbor_degrees
from .triple_store import flush_triple_events
from time import perf_counter
from ...notebook_event_log import NOTEBOOK_21_ID, get_or_create_notebook_logger
from .schemas import build_artifact_paths


@dataclass(frozen=True)
class NodeIntegrityConfig:
    cache_max_age_days: int = 365
    query_timeout_seconds: int = 30
    query_delay_seconds: float = 1.0
    http_max_retries: int = 4
    http_backoff_base_seconds: float = 1.0
    network_progress_every: int = 50
    discovery_query_budget: int = 0
    per_node_expansion_query_budget: int = 0
    total_expansion_query_budget: int = 0
    inlinks_limit: int = 200
    max_nodes_to_expand: int = 0
    include_triple_only_qids_in_discovery: bool = False
    discovery_batch_fetch_size: int = 1


@dataclass(frozen=True)
class NodeIntegrityResult:
    known_qids: int
    checked_qids: int
    repaired_discovery_qids: int
    repaired_qids: set[str]
    newly_discovered_qids: set[str]
    eligible_unexpanded_qids: list[str]
    expanded_qids: set[str]
    network_queries_discovery: int
    network_queries_expansion: int
    total_network_queries: int
    timeout_warnings: int
    stop_reason: str
    eligibility_transitions: list[dict]
    materialize_stats: dict


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


def _is_class_node(entity_doc: dict) -> bool:
    return bool(_claim_qids(entity_doc, "P279"))


def _should_expand_class_frontier(qid: str, entity_doc: dict, core_class_qids: set[str]) -> bool:
    """Limit recursive subclass frontier expansion for non-core class nodes.

    Policy:
    - Non-class entities may still contribute their direct class references.
    - Class nodes are only allowed to expand their own subclass frontier when
      they are part of the configured core class set.
    """
    if not isinstance(entity_doc, dict) or not entity_doc:
        return False
    if not _is_class_node(entity_doc):
        return True
    return canonical_qid(qid) in effective_core_class_qids(core_class_qids)


def _p31_core_match(entity_doc: dict, core_class_qids: set[str]) -> bool:
    return bool(_claim_qids(entity_doc, "P31") & effective_core_class_qids(core_class_qids))


def _load_projected_class_resolution(repo_root: Path) -> dict[str, bool]:
    """Load projected class->subclass_of_core_class decisions if available."""
    paths = build_artifact_paths(Path(repo_root))
    path = paths.class_hierarchy_csv
    if not path.exists():
        return {}

    projected: dict[str, bool] = {}
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            class_qid = canonical_qid(str(row.get("class_id", "") or ""))
            if not class_qid:
                continue
            flag = str(row.get("subclass_of_core_class", "") or "").strip().lower()
            projected[class_qid] = flag in {"true", "1", "yes"}
    return projected


def _p31_core_match_with_subclass_resolution(
    repo_root: Path,
    entity_doc: dict,
    core_class_qids: set[str],
    *,
    class_resolution_cache: dict[str, bool] | None = None,
    projected_class_resolution: dict[str, bool] | None = None,
    class_resolution_event_emitter=None,
    recovered_lineage: RecoveredLineageEvidence | None = None,
    resolution_policy: str = "runtime_then_recovered_then_network",
) -> bool:
    core_qids = effective_core_class_qids(core_class_qids)
    if not core_qids:
        return False
    if _p31_core_match(entity_doc, core_qids):
        return True

    class_resolution_cache = class_resolution_cache if class_resolution_cache is not None else {}
    projected_class_resolution = projected_class_resolution if projected_class_resolution is not None else {}

    def _resolver(qid: str) -> dict:
        return get_item(repo_root, qid)

    for class_qid in sorted(_claim_qids(entity_doc, "P31")):
        if class_qid in class_resolution_cache:
            if class_resolution_cache[class_qid]:
                return True
            continue

        if class_qid in projected_class_resolution:
            is_subclass_of_core = bool(projected_class_resolution[class_qid])
            class_resolution_cache[class_qid] = is_subclass_of_core
            if is_subclass_of_core:
                return True
            continue

        class_doc = get_item(repo_root, class_qid)
        if not isinstance(class_doc, dict) or not class_doc:
            class_resolution_cache[class_qid] = False
            continue
        resolution = resolve_class_path(
            class_doc,
            core_qids,
            _resolver,
            on_resolved=(
                (lambda result, class_qid=class_qid: class_resolution_event_emitter(
                    event_type="class_membership_resolved",
                    phase="node_integrity_expansion",
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
                )) if callable(class_resolution_event_emitter) else None
            ),
            recovered_lineage=recovered_lineage,
            resolution_policy=resolution_policy,
        )
        is_subclass_of_core = bool(resolution.get("subclass_of_core_class", False))
        class_resolution_cache[class_qid] = is_subclass_of_core
        if is_subclass_of_core:
            return True
    return False


def _has_minimal_discovery_payload(entity_doc: dict) -> bool:
    if not isinstance(entity_doc, dict) or not entity_doc:
        return False
    if not entity_doc.get("id"):
        return False
    labels = entity_doc.get("labels")
    descriptions = entity_doc.get("descriptions")
    aliases = entity_doc.get("aliases")
    claims = entity_doc.get("claims")
    if not isinstance(labels, dict) or not isinstance(descriptions, dict) or not isinstance(aliases, dict):
        return False
    if not isinstance(claims, dict):
        return False
    if "P31" not in claims or "P279" not in claims:
        return False
    if not isinstance(claims.get("P31", []), list) or not isinstance(claims.get("P279", []), list):
        return False
    return True


def _first_text_value(multilang_block: dict) -> str:
    if not isinstance(multilang_block, dict):
        return ""
    for lang in list(get_active_wikidata_languages()) + [DEFAULT_WIKIDATA_FALLBACK_LANGUAGE]:
        value = multilang_block.get(lang, {})
        text = str(value.get("value", "")).strip() if isinstance(value, dict) else ""
        if text:
            return text
    return ""


def _minimal_payload_preview(entity_doc: dict) -> str:
    if not isinstance(entity_doc, dict):
        return "payload=invalid"
    label = _first_text_value(entity_doc.get("labels", {}))
    p31 = sorted(_claim_qids(entity_doc, "P31"))
    p279 = sorted(_claim_qids(entity_doc, "P279"))
    label_part = f'label="{label}"' if label else "label=<empty>"
    p31_part = f"p31={','.join(p31[:3])}" if p31 else "p31=<none>"
    p279_part = f"p279={','.join(p279[:3])}" if p279 else "p279=<none>"
    return f"{label_part}; {p31_part}; {p279_part}"


def _record_outlinks_for_node(
    repo_root: Path,
    qid: str,
    entity_payload: dict,
    cache_max_age_days: int,
    discovered_at_utc: str,
    *,
    event_emitter=None,
    event_phase: str | None = None,
) -> None:
    outlinks_payload = get_or_build_outlinks(repo_root, qid, entity_payload, cache_max_age_days)
    record_item_edges(
        repo_root,
        qid,
        outlinks_payload.get("edges", []),
        discovered_at_utc=discovered_at_utc,
        source_query_file="derived_local_outlinks_node_integrity",
        event_emitter=event_emitter,
        event_phase=event_phase,
    )


def _known_qids(
    repo_root: Path,
    seed_qids: set[str],
    core_class_qids: set[str],
    *,
    include_triple_qids: bool,
) -> set[str]:
    known: set[str] = set(seed_qids) | set(core_class_qids)
    for item in iter_items(repo_root):
        qid = canonical_qid(item.get("id", ""))
        if qid:
            known.add(qid)
    if include_triple_qids:
        for triple in iter_unique_triples(repo_root):
            subject = canonical_qid(triple.get("subject", ""))
            obj = canonical_qid(triple.get("object", ""))
            if subject:
                known.add(subject)
            if obj:
                known.add(obj)
    return known


def _seed_neighbor_degree_map(repo_root: Path, seed_qids: set[str]) -> dict[str, int]:
    """Return minimal seed-neighborhood degree for nodes within two hops."""
    return seed_neighbor_degrees(repo_root, seed_qids, max_degree=2)


def _resolve_runtime_seed_and_core_classes(repo_root: Path, seed_qids: set[str] | None, core_class_qids: set[str] | None) -> tuple[set[str], set[str]]:
    resolved_seed_qids = {canonical_qid(qid) for qid in (seed_qids or set()) if canonical_qid(qid)}
    if not resolved_seed_qids:
        setup_seeds, _ = load_seed_instances(repo_root)
        resolved_seed_qids = {
            canonical_qid(seed.get("wikidata_id", ""))
            for seed in setup_seeds
            if canonical_qid(seed.get("wikidata_id", ""))
        }

    resolved_core_classes = {canonical_qid(qid) for qid in (core_class_qids or set()) if canonical_qid(qid)}
    if not resolved_core_classes:
        setup_core_classes = load_core_classes(repo_root)
        resolved_core_classes = {
            canonical_qid(row.get("wikidata_id", ""))
            for row in setup_core_classes
            if canonical_qid(row.get("wikidata_id", ""))
        }

    return resolved_seed_qids, effective_core_class_qids(resolved_core_classes)


def _resolve_first_path_to_core(
    entity_doc: dict,
    core_class_qids: set[str],
    get_entity_fn,
    *,
    recovered_lineage: RecoveredLineageEvidence | None = None,
    resolution_policy: str = "runtime_then_recovered_then_network",
) -> str:
    if not isinstance(entity_doc, dict) or not entity_doc:
        return ""

    direct_core = sorted(_claim_qids(entity_doc, "P31") & effective_core_class_qids(core_class_qids))
    if direct_core:
        return direct_core[0]

    for class_qid in sorted(_claim_qids(entity_doc, "P31")):
        class_doc = get_entity_fn(class_qid)
        if not isinstance(class_doc, dict) or not class_doc:
            continue
        resolution = resolve_class_path(
            class_doc,
            effective_core_class_qids(core_class_qids),
            get_entity_fn,
            recovered_lineage=recovered_lineage,
            resolution_policy=resolution_policy,
        )
        if bool(resolution.get("subclass_of_core_class", False)):
            return str(resolution.get("path_to_core_class", "") or "")
    return ""


def _eligibility_decision(
    *,
    qid: str,
    item: dict,
    seed_qids: set[str],
    seed_neighbor_degree_map: dict[str, int],
    core_class_qids: set[str],
    repo_root: Path,
    class_resolution_cache: dict[str, bool],
    projected_class_resolution: dict[str, bool],
    recovered_lineage: RecoveredLineageEvidence | None,
    resolution_policy: str,
) -> dict:
    is_class_node = _is_class_node(item)
    seed_neighbor_degree = seed_neighbor_degree_map.get(qid)
    p31_core_match = _p31_core_match_with_subclass_resolution(
        repo_root,
        item,
        core_class_qids,
        class_resolution_cache=class_resolution_cache,
        projected_class_resolution=projected_class_resolution,
        class_resolution_event_emitter=None,
        recovered_lineage=recovered_lineage,
        resolution_policy=resolution_policy,
    )
    eligible = is_expandable_target(
        qid,
        seed_qids=seed_qids,
        seed_neighbor_degree=seed_neighbor_degree,
        direct_or_subclass_core_match=p31_core_match,
        is_class_node=is_class_node,
    )

    if is_class_node:
        reason = "is_class_node"
    elif qid in seed_qids:
        reason = "seed_qid"
    elif seed_neighbor_degree not in {1, 2}:
        reason = "not_seed_neighbor_degree_1_or_2"
    elif not p31_core_match:
        reason = "no_core_class_match"
    else:
        reason = "seed_neighbor_degree_1_or_2_and_direct_or_subclass_core_match"

    return {
        "is_eligible": bool(eligible),
        "reason": reason,
        "seed_neighbor_degree": seed_neighbor_degree,
    }


def run_node_integrity_pass(
    repo_root: Path,
    *,
    config: NodeIntegrityConfig | None = None,
    seed_qids: set[str] | None = None,
    core_class_qids: set[str] | None = None,
) -> NodeIntegrityResult:
    repo_root = Path(repo_root)
    config = config or NodeIntegrityConfig()
    notebook_logger = get_or_create_notebook_logger(repo_root, NOTEBOOK_21_ID)
    discovery_contract = PhaseContract(
        phase="node_integrity_discovery",
        owner="node_integrity",
        input_contract="known_qids + seed/core class context + discovery budgets",
        output_contract="repaired/newly_discovered qids + discovery telemetry",
    )
    expansion_contract = PhaseContract(
        phase="node_integrity_expansion",
        owner="node_integrity",
        input_contract="eligible_unexpanded_qids + expansion budgets",
        output_contract="expanded_qids + expansion telemetry + materialization stats",
    )
    recovered_lineage, recovered_lineage_source = _load_recovered_lineage_evidence(repo_root)
    resolution_policy = _lineage_resolution_policy()
    print(
        f"[node_integrity] lineage policy={resolution_policy} recovered_source={recovered_lineage_source}",
        flush=True,
    )
    notebook_logger.append_event(
        event_type="lineage_resolution_config",
        phase="node_integrity",
        message="lineage resolution configuration",
        extra={
            "resolution_policy": resolution_policy,
            "recovered_lineage_source": recovered_lineage_source,
            "phase_contracts": {
                "discovery": phase_contract_payload(discovery_contract),
                "expansion": phase_contract_payload(expansion_contract),
            },
        },
    )

    resolved_seed_qids, resolved_core_classes = _resolve_runtime_seed_and_core_classes(
        repo_root,
        seed_qids,
        core_class_qids,
    )
    known_qids = _known_qids(
        repo_root,
        resolved_seed_qids,
        resolved_core_classes,
        include_triple_qids=bool(config.include_triple_only_qids_in_discovery),
    )
    pre_seed_neighbor_degree_map = _seed_neighbor_degree_map(repo_root, resolved_seed_qids)

    discovered_before = {
        canonical_qid(item.get("id", ""))
        for item in iter_items(repo_root)
        if canonical_qid(item.get("id", ""))
    }
    pre_pass_items: dict[str, dict] = {
        canonical_qid(item.get("id", "")): copy.deepcopy(item)
        for item in iter_items(repo_root)
        if canonical_qid(item.get("id", ""))
    }
    repaired_discovery_qids = 0
    repaired_qids: set[str] = set()
    newly_discovered_qids: set[str] = set()
    checked_qids = 0
    timeout_warnings = 0
    stop_reason = "seed_complete"
    interrupt_notice_emitted = False

    def _emit_interrupt_notice(where: str) -> None:
        nonlocal interrupt_notice_emitted
        if interrupt_notice_emitted:
            return
        print(f"[node_integrity] Interrupt detected - now exiting ({where})", flush=True)
        interrupt_notice_emitted = True

    notebook_logger.append_event(
        event_type="phase_contract_declared",
        phase="node_integrity_discovery",
        message="phase contract declared",
        extra={"phase_contract": phase_contract_payload(discovery_contract)},
    )
    notebook_logger.log_phase_started("node_integrity_discovery", message="node integrity discovery started")
    begin_request_context(
        budget_remaining=normalize_query_budget(config.discovery_query_budget),
        query_delay_seconds=float(config.query_delay_seconds),
        http_max_retries=int(config.http_max_retries),
        http_backoff_base_seconds=float(config.http_backoff_base_seconds),
        progress_every_calls=int(config.network_progress_every),
        context_label="node_integrity:discovery",
        event_emitter=notebook_logger.append_event,
        event_phase="node_integrity_discovery",
    )

    to_check = deque(sorted(known_qids))
    queued: set[str] = set(known_qids)
    checked: set[str] = set()
    discovery_progress_last_emit = perf_counter()
    discovery_progress_interval_seconds = 60.0
    discovery_latest_action = "startup: waiting for first check"
    try:
        def _enqueue_class_frontier_from_entity(source_qid: str, source_doc: dict) -> int:
            new_class_qids = 0
            if _should_expand_class_frontier(source_qid, source_doc, resolved_core_classes):
                for class_qid in sorted(_claim_qids(source_doc, "P31") | _claim_qids(source_doc, "P279")):
                    if class_qid not in queued:
                        to_check.append(class_qid)
                        queued.add(class_qid)
                        known_qids.add(class_qid)
                        new_class_qids += 1
            return new_class_qids

        while to_check:
            if _termination_requested(repo_root):
                stop_reason = "user_interrupted"
                _emit_interrupt_notice("discovery")
                break
            now_progress = perf_counter()
            if now_progress - discovery_progress_last_emit >= discovery_progress_interval_seconds:
                print(
                    (
                        "[node_integrity:discovery] heartbeat: "
                        f"checked={checked_qids} pending={len(to_check)} known={len(known_qids)} "
                        f"repaired={repaired_discovery_qids} newly_discovered={len(newly_discovered_qids)}"
                    ),
                    flush=True,
                )
                print(f"[node_integrity:discovery] example: {discovery_latest_action}", flush=True)
                discovery_progress_last_emit = now_progress
            qid = canonical_qid(to_check.popleft())
            if not qid or qid in checked:
                continue
            checked.add(qid)
            checked_qids += 1

            current = get_item(repo_root, qid)
            needs_refresh = not _has_minimal_discovery_payload(current)
            entity_doc = current if isinstance(current, dict) else {}
            discovery_latest_action = f"checked {qid}: refresh={'yes' if needs_refresh else 'no'}"

            if needs_refresh:
                batch_size = max(1, int(config.discovery_batch_fetch_size or 1))
                refresh_qids: list[str] = [qid]
                while len(refresh_qids) < batch_size and to_check:
                    candidate_qid = canonical_qid(to_check[0])
                    if not candidate_qid or candidate_qid in checked:
                        to_check.popleft()
                        continue
                    candidate_item = get_item(repo_root, candidate_qid)
                    candidate_needs_refresh = not _has_minimal_discovery_payload(candidate_item)
                    if not candidate_needs_refresh:
                        break
                    refresh_qids.append(candidate_qid)
                    checked.add(candidate_qid)
                    checked_qids += 1
                    to_check.popleft()

                try:
                    if len(refresh_qids) == 1:
                        single_qid = refresh_qids[0]
                        payloads_by_qid = {
                            single_qid: get_or_fetch_entity(
                                repo_root,
                                single_qid,
                                config.cache_max_age_days,
                                timeout=config.query_timeout_seconds,
                            )
                        }
                    else:
                        payloads_by_qid = get_or_fetch_entities_batch(
                            repo_root,
                            refresh_qids,
                            config.cache_max_age_days,
                            timeout=config.query_timeout_seconds,
                        )
                except KeyboardInterrupt:
                    stop_reason = "user_interrupted"
                    _emit_interrupt_notice("discovery")
                    discovery_latest_action = f"user interruption requested while refreshing {qid}"
                    notebook_logger.append_event(
                        event_type="user_interrupted",
                        phase="node_integrity_discovery",
                        message="user interruption requested during node integrity discovery refresh",
                        entity={"qid": qid},
                    )
                    break
                except TimeoutError as exc:
                    timeout_warnings += 1
                    discovery_latest_action = f"timeout while refreshing batch starting at {qid}: {exc}"
                    print(f"[node_integrity:discovery] warning: {discovery_latest_action}", flush=True)
                    notebook_logger.append_event(
                        event_type="timeout_warning",
                        phase="node_integrity_discovery",
                        message="node integrity refresh timed out; continuing with next qid",
                        entity={"qid": qid, "batch_size": len(refresh_qids)},
                        result={"status": "timeout", "error": str(exc)},
                    )
                    continue
                except RuntimeError as exc:
                    if str(exc) == "Network query budget hit":
                        break
                    if _is_termination_runtime_error(exc) or _termination_requested(repo_root):
                        stop_reason = "user_interrupted"
                        break
                    raise
                if stop_reason == "user_interrupted":
                    break

                for refresh_qid in refresh_qids:
                    refresh_payload = payloads_by_qid.get(refresh_qid, {})
                    refresh_doc = refresh_payload.get("entities", {}).get(refresh_qid, {})
                    if isinstance(refresh_doc, dict) and refresh_doc:
                        discovered_at_utc = _iso_now()
                        upsert_discovered_item(repo_root, refresh_qid, refresh_doc, discovered_at_utc)
                        _record_outlinks_for_node(
                            repo_root,
                            refresh_qid,
                            refresh_payload,
                            config.cache_max_age_days,
                            discovered_at_utc,
                            event_emitter=notebook_logger.append_event,
                            event_phase="node_integrity_discovery",
                        )
                        repaired_discovery_qids += 1
                        repaired_qids.add(refresh_qid)
                        if refresh_qid not in discovered_before:
                            newly_discovered_qids.add(refresh_qid)
                        payload_preview = _minimal_payload_preview(refresh_doc)
                        discovery_latest_action = f"minimal payload restored for {refresh_qid} -> {payload_preview}"

                        entity_label = pick_entity_label(refresh_doc)
                        notebook_logger.append_event(
                            event_type="entity_discovered",
                            phase="node_integrity_discovery",
                            message=f"entity discovered during node integrity: {refresh_qid} ({entity_label})",
                            entity={"qid": refresh_qid, "label": entity_label},
                            extra=build_entity_discovered_event(
                                qid=refresh_qid,
                                label=entity_label,
                                source_step="entity_fetch",
                                discovery_method="node_integrity_repair",
                            ).get("payload", {}),
                        )
                    else:
                        discovery_latest_action = f"fetched {refresh_qid}: empty payload"

                    new_class_qids = _enqueue_class_frontier_from_entity(refresh_qid, refresh_doc if isinstance(refresh_doc, dict) else {})
                    if new_class_qids > 0:
                        discovery_latest_action = f"expanded class frontier from {refresh_qid}: +{new_class_qids} class qids"
                    elif _is_class_node(refresh_doc if isinstance(refresh_doc, dict) else {}):
                        discovery_latest_action = f"class frontier limited for {refresh_qid}: non-core class node"
                continue

            new_class_qids = _enqueue_class_frontier_from_entity(qid, entity_doc)
            if new_class_qids > 0:
                discovery_latest_action = f"expanded class frontier from {qid}: +{new_class_qids} class qids"
            elif _is_class_node(entity_doc):
                discovery_latest_action = f"class frontier limited for {qid}: non-core class node"
    except KeyboardInterrupt:
        stop_reason = "user_interrupted"
        _emit_interrupt_notice("discovery")
        notebook_logger.append_event(
            event_type="user_interrupted",
            phase="node_integrity_discovery",
            message="user interruption requested during node integrity discovery",
        )
    finally:
        network_queries_discovery = int(end_request_context())
        notebook_logger.log_phase_finished(
            "node_integrity_discovery",
            message="node integrity discovery finished",
            extra={
                "checked_qids": int(checked_qids),
                "repaired_discovery_qids": int(repaired_discovery_qids),
                "network_queries": int(network_queries_discovery),
                "phase_contract": phase_contract_payload(discovery_contract),
                "phase_outcome": phase_outcome_payload(
                    phase="node_integrity_discovery",
                    work_label="run_node_integrity_discovery",
                    status="completed",
                    details={
                        "checked_qids": int(checked_qids),
                        "repaired_discovery_qids": int(repaired_discovery_qids),
                        "network_queries": int(network_queries_discovery),
                    },
                ),
            },
        )

    projected_class_resolution = _load_projected_class_resolution(repo_root)

    pre_class_resolution_cache: dict[str, bool] = {}
    pre_pass_decisions: dict[str, dict] = {}
    for qid, item in sorted(pre_pass_items.items()):
        pre_pass_decisions[qid] = _eligibility_decision(
            qid=qid,
            item=item,
            seed_qids=resolved_seed_qids,
            seed_neighbor_degree_map=pre_seed_neighbor_degree_map,
            core_class_qids=resolved_core_classes,
            repo_root=repo_root,
            class_resolution_cache=pre_class_resolution_cache,
            projected_class_resolution=projected_class_resolution,
            recovered_lineage=recovered_lineage,
            resolution_policy=resolution_policy,
        )

    seed_neighbor_degree_map = _seed_neighbor_degree_map(repo_root, resolved_seed_qids)
    class_resolution_cache: dict[str, bool] = {}

    post_pass_decisions: dict[str, dict] = {}
    for item in iter_items(repo_root):
        qid = canonical_qid(item.get("id", ""))
        if not qid:
            continue
        post_pass_decisions[qid] = _eligibility_decision(
            qid=qid,
            item=item,
            seed_qids=resolved_seed_qids,
            seed_neighbor_degree_map=seed_neighbor_degree_map,
            core_class_qids=resolved_core_classes,
            repo_root=repo_root,
            class_resolution_cache=class_resolution_cache,
            projected_class_resolution=projected_class_resolution,
            recovered_lineage=recovered_lineage,
            resolution_policy=resolution_policy,
        )

    eligible_unexpanded_qids: list[str] = []
    for item in iter_items(repo_root):
        qid = canonical_qid(item.get("id", ""))
        if not qid:
            continue
        if str(item.get("expanded_at_utc", "") or "").strip():
            continue
        p31_core_match = _p31_core_match_with_subclass_resolution(
            repo_root,
            item,
            resolved_core_classes,
            class_resolution_cache=class_resolution_cache,
            projected_class_resolution=projected_class_resolution,
            class_resolution_event_emitter=notebook_logger.append_event,
            recovered_lineage=recovered_lineage,
            resolution_policy=resolution_policy,
        )
        if is_expandable_target(
            qid,
            seed_qids=resolved_seed_qids,
            seed_neighbor_degree=seed_neighbor_degree_map.get(qid),
            direct_or_subclass_core_match=p31_core_match,
            is_class_node=_is_class_node(item),
        ):
            eligible_unexpanded_qids.append(qid)

    def _get_entity_for_path(entity_qid: str) -> dict:
        return get_item(repo_root, entity_qid)

    eligibility_transitions: list[dict] = []
    for qid in sorted(set(pre_pass_decisions.keys()) | set(post_pass_decisions.keys())):
        previous = pre_pass_decisions.get(qid, {"is_eligible": False, "reason": "unknown"})
        current = post_pass_decisions.get(qid, {"is_eligible": False, "reason": "unknown"})
        if bool(previous.get("is_eligible", False)) or not bool(current.get("is_eligible", False)):
            continue

        item_now = get_item(repo_root, qid)
        path_to_core_class = _resolve_first_path_to_core(
            item_now,
            resolved_core_classes,
            _get_entity_for_path,
            recovered_lineage=recovered_lineage,
            resolution_policy=resolution_policy,
        )
        transition = {
            "qid": qid,
            "previous_eligible": bool(previous.get("is_eligible", False)),
            "current_eligible": bool(current.get("is_eligible", False)),
            "previous_reason": str(previous.get("reason", "") or ""),
            "current_reason": str(current.get("reason", "") or ""),
            "path_to_core_class": path_to_core_class,
            "timestamp_utc": _iso_now(),
        }
        eligibility_transitions.append(transition)

        notebook_logger.append_event(
            event_type="eligibility_transition",
            phase="node_integrity_expansion",
            message=f"eligibility transition {qid}: {transition['previous_reason']} -> {transition['current_reason']}",
            entity={"qid": qid, "label": pick_entity_label(item_now) or qid},
            extra=build_eligibility_transition_event(
                entity_qid=qid,
                previous_eligible=transition["previous_eligible"],
                current_eligible=transition["current_eligible"],
                previous_reason=transition["previous_reason"],
                current_reason=transition["current_reason"],
                path_to_core_class=transition["path_to_core_class"],
            ).get("payload", {}),
        )

    eligible_unexpanded_qids = sorted(set(eligible_unexpanded_qids))
    if int(config.max_nodes_to_expand or 0) > 0:
        eligible_unexpanded_qids = eligible_unexpanded_qids[: int(config.max_nodes_to_expand)]

    expanded_qids: set[str] = set()
    network_queries_expansion = 0
    expansion_budget_remaining = normalize_query_budget(config.total_expansion_query_budget)
    per_node_budget = normalize_query_budget(config.per_node_expansion_query_budget)

    per_node_expansion_config = ExpansionConfig(
        max_depth=0,
        max_nodes=1,
        total_query_budget=per_node_budget,
        per_seed_query_budget=per_node_budget,
        query_timeout_seconds=int(config.query_timeout_seconds),
        query_delay_seconds=float(config.query_delay_seconds),
        inlinks_limit=int(config.inlinks_limit),
        cache_max_age_days=int(config.cache_max_age_days),
        max_neighbors_per_node=0,
        network_progress_every=int(config.network_progress_every),
    )

    expansion_progress_last_emit = perf_counter()
    expansion_progress_interval_seconds = 60.0
    expansion_latest_action = "startup: waiting for first expansion"
    notebook_logger.append_event(
        event_type="phase_contract_declared",
        phase="node_integrity_expansion",
        message="phase contract declared",
        extra={"phase_contract": phase_contract_payload(expansion_contract)},
    )
    notebook_logger.log_phase_started("node_integrity_expansion", message="node integrity expansion started")
    expansion_flush_every = 100
    try:
        for idx, qid in enumerate(eligible_unexpanded_qids, start=1):
            if _termination_requested(repo_root):
                stop_reason = "user_interrupted"
                _emit_interrupt_notice("expansion")
                break
            now_progress = perf_counter()
            if now_progress - expansion_progress_last_emit >= expansion_progress_interval_seconds:
                print(
                    (
                        "[node_integrity:expansion] heartbeat: "
                        f"processed={idx - 1}/{len(eligible_unexpanded_qids)} expanded={len(expanded_qids)} "
                        f"network_queries_expansion={network_queries_expansion}"
                    ),
                    flush=True,
                )
                print(f"[node_integrity:expansion] example: {expansion_latest_action}", flush=True)
                expansion_progress_last_emit = now_progress
            if expansion_budget_remaining == 0:
                break
            summary = run_seed_expansion(
                repo_root,
                seed={"wikidata_id": qid},
                seed_qids=resolved_seed_qids,
                core_class_qids=resolved_core_classes,
                total_budget_remaining=expansion_budget_remaining,
                config=per_node_expansion_config,
                resume_inlinks_cursor=None,
                flush_persistence=False,
                event_emitter=notebook_logger.append_event,
                event_phase="node_integrity_expansion",
            )
            
            if str(summary.get("stop_reason", "")) == "user_interrupted":
                stop_reason = "user_interrupted"
                _emit_interrupt_notice("expansion")
                break
            used = int(summary.get("network_queries", 0))
            network_queries_expansion += used
            expanded_now = {canonical_qid(x) for x in summary.get("expanded_qids", set()) if canonical_qid(x)}
            expanded_qids |= expanded_now
            expansion_latest_action = f"expanded seed {qid}: +{len(expanded_now)} qids, network_queries={used}"
            if expansion_budget_remaining > 0:
                expansion_budget_remaining = max(0, expansion_budget_remaining - used)

            if idx % expansion_flush_every == 0:
                flush_node_store(repo_root)
                flush_triple_events(repo_root)
    except KeyboardInterrupt:
        stop_reason = "user_interrupted"
        _emit_interrupt_notice("expansion")
        notebook_logger.append_event(
            event_type="user_interrupted",
            phase="node_integrity_expansion",
            message="user interruption requested during node integrity expansion",
        )
    finally:
        flush_node_store(repo_root)
        flush_triple_events(repo_root)

    run_id = f"node_integrity_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    materialize_stats = {"skipped_due_to_user_interrupted": True}
    if stop_reason != "user_interrupted":
        try:
            materialize_stats = materialize_final(repo_root, run_id=run_id)
        except KeyboardInterrupt:
            stop_reason = "user_interrupted"
            _emit_interrupt_notice("final_materialization")
            notebook_logger.append_event(
                event_type="user_interrupted",
                phase="node_integrity_expansion",
                message="user interruption requested during final materialization",
            )
    notebook_logger.log_phase_finished(
        "node_integrity_expansion",
        message="node integrity expansion finished",
        extra={
            "expanded_qids": int(len(expanded_qids)),
            "network_queries": int(network_queries_expansion),
            "timeout_warnings": int(timeout_warnings),
            "stop_reason": stop_reason,
            "phase_contract": phase_contract_payload(expansion_contract),
            "phase_outcome": phase_outcome_payload(
                phase="node_integrity_expansion",
                work_label="run_node_integrity_expansion",
                status="completed" if stop_reason != "user_interrupted" else "interrupted",
                details={
                    "expanded_qids": int(len(expanded_qids)),
                    "network_queries": int(network_queries_expansion),
                    "timeout_warnings": int(timeout_warnings),
                    "stop_reason": str(stop_reason),
                },
            ),
        },
    )

    return NodeIntegrityResult(
        known_qids=int(len(known_qids)),
        checked_qids=int(checked_qids),
        repaired_discovery_qids=int(repaired_discovery_qids),
        repaired_qids=set(sorted(repaired_qids)),
        newly_discovered_qids=set(sorted(newly_discovered_qids)),
        eligible_unexpanded_qids=eligible_unexpanded_qids,
        expanded_qids=set(sorted(expanded_qids)),
        network_queries_discovery=int(network_queries_discovery),
        network_queries_expansion=int(network_queries_expansion),
        total_network_queries=int(network_queries_discovery + network_queries_expansion),
        timeout_warnings=int(timeout_warnings),
        stop_reason=stop_reason,
        eligibility_transitions=eligibility_transitions,
        materialize_stats=materialize_stats,
    )
