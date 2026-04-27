from __future__ import annotations

import os

from .phase_contracts import phase_outcome_payload


_ALLOWED_RUN_PROFILES = {"operational", "smoke", "cache_only"}


def _parse_bool_flag(value: object) -> bool:
    token = str(value or "").strip().lower()
    return token in {"1", "true", "yes", "y", "on"}


def resolve_run_profile(config: dict | None = None) -> str:
    cfg = config or {}
    from_config = str(cfg.get("run_profile", "") or "").strip().lower()
    if from_config in _ALLOWED_RUN_PROFILES:
        return from_config
    from_env = str(os.getenv("WIKIDATA_RUN_PROFILE", "") or "").strip().lower()
    if from_env in _ALLOWED_RUN_PROFILES:
        return from_env
    return "operational"


def resolve_allow_non_operational_summary_overwrite(config: dict | None = None) -> bool:
    cfg = config or {}
    if "allow_non_operational_summary_overwrite" in cfg:
        return bool(cfg.get("allow_non_operational_summary_overwrite", False))
    return _parse_bool_flag(os.getenv("WIKIDATA_ALLOW_NON_OPERATIONAL_SUMMARY_OVERWRITE", "0"))


def apply_run_profile_environment(config: dict) -> dict:
    run_profile = resolve_run_profile(config)
    allow_overwrite = resolve_allow_non_operational_summary_overwrite(config)
    os.environ["WIKIDATA_RUN_PROFILE"] = run_profile
    os.environ["WIKIDATA_ALLOW_NON_OPERATIONAL_SUMMARY_OVERWRITE"] = "1" if allow_overwrite else "0"
    return {
        "run_profile": run_profile,
        "allow_non_operational_summary_overwrite": bool(allow_overwrite),
    }


def build_heartbeat_settings(config: dict) -> dict:
    return {
        "interval_seconds": int(config.get("heartbeat_interval_seconds", 60) or 60),
        "window_size": int(config.get("heartbeat_window_size", 25) or 25),
    }


def resolve_heartbeat_settings(config: dict, heartbeat_settings: dict | None = None) -> dict:
    """Return valid heartbeat settings, reusing existing values when available."""
    if isinstance(heartbeat_settings, dict):
        interval_seconds = int(heartbeat_settings.get("interval_seconds", 0) or 0)
        window_size = int(heartbeat_settings.get("window_size", 0) or 0)
        if interval_seconds > 0 and window_size > 0:
            return {
                "interval_seconds": interval_seconds,
                "window_size": window_size,
            }
    return build_heartbeat_settings(config)


def build_benchmark_settings(config: dict) -> dict:
    return {
        "rounds": int(config.get("handler_benchmark_rounds", 2) or 2),
        "batch_size": int(config.get("handler_benchmark_batch_size", 1000) or 1000),
        "include_full_rebuild": bool(config.get("handler_benchmark_include_full_rebuild", True)),
        "run_enabled": bool(config.get("handler_benchmark_run", True)),
    }


def resolve_stage_a_queries_this_run(checkpoint_stats: dict | None) -> int:
    stats = checkpoint_stats or {}
    return int(
        stats.get(
            "stage_a_network_queries_this_run",
            stats.get("stage_a_network_queries", stats.get("total_queries", 0)),
        )
        or 0
    )


def build_runtime_evidence_inputs(
    *,
    checkpoint_stats: dict | None,
    fallback_result,
    node_integrity_result,
    reentry_summary: dict | None,
    benchmark_summary,
) -> dict:
    reentry = reentry_summary or {}
    reentry_expanded_qids_count = int(reentry.get("expanded", 0) or 0)
    if "expanded_qids" in reentry:
        reentry_expanded_qids_count = int(len(reentry.get("expanded_qids", []) or []))
    return {
        "stage_a_queries_this_run": int(resolve_stage_a_queries_this_run(checkpoint_stats)),
        "fallback_candidates_count": int(len(getattr(fallback_result, "fallback_candidates", []) or [])),
        "node_integrity_timeout_warnings": int(getattr(node_integrity_result, "timeout_warnings", 0) or 0),
        "reentry_expanded_qids_count": int(reentry_expanded_qids_count),
        "fallback_class_scoped_search_queries": int(getattr(fallback_result, "class_scoped_search_queries", 0) or 0),
        "fallback_generic_search_queries": int(getattr(fallback_result, "generic_search_queries", 0) or 0),
        "fallback_class_scoped_hits": int(getattr(fallback_result, "class_scoped_hits", 0) or 0),
        "fallback_generic_hits": int(getattr(fallback_result, "generic_hits", 0) or 0),
        "benchmark_summary_payload": benchmark_summary if isinstance(benchmark_summary, dict) else {},
    }


