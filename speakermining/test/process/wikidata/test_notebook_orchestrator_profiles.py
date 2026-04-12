from __future__ import annotations

import os

from process.candidate_generation.wikidata.notebook_orchestrator import (
    apply_run_profile_environment,
    build_benchmark_run_context,
    build_runtime_evidence_payload_parts,
    resolve_allow_non_operational_summary_overwrite,
    resolve_run_profile,
)


def test_resolve_run_profile_prefers_config_then_env(monkeypatch) -> None:
    monkeypatch.setenv("WIKIDATA_RUN_PROFILE", "smoke")
    assert resolve_run_profile({}) == "smoke"
    assert resolve_run_profile({"run_profile": "cache_only"}) == "cache_only"
    assert resolve_run_profile({"run_profile": "unknown"}) == "smoke"


def test_resolve_run_profile_defaults_operational(monkeypatch) -> None:
    monkeypatch.delenv("WIKIDATA_RUN_PROFILE", raising=False)
    assert resolve_run_profile({}) == "operational"


def test_apply_run_profile_environment_sets_env(monkeypatch) -> None:
    monkeypatch.delenv("WIKIDATA_RUN_PROFILE", raising=False)
    monkeypatch.delenv("WIKIDATA_ALLOW_NON_OPERATIONAL_SUMMARY_OVERWRITE", raising=False)

    resolved = apply_run_profile_environment(
        {
            "run_profile": "smoke",
            "allow_non_operational_summary_overwrite": True,
        }
    )

    assert resolved["run_profile"] == "smoke"
    assert bool(resolved["allow_non_operational_summary_overwrite"]) is True
    assert os.getenv("WIKIDATA_RUN_PROFILE") == "smoke"
    assert os.getenv("WIKIDATA_ALLOW_NON_OPERATIONAL_SUMMARY_OVERWRITE") == "1"


def test_runtime_context_includes_run_profile_flags(monkeypatch) -> None:
    monkeypatch.setenv("WIKIDATA_RUN_PROFILE", "cache_only")
    monkeypatch.setenv("WIKIDATA_ALLOW_NON_OPERATIONAL_SUMMARY_OVERWRITE", "0")

    run_context, stage_summaries = build_runtime_evidence_payload_parts(
        {},
        resume_mode="append",
        stage_a_queries_this_run=0,
        node_integrity_timeout_warnings=0,
        fallback_candidates_count=0,
        reentry_expanded_qids_count=0,
        fallback_class_scoped_search_queries=0,
        fallback_generic_search_queries=0,
        fallback_class_scoped_hits=0,
        fallback_generic_hits=0,
    )

    assert run_context["run_profile"] == "cache_only"
    assert bool(run_context["allow_non_operational_summary_overwrite"]) is False
    assert isinstance(stage_summaries, dict)


def test_benchmark_context_includes_run_profile_flags(monkeypatch) -> None:
    monkeypatch.setenv("WIKIDATA_RUN_PROFILE", "smoke")
    monkeypatch.setenv("WIKIDATA_ALLOW_NON_OPERATIONAL_SUMMARY_OVERWRITE", "1")

    context = build_benchmark_run_context(
        {},
        target_rows_count=1,
        seed_count=2,
        unresolved_targets_count=3,
    )

    assert context["run_profile"] == "smoke"
    assert bool(context["allow_non_operational_summary_overwrite"]) is True


def test_resolve_allow_non_operational_summary_overwrite_prefers_config(monkeypatch) -> None:
    monkeypatch.setenv("WIKIDATA_ALLOW_NON_OPERATIONAL_SUMMARY_OVERWRITE", "0")
    assert resolve_allow_non_operational_summary_overwrite(
        {"allow_non_operational_summary_overwrite": True}
    )
