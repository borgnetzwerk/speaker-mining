from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .bootstrap import load_core_classes, load_seed_instances
from .cache import begin_request_context, end_request_context
from .class_resolver import resolve_class_path
from .common import canonical_qid, effective_core_class_qids, normalize_query_budget
from .entity import get_or_build_outlinks, get_or_fetch_entity
from .expansion_engine import ExpansionConfig, is_expandable_target, run_seed_expansion
from .materializer import materialize_final
from .node_store import get_item, iter_items, upsert_discovered_item
from .triple_store import has_direct_link_to_any_seed, iter_unique_triples, record_item_edges
from time import perf_counter


@dataclass(frozen=True)
class NodeIntegrityConfig:
    cache_max_age_days: int = 365
    query_timeout_seconds: int = 30
    query_delay_seconds: float = 1.0
    network_progress_every: int = 50
    discovery_query_budget: int = 0
    per_node_expansion_query_budget: int = 0
    total_expansion_query_budget: int = 0
    inlinks_limit: int = 200
    max_nodes_to_expand: int = 0


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
    materialize_stats: dict


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


def _is_class_node(entity_doc: dict) -> bool:
    return bool(_claim_qids(entity_doc, "P279"))


def _p31_core_match(entity_doc: dict, core_class_qids: set[str]) -> bool:
    return bool(_claim_qids(entity_doc, "P31") & effective_core_class_qids(core_class_qids))


def _p31_core_match_with_subclass_resolution(repo_root: Path, entity_doc: dict, core_class_qids: set[str]) -> bool:
    core_qids = effective_core_class_qids(core_class_qids)
    if not core_qids:
        return False
    if _p31_core_match(entity_doc, core_qids):
        return True

    def _resolver(qid: str) -> dict:
        return get_item(repo_root, qid)

    for class_qid in sorted(_claim_qids(entity_doc, "P31")):
        class_doc = get_item(repo_root, class_qid)
        if not isinstance(class_doc, dict) or not class_doc:
            continue
        resolution = resolve_class_path(class_doc, core_qids, _resolver)
        if bool(resolution.get("subclass_of_core_class", False)):
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


def _record_outlinks_for_node(repo_root: Path, qid: str, entity_payload: dict, cache_max_age_days: int, discovered_at_utc: str) -> None:
    outlinks_payload = get_or_build_outlinks(repo_root, qid, entity_payload, cache_max_age_days)
    record_item_edges(
        repo_root,
        qid,
        outlinks_payload.get("edges", []),
        discovered_at_utc=discovered_at_utc,
        source_query_file="derived_local_outlinks_node_integrity",
    )


def _known_qids(repo_root: Path, seed_qids: set[str], core_class_qids: set[str]) -> set[str]:
    known: set[str] = set(seed_qids) | set(core_class_qids)
    for item in iter_items(repo_root):
        qid = canonical_qid(item.get("id", ""))
        if qid:
            known.add(qid)
    for triple in iter_unique_triples(repo_root):
        subject = canonical_qid(triple.get("subject", ""))
        obj = canonical_qid(triple.get("object", ""))
        if subject:
            known.add(subject)
        if obj:
            known.add(obj)
    return known


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