def normalize_query_budget(max_queries_per_run: int) -> int:
    value = int(max_queries_per_run)
    if value < -1:
        raise ValueError("config['max_queries_per_run'] must be -1, 0, or a positive integer")
    return value


def resolve_budget_after_stage_a(max_queries_per_run: int, stage_a_queries_this_run: int) -> int:
    total_budget = normalize_query_budget(max_queries_per_run)
    used = max(0, int(stage_a_queries_this_run or 0))
    if total_budget == -1:
        return -1
    return max(0, total_budget - used)


def build_node_integrity_budget_plan(max_queries_per_run: int, stage_a_queries_this_run: int) -> dict:
    remaining = resolve_budget_after_stage_a(max_queries_per_run, stage_a_queries_this_run)
    if remaining == -1:
        label = "unlimited"
    else:
        label = str(remaining)
    return {
        "remaining_budget": remaining,
        "label": label,
        "discovery_query_budget": remaining,
        "per_node_expansion_query_budget": remaining,
        "total_expansion_query_budget": remaining,
    }


def build_fallback_budget_plan(max_queries_per_run: int, stage_a_queries_this_run: int) -> dict:
    remaining = resolve_budget_after_stage_a(max_queries_per_run, stage_a_queries_this_run)
    label = "unlimited" if remaining == -1 else str(remaining)
    return {
        "remaining_budget": remaining,
        "label": label,
        "network_budget_remaining": remaining,
        "max_queries_per_run": remaining,
    }


def build_benchmark_run_context(
    config: dict,
    *,
    target_rows_count: int,
    seed_count: int,
    unresolved_targets_count: int,
) -> dict:
    run_profile = resolve_run_profile(config)
    allow_non_operational_summary_overwrite = resolve_allow_non_operational_summary_overwrite(config)
    return {
        "max_queries_per_run": int(config.get("max_queries_per_run", 0) or 0),
        "cache_max_age_days": int(config.get("cache_max_age_days", 0) or 0),
        "run_profile": run_profile,
        "allow_non_operational_summary_overwrite": bool(allow_non_operational_summary_overwrite),
        "fallback_prefer_class_scoped_search": bool(config.get("fallback_prefer_class_scoped_search", False)),
        "fallback_allow_generic_search_after_class_scoped": bool(config.get("fallback_allow_generic_search_after_class_scoped", True)),
        "lineage_resolution_policy": str(
            os.getenv("WIKIDATA_LINEAGE_RESOLUTION_POLICY", "runtime_then_recovered_then_network") or ""
        ).strip()
        or "runtime_then_recovered_then_network",
        "target_rows": int(target_rows_count),
        "seed_count": int(seed_count),
        "unresolved_targets": int(unresolved_targets_count),
    }


