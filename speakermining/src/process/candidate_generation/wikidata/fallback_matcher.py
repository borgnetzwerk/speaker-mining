from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

import pandas as pd

from .cache import _atomic_write_df
from .cache import begin_request_context, end_request_context
from .common import canonical_qid, effective_core_class_qids, normalize_query_budget, normalize_text, pick_entity_label
from .entity import get_or_fetch_entity, get_or_search_entities_by_label
from .event_log import write_candidate_matched_event
from .node_store import flush_node_store, iter_items
from .node_store import upsert_discovered_item
from .schemas import build_artifact_paths
from .triple_store import flush_triple_events, has_direct_link_to_any_seed
from ...notebook_event_log import NOTEBOOK_21_ID, get_or_create_notebook_logger


@dataclass(frozen=True)
class FallbackMatchResult:
    fallback_candidates: list[dict]
    newly_discovered_qids: set[str]
    eligible_for_expansion_qids: set[str]
    ineligible_qids: set[str]


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
    notebook_logger.log_phase_started("stage_b_fallback_matching", message="fallback string matching started")
    print("[fallback_stage] Starting fallback string matching", flush=True)
    fallback_candidates: list[dict] = []
    newly_discovered_qids: set[str] = set()
    eligible_for_expansion_qids: set[str] = set()
    ineligible_qids: set[str] = set()
    seed_qids = {canonical_qid(qid) for qid in (seeds or set()) if canonical_qid(qid)}
    effective_core_classes = effective_core_class_qids(core_class_qids)

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
    search_languages = config.get("fallback_search_languages", ["de", "en"])
    has_explicit_budget = "network_budget_remaining" in config or "max_queries_per_run" in config
    search_query_budget = normalize_query_budget(
        config.get("network_budget_remaining", config.get("max_queries_per_run", 0))
    )
    query_delay_seconds = float(config.get("query_delay_seconds", 1.0) or 0.0)
    progress_every_calls = int(config.get("network_progress_every", 50) or 0)
    if not isinstance(search_languages, list) or not search_languages:
        search_languages = ["de", "en"]
    enabled_mention_types = {
        str(value).strip().lower()
        for value in config.get("fallback_enabled_mention_types", ["person"])
        if str(value).strip()
    }
    if not enabled_mention_types:
        enabled_mention_types = {"person"}
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
    endpoint_budget_exhausted = bool(has_explicit_budget and search_query_budget == 0)
    if endpoint_budget_exhausted:
        print("[fallback_stage] Endpoint search disabled because explicit network budget is 0", flush=True)

    from .expansion_engine import is_expandable_target

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

            # For unresolved labels that are absent locally, perform bounded endpoint search.
            if (
                not endpoint_budget_exhausted
                and mention_label not in label_index
                and mention_label not in searched_labels
            ):
                searched_labels.add(mention_label)
                original_label = str(target.get("mention_label", "") or "")
                for language in [str(lang).strip().lower() for lang in search_languages if str(lang).strip()]:
                    try:
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
                        raise

                    for hit in search_payload.get("search", []) or []:
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
                            raise

                        entity_doc = entity_payload.get("entities", {}).get(qid, {})
                        upsert_discovered_item(repo_root, qid, entity_doc, _iso_now())
                        candidate = _candidate_from_item(entity_doc)
                        if candidate:
                            _index_candidate(label_index, candidate)

                    if endpoint_budget_exhausted:
                        break

            for candidate in sorted(label_index.get(mention_label, []), key=lambda row: row.get("qid", "")):
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
                has_direct_link = has_direct_link_to_any_seed(repo_root, qid, seed_qids)
                can_expand = is_expandable_target(
                    qid,
                    seed_qids=seed_qids,
                    has_direct_link_to_seed=has_direct_link,
                    p31_core_match=bool(set(candidate.get("p31", [])) & effective_core_classes),
                    is_class_node=bool(candidate.get("is_class_node", False)),
                )
                if can_expand:
                    eligible_for_expansion_qids.add(qid)
                else:
                    ineligible_qids.add(qid)
    finally:
        end_request_context()

    # Deduplicate by (mention_id, candidate_id).
    dedup: dict[tuple[str, str], dict] = {}
    for row in fallback_candidates:
        dedup[(row["mention_id"], row["candidate_id"])] = row
    fallback_candidates = [dedup[key] for key in sorted(dedup)]

    paths = build_artifact_paths(Path(repo_root))
    candidate_columns = ["mention_id", "mention_type", "mention_label", "candidate_id", "candidate_label", "source", "context"]
    fallback_df = pd.DataFrame(fallback_candidates) if fallback_candidates else pd.DataFrame(columns=candidate_columns)
    for col in candidate_columns:
        if col not in fallback_df.columns:
            fallback_df[col] = ""
    _atomic_write_df(paths.fallback_stage_candidates_csv, fallback_df[candidate_columns])

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
            f"eligible={len(eligible_for_expansion_qids)}"
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
        },
    )

    return FallbackMatchResult(
        fallback_candidates=fallback_candidates,
        newly_discovered_qids=newly_discovered_qids,
        eligible_for_expansion_qids=eligible_for_expansion_qids,
        ineligible_qids=ineligible_qids,
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

    return {
        "eligible_qids": ordered,
        "expanded": expanded,
        "seed_count": len({canonical_qid(s) for s in seeds if canonical_qid(s)}),
    }