def run_node_integrity_pass(
    repo_root: Path,
    *,
    config: NodeIntegrityConfig | None = None,
    seed_qids: set[str] | None = None,
    core_class_qids: set[str] | None = None,
) -> NodeIntegrityResult:
    repo_root = Path(repo_root)
    config = config or NodeIntegrityConfig()

    resolved_seed_qids, resolved_core_classes = _resolve_runtime_seed_and_core_classes(
        repo_root,
        seed_qids,
        core_class_qids,
    )
    known_qids = _known_qids(repo_root, resolved_seed_qids, resolved_core_classes)

    discovered_before = {
        canonical_qid(item.get("id", ""))
        for item in iter_items(repo_root)
        if canonical_qid(item.get("id", ""))
    }
    repaired_discovery_qids = 0
    repaired_qids: set[str] = set()
    newly_discovered_qids: set[str] = set()
    checked_qids = 0

    begin_request_context(
        budget_remaining=normalize_query_budget(config.discovery_query_budget),
        query_delay_seconds=float(config.query_delay_seconds),
        progress_every_calls=int(config.network_progress_every),
        context_label="node_integrity:discovery",
    )

    to_check = deque(sorted(known_qids))
    queued: set[str] = set(known_qids)
    checked: set[str] = set()
    discovery_progress_last_emit = perf_counter()
    discovery_progress_interval_seconds = 60.0
    discovery_latest_action = "startup: waiting for first check"
    try:
        while to_check:
            now_progress = perf_counter()
            if now_progress - discovery_progress_last_emit >= discovery_progress_interval_seconds:
                print(
                    (
                        "[node_integrity:discovery] heartbeat: "
                        f"checked={checked_qids} pending={len(to_check)} known={len(known_qids)} "
                        f"repaired={repaired_discovery_qids} newly_discovered={len(newly_discovered_qids)} "
                        f"latest_action={discovery_latest_action}"
                    ),
                    flush=True,
                )
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
                try:
                    payload = get_or_fetch_entity(
                        repo_root,
                        qid,
                        config.cache_max_age_days,
                        timeout=config.query_timeout_seconds,
                    )
                except RuntimeError as exc:
                    if str(exc) == "Network query budget hit":
                        break
                    raise

                entity_doc = payload.get("entities", {}).get(qid, {})
                if isinstance(entity_doc, dict) and entity_doc:
                    discovered_at_utc = _iso_now()
                    upsert_discovered_item(repo_root, qid, entity_doc, discovered_at_utc)
                    _record_outlinks_for_node(
                        repo_root,
                        qid,
                        payload,
                        config.cache_max_age_days,
                        discovered_at_utc,
                    )
                    repaired_discovery_qids += 1
                    repaired_qids.add(qid)
                    if qid not in discovered_before:
                        newly_discovered_qids.add(qid)
                    discovery_latest_action = (
                        f"repaired {qid}: minimal payload restored"
                        if qid in repaired_qids
                        else f"fetched {qid}: payload available"
                    )
                else:
                    discovery_latest_action = f"fetched {qid}: empty payload"

            new_class_qids = 0
            for class_qid in sorted(_claim_qids(entity_doc, "P31") | _claim_qids(entity_doc, "P279")):
                if class_qid not in queued:
                    to_check.append(class_qid)
                    queued.add(class_qid)
                    known_qids.add(class_qid)
                    new_class_qids += 1
            if new_class_qids > 0:
                discovery_latest_action = f"expanded class frontier from {qid}: +{new_class_qids} class qids"
    finally:
        network_queries_discovery = int(end_request_context())

    eligible_unexpanded_qids: list[str] = []
    for item in iter_items(repo_root):
        qid = canonical_qid(item.get("id", ""))
        if not qid:
            continue
        if str(item.get("expanded_at_utc", "") or "").strip():
            continue
        if is_expandable_target(
            qid,
            seed_qids=resolved_seed_qids,
            has_direct_link_to_seed=has_direct_link_to_any_seed(repo_root, qid, resolved_seed_qids),
            p31_core_match=_p31_core_match_with_subclass_resolution(repo_root, item, resolved_core_classes),
            is_class_node=_is_class_node(item),
        ):
            eligible_unexpanded_qids.append(qid)

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
    for idx, qid in enumerate(eligible_unexpanded_qids, start=1):
        now_progress = perf_counter()
        if now_progress - expansion_progress_last_emit >= expansion_progress_interval_seconds:
            print(
                (
                    "[node_integrity:expansion] heartbeat: "
                    f"processed={idx - 1}/{len(eligible_unexpanded_qids)} expanded={len(expanded_qids)} "
                    f"network_queries_expansion={network_queries_expansion} "
                    f"latest_action={expansion_latest_action}"
                ),
                flush=True,
            )
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
        )
        used = int(summary.get("network_queries", 0))
        network_queries_expansion += used
        expanded_now = {canonical_qid(x) for x in summary.get("expanded_qids", set()) if canonical_qid(x)}
        expanded_qids |= expanded_now
        expansion_latest_action = f"expanded seed {qid}: +{len(expanded_now)} qids, network_queries={used}"
        if expansion_budget_remaining > 0:
            expansion_budget_remaining = max(0, expansion_budget_remaining - used)

    run_id = f"node_integrity_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    materialize_stats = materialize_final(repo_root, run_id=run_id)

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
        materialize_stats=materialize_stats,
    )