def build_runtime_evidence_payload_parts(
    config: dict,
    *,
    resume_mode: str,
    stage_a_queries_this_run: int,
    node_integrity_timeout_warnings: int,
    fallback_candidates_count: int,
    reentry_expanded_qids_count: int,
    fallback_class_scoped_search_queries: int,
    fallback_generic_search_queries: int,
    fallback_class_scoped_hits: int,
    fallback_generic_hits: int,
) -> tuple[dict, dict]:
    run_profile = resolve_run_profile(config)
    allow_non_operational_summary_overwrite = resolve_allow_non_operational_summary_overwrite(config)
    run_context = {
        "resume_mode": str(resume_mode or ""),
        "cache_max_age_days": int(config.get("cache_max_age_days", 0) or 0),
        "max_queries_per_run": int(config.get("max_queries_per_run", 0) or 0),
        "run_profile": run_profile,
        "allow_non_operational_summary_overwrite": bool(allow_non_operational_summary_overwrite),
        "fallback_enabled_mention_types_resolved": list(config.get("fallback_enabled_mention_types_resolved", []) or []),
        "fallback_prefer_class_scoped_search": bool(config.get("fallback_prefer_class_scoped_search", False)),
        "fallback_allow_generic_search_after_class_scoped": bool(config.get("fallback_allow_generic_search_after_class_scoped", True)),
        "lineage_resolution_policy": str(
            os.getenv("WIKIDATA_LINEAGE_RESOLUTION_POLICY", "runtime_then_recovered_then_network") or ""
        ).strip()
        or "runtime_then_recovered_then_network",
    }

    stage_summaries = {
        "stage_a_queries_this_run": int(stage_a_queries_this_run),
        "node_integrity_timeout_warnings": int(node_integrity_timeout_warnings),
        "fallback_candidates": int(fallback_candidates_count),
        "reentry_expanded_qids": int(reentry_expanded_qids_count),
        "fallback_class_scoped_search_queries": int(fallback_class_scoped_search_queries),
        "fallback_generic_search_queries": int(fallback_generic_search_queries),
        "fallback_class_scoped_hits": int(fallback_class_scoped_hits),
        "fallback_generic_hits": int(fallback_generic_hits),
    }
    return run_context, stage_summaries


def build_runtime_evidence_payload(
    config: dict,
    *,
    resume_mode: str,
    stage_a_queries_this_run: int,
    node_integrity_timeout_warnings: int,
    fallback_candidates_count: int,
    reentry_expanded_qids_count: int,
    fallback_class_scoped_search_queries: int,
    fallback_generic_search_queries: int,
    fallback_class_scoped_hits: int,
    fallback_generic_hits: int,
    benchmark_summary_present: bool,
) -> dict:
    run_context, stage_summaries = build_runtime_evidence_payload_parts(
        config,
        resume_mode=resume_mode,
        stage_a_queries_this_run=stage_a_queries_this_run,
        node_integrity_timeout_warnings=node_integrity_timeout_warnings,
        fallback_candidates_count=fallback_candidates_count,
        reentry_expanded_qids_count=reentry_expanded_qids_count,
        fallback_class_scoped_search_queries=fallback_class_scoped_search_queries,
        fallback_generic_search_queries=fallback_generic_search_queries,
        fallback_class_scoped_hits=fallback_class_scoped_hits,
        fallback_generic_hits=fallback_generic_hits,
    )

    node_integrity_status = "completed_with_warnings" if int(node_integrity_timeout_warnings) > 0 else "completed"
    benchmark_status = "available" if bool(benchmark_summary_present) else "not_available"

    phase_outcomes = [
        phase_outcome_payload(
            phase="stage_a_query_budget",
            work_label="stage_a_network_queries",
            status="observed",
            details={"queries_this_run": int(stage_a_queries_this_run)},
        ),
        phase_outcome_payload(
            phase="step_6_5_node_integrity",
            work_label="run_node_integrity_stage",
            status=node_integrity_status,
            details={"timeout_warnings": int(node_integrity_timeout_warnings)},
        ),
        phase_outcome_payload(
            phase="step_8_fallback_matcher",
            work_label="run_fallback_matching_stage",
            status="completed",
            details={
                "fallback_candidates": int(fallback_candidates_count),
                "class_scoped_search_queries": int(fallback_class_scoped_search_queries),
                "generic_search_queries": int(fallback_generic_search_queries),
                "class_scoped_hits": int(fallback_class_scoped_hits),
                "generic_hits": int(fallback_generic_hits),
            },
        ),
        phase_outcome_payload(
            phase="step_9_fallback_reentry",
            work_label="enqueue_eligible_fallback_qids",
            status="completed",
            details={"reentry_expanded_qids": int(reentry_expanded_qids_count)},
        ),
        phase_outcome_payload(
            phase="step_11_handler_benchmark",
            work_label="run_handler_materialization_benchmark",
            status=benchmark_status,
            details={"benchmark_summary_present": bool(benchmark_summary_present)},
        ),
    ]

    return {
        "run_context": run_context,
        "stage_summaries": stage_summaries,
        "phase_outcomes": phase_outcomes,
    }
