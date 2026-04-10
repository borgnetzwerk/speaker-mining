from __future__ import annotations

# pyright: reportMissingImports=false

from pathlib import Path

import pytest

from process.candidate_generation.wikidata.event_log import _chunks_dir, _iter_jsonl_events
from process.candidate_generation.wikidata.fallback_matcher import merge_stage_candidates, run_fallback_string_matching_stage
from process.candidate_generation.wikidata.node_store import upsert_discovered_item
from process.candidate_generation.wikidata.triple_store import record_item_edges


def test_fallback_matches_unresolved_with_scope(tmp_path: Path) -> None:
    # Create one discovered person-like entity with German label "Markus Lanz".
    entity_doc = {
        "id": "Q1499182",
        "labels": {"de": {"value": "Markus Lanz"}},
        "descriptions": {},
        "aliases": {},
        "claims": {
            "P31": [
                {
                    "mainsnak": {
                        "datavalue": {
                            "value": {"entity-type": "item", "id": "Q215627"}
                        }
                    }
                }
            ]
        },
    }
    upsert_discovered_item(tmp_path, "Q1499182", entity_doc, "2026-03-31T12:00:00Z")

    unresolved = [
        {
            "mention_id": "m1",
            "mention_type": "person",
            "mention_label": "Markus Lanz",
            "context": "test",
        }
    ]
    class_scope_hints = {"person": ["Q215627"]}

    result = run_fallback_string_matching_stage(
        tmp_path,
        unresolved_targets=unresolved,
        core_class_qids={"Q215627"},
        class_scope_hints=class_scope_hints,
        config={"fallback_enabled_mention_types": ["person"]},
    )

    assert len(result.fallback_candidates) == 1
    assert result.fallback_candidates[0]["mention_id"] == "m1"
    assert result.fallback_candidates[0]["candidate_id"] == "Q1499182"


def test_fallback_marks_seed_linked_candidate_as_eligible(tmp_path: Path) -> None:
    entity_doc = {
        "id": "Q1499182",
        "labels": {"de": {"value": "Markus Lanz"}},
        "descriptions": {},
        "aliases": {},
        "claims": {
            "P31": [
                {
                    "mainsnak": {
                        "datavalue": {
                            "value": {"entity-type": "item", "id": "Q215627"}
                        }
                    }
                }
            ]
        },
    }
    upsert_discovered_item(tmp_path, "Q1499182", entity_doc, "2026-03-31T12:00:00Z")

    # Create an item-to-item direct link between candidate and seed.
    record_item_edges(
        tmp_path,
        "Q1499182",
        [{"pid": "P463", "to_qid": "Q100"}],
        discovered_at_utc="2026-03-31T12:01:00Z",
        source_query_file="test",
    )

    unresolved = [
        {
            "mention_id": "m1",
            "mention_type": "person",
            "mention_label": "Markus Lanz",
            "context": "test",
        }
    ]
    class_scope_hints = {"person": ["Q215627"]}

    result = run_fallback_string_matching_stage(
        tmp_path,
        unresolved_targets=unresolved,
        seeds={"Q100"},
        core_class_qids={"Q215627"},
        class_scope_hints=class_scope_hints,
        config={"fallback_enabled_mention_types": ["person"]},
    )

    assert "Q1499182" in result.eligible_for_expansion_qids


def test_fallback_marks_second_degree_seed_neighbor_as_eligible(tmp_path: Path) -> None:
    entity_doc = {
        "id": "Q1499182",
        "labels": {"de": {"value": "Markus Lanz"}},
        "descriptions": {},
        "aliases": {},
        "claims": {
            "P31": [
                {
                    "mainsnak": {
                        "datavalue": {
                            "value": {"entity-type": "item", "id": "Q215627"}
                        }
                    }
                }
            ]
        },
    }
    upsert_discovered_item(tmp_path, "Q1499182", entity_doc, "2026-03-31T12:00:00Z")

    # Build a two-hop path candidate -> intermediate -> seed.
    record_item_edges(
        tmp_path,
        "Q1499182",
        [{"pid": "P463", "to_qid": "Q900"}],
        discovered_at_utc="2026-03-31T12:01:00Z",
        source_query_file="test",
    )
    record_item_edges(
        tmp_path,
        "Q900",
        [{"pid": "P463", "to_qid": "Q100"}],
        discovered_at_utc="2026-03-31T12:01:01Z",
        source_query_file="test",
    )

    unresolved = [
        {
            "mention_id": "m1",
            "mention_type": "person",
            "mention_label": "Markus Lanz",
            "context": "test",
        }
    ]
    class_scope_hints = {"person": ["Q215627"]}

    result = run_fallback_string_matching_stage(
        tmp_path,
        unresolved_targets=unresolved,
        seeds={"Q100"},
        core_class_qids={"Q215627"},
        class_scope_hints=class_scope_hints,
        config={"fallback_enabled_mention_types": ["person"]},
    )

    assert "Q1499182" in result.eligible_for_expansion_qids


def test_fallback_discovers_candidates_via_endpoint_search(tmp_path: Path, monkeypatch) -> None:
    def _fake_search(*args, **kwargs):
        _ = (args, kwargs)
        return {"search": [{"id": "Q1499182"}]}

    def _fake_fetch(*args, **kwargs):
        _ = (args, kwargs)
        return {
            "entities": {
                "Q1499182": {
                    "id": "Q1499182",
                    "labels": {"de": {"value": "Markus Lanz"}},
                    "descriptions": {},
                    "aliases": {},
                    "claims": {
                        "P31": [
                            {
                                "mainsnak": {
                                    "datavalue": {
                                        "value": {"entity-type": "item", "id": "Q215627"}
                                    }
                                }
                            }
                        ]
                    },
                }
            }
        }

    monkeypatch.setattr(
        "process.candidate_generation.wikidata.fallback_matcher.get_or_search_entities_by_label",
        _fake_search,
    )
    monkeypatch.setattr(
        "process.candidate_generation.wikidata.fallback_matcher.get_or_fetch_entity",
        _fake_fetch,
    )

    unresolved = [
        {
            "mention_id": "m1",
            "mention_type": "person",
            "mention_label": "Markus Lanz",
            "context": "test",
        }
    ]
    class_scope_hints = {"person": ["Q215627"]}

    result = run_fallback_string_matching_stage(
        tmp_path,
        unresolved_targets=unresolved,
        seeds={"Q100"},
        core_class_qids={"Q215627"},
        class_scope_hints=class_scope_hints,
        config={
            "fallback_search_limit": 5,
            "fallback_search_languages": ["de"],
            "fallback_enabled_mention_types": ["person"],
        },
    )

    assert len(result.fallback_candidates) == 1
    assert result.fallback_candidates[0]["candidate_id"] == "Q1499182"


def test_fallback_prefers_class_scoped_search_when_available(tmp_path: Path, monkeypatch) -> None:
    calls = {"scoped": 0, "generic": 0}

    def _fake_scoped_search(*args, **kwargs):
        _ = (args, kwargs)
        calls["scoped"] += 1
        return {"search": [{"id": "Q1499182"}]}

    def _fake_generic_search(*args, **kwargs):
        _ = (args, kwargs)
        calls["generic"] += 1
        return {"search": []}

    def _fake_fetch(*args, **kwargs):
        _ = (args, kwargs)
        return {
            "entities": {
                "Q1499182": {
                    "id": "Q1499182",
                    "labels": {"de": {"value": "Markus Lanz"}},
                    "descriptions": {},
                    "aliases": {},
                    "claims": {
                        "P31": [
                            {
                                "mainsnak": {
                                    "datavalue": {
                                        "value": {"entity-type": "item", "id": "Q215627"}
                                    }
                                }
                            }
                        ]
                    },
                }
            }
        }

    monkeypatch.setattr(
        "process.candidate_generation.wikidata.fallback_matcher.get_or_search_entities_by_label_in_class_ranked",
        _fake_scoped_search,
    )
    monkeypatch.setattr(
        "process.candidate_generation.wikidata.fallback_matcher.get_or_search_entities_by_label",
        _fake_generic_search,
    )
    monkeypatch.setattr(
        "process.candidate_generation.wikidata.fallback_matcher.get_or_fetch_entity",
        _fake_fetch,
    )

    unresolved = [
        {
            "mention_id": "m1",
            "mention_type": "person",
            "mention_label": "Markus Lanz",
            "context": "test",
        }
    ]
    class_scope_hints = {"person": ["Q215627"]}

    result = run_fallback_string_matching_stage(
        tmp_path,
        unresolved_targets=unresolved,
        seeds={"Q100"},
        core_class_qids={"Q215627"},
        class_scope_hints=class_scope_hints,
        config={
            "fallback_enabled_mention_types": ["person"],
            "fallback_search_languages": ["de"],
            "fallback_prefer_class_scoped_search": True,
            "fallback_allow_generic_search_after_class_scoped": False,
        },
    )

    assert calls["scoped"] >= 1
    assert calls["generic"] == 0
    assert len(result.fallback_candidates) == 1
    assert int(result.class_scoped_search_queries) >= 1
    assert int(result.generic_search_queries) == 0
    assert int(result.class_scoped_hits) >= 1
    assert int(result.generic_hits) == 0


def test_fallback_uses_generic_search_if_scoped_search_is_empty(tmp_path: Path, monkeypatch) -> None:
    calls = {"scoped": 0, "generic": 0}

    def _fake_scoped_search(*args, **kwargs):
        _ = (args, kwargs)
        calls["scoped"] += 1
        return {"search": []}

    def _fake_generic_search(*args, **kwargs):
        _ = (args, kwargs)
        calls["generic"] += 1
        return {"search": [{"id": "Q1499182"}]}

    def _fake_fetch(*args, **kwargs):
        _ = (args, kwargs)
        return {
            "entities": {
                "Q1499182": {
                    "id": "Q1499182",
                    "labels": {"de": {"value": "Markus Lanz"}},
                    "descriptions": {},
                    "aliases": {},
                    "claims": {
                        "P31": [
                            {
                                "mainsnak": {
                                    "datavalue": {
                                        "value": {"entity-type": "item", "id": "Q215627"}
                                    }
                                }
                            }
                        ]
                    },
                }
            }
        }

    monkeypatch.setattr(
        "process.candidate_generation.wikidata.fallback_matcher.get_or_search_entities_by_label_in_class_ranked",
        _fake_scoped_search,
    )
    monkeypatch.setattr(
        "process.candidate_generation.wikidata.fallback_matcher.get_or_search_entities_by_label",
        _fake_generic_search,
    )
    monkeypatch.setattr(
        "process.candidate_generation.wikidata.fallback_matcher.get_or_fetch_entity",
        _fake_fetch,
    )

    unresolved = [
        {
            "mention_id": "m1",
            "mention_type": "person",
            "mention_label": "Markus Lanz",
            "context": "test",
        }
    ]
    class_scope_hints = {"person": ["Q215627"]}

    result = run_fallback_string_matching_stage(
        tmp_path,
        unresolved_targets=unresolved,
        seeds={"Q100"},
        core_class_qids={"Q215627"},
        class_scope_hints=class_scope_hints,
        config={
            "fallback_enabled_mention_types": ["person"],
            "fallback_search_languages": ["de"],
            "fallback_prefer_class_scoped_search": True,
            "fallback_allow_generic_search_after_class_scoped": True,
        },
    )

    assert calls["scoped"] >= 1
    assert calls["generic"] >= 1
    assert len(result.fallback_candidates) == 1
    assert int(result.class_scoped_search_queries) >= 1
    assert int(result.generic_search_queries) >= 1
    assert int(result.class_scoped_hits) == 0
    assert int(result.generic_hits) >= 1


def test_merge_stage_candidates_keeps_graph_authority() -> None:
    graph = [
        {
            "mention_id": "m1",
            "candidate_id": "Q1",
            "source": "graph_stage",
            "candidate_label": "Graph Label",
        }
    ]
    fallback = [
        {
            "mention_id": "m1",
            "candidate_id": "Q1",
            "source": "fallback_string",
            "candidate_label": "Fallback Label",
        },
        {
            "mention_id": "m1",
            "candidate_id": "Q2",
            "source": "fallback_string",
            "candidate_label": "Fallback Alt",
        },
    ]

    merged = merge_stage_candidates(graph, fallback)
    assert len(merged) == 2
    primary = [row for row in merged if row["candidate_id"] == "Q1"][0]
    assert primary["source"] == "graph_stage"


def test_fallback_initializes_request_context_with_budget(tmp_path: Path, monkeypatch) -> None:
    calls: list[dict] = []
    ended = {"count": 0}

    def _fake_begin(
        *,
        budget_remaining: int,
        query_delay_seconds: float,
        progress_every_calls: int = 50,
        context_label: str = "wikidata",
        event_emitter=None,
        event_phase: str | None = None,
    ) -> None:
        _ = (event_emitter, event_phase)
        calls.append(
            {
                "budget_remaining": int(budget_remaining),
                "query_delay_seconds": float(query_delay_seconds),
                "progress_every_calls": int(progress_every_calls),
                "context_label": str(context_label),
            }
        )

    def _fake_end() -> int:
        ended["count"] += 1
        return 0

    monkeypatch.setattr(
        "process.candidate_generation.wikidata.fallback_matcher.begin_request_context",
        _fake_begin,
    )
    monkeypatch.setattr(
        "process.candidate_generation.wikidata.fallback_matcher.end_request_context",
        _fake_end,
    )

    run_fallback_string_matching_stage(
        tmp_path,
        unresolved_targets=[],
        seeds={"Q100"},
        core_class_qids={"Q215627"},
        class_scope_hints={"person": ["Q215627"]},
        config={
            "network_budget_remaining": 7,
            "query_delay_seconds": 0.25,
            "network_progress_every": 50,
            "fallback_enabled_mention_types": ["person"],
        },
    )

    assert calls == [
        {
            "budget_remaining": 7,
            "query_delay_seconds": 0.25,
            "progress_every_calls": 50,
            "context_label": "fallback_stage",
        }
    ]
    assert ended["count"] == 1


def test_fallback_handles_budget_hit_without_crashing(tmp_path: Path, monkeypatch) -> None:
    def _budget_hit(*args, **kwargs):
        _ = (args, kwargs)
        raise RuntimeError("Network query budget hit")

    monkeypatch.setattr(
        "process.candidate_generation.wikidata.fallback_matcher.get_or_search_entities_by_label",
        _budget_hit,
    )

    unresolved = [
        {
            "mention_id": "m1",
            "mention_type": "person",
            "mention_label": "Markus Lanz",
            "context": "test",
        }
    ]

    result = run_fallback_string_matching_stage(
        tmp_path,
        unresolved_targets=unresolved,
        seeds={"Q100"},
        core_class_qids={"Q215627"},
        class_scope_hints={"person": ["Q215627"]},
        config={
            "max_queries_per_run": 1,
            "fallback_search_languages": ["de"],
            "fallback_enabled_mention_types": ["person"],
        },
    )

    assert result.fallback_candidates == []


def test_fallback_explicit_zero_budget_disables_endpoint_search(tmp_path: Path, monkeypatch) -> None:
    called = {"count": 0}

    def _should_not_be_called(*args, **kwargs):
        _ = (args, kwargs)
        called["count"] += 1
        return {"search": []}

    monkeypatch.setattr(
        "process.candidate_generation.wikidata.fallback_matcher.get_or_search_entities_by_label",
        _should_not_be_called,
    )

    unresolved = [
        {
            "mention_id": "m1",
            "mention_type": "person",
            "mention_label": "Markus Lanz",
            "context": "test",
        }
    ]

    result = run_fallback_string_matching_stage(
        tmp_path,
        unresolved_targets=unresolved,
        seeds={"Q100"},
        core_class_qids={"Q215627"},
        class_scope_hints={"person": ["Q215627"]},
        config={
            "network_budget_remaining": 0,
            "fallback_search_languages": ["de"],
            "fallback_enabled_mention_types": ["person"],
        },
    )

    assert called["count"] == 0
    assert result.fallback_candidates == []


def test_fallback_stops_gracefully_when_user_interrupt_requested(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "process.candidate_generation.wikidata.fallback_matcher._termination_requested",
        lambda _repo_root: True,
    )

    unresolved = [
        {
            "mention_id": "m1",
            "mention_type": "person",
            "mention_label": "Markus Lanz",
            "context": "test",
        }
    ]

    result = run_fallback_string_matching_stage(
        tmp_path,
        unresolved_targets=unresolved,
        seeds={"Q100"},
        core_class_qids={"Q215627"},
        class_scope_hints={"person": ["Q215627"]},
        config={"max_queries_per_run": -1, "fallback_enabled_mention_types": ["person"]},
    )

    assert result.fallback_candidates == []
    assert result.eligible_for_expansion_qids == set()


def test_fallback_emits_candidate_matched_events(tmp_path: Path) -> None:
    entity_doc = {
        "id": "Q1499182",
        "labels": {"de": {"value": "Markus Lanz"}},
        "descriptions": {},
        "aliases": {},
        "claims": {
            "P31": [
                {
                    "mainsnak": {
                        "datavalue": {
                            "value": {"entity-type": "item", "id": "Q215627"}
                        }
                    }
                }
            ]
        },
    }
    upsert_discovered_item(tmp_path, "Q1499182", entity_doc, "2026-03-31T12:00:00Z")

    unresolved = [
        {
            "mention_id": "m1",
            "mention_type": "person",
            "mention_label": "Markus Lanz",
            "context": "test",
        }
    ]

    run_fallback_string_matching_stage(
        tmp_path,
        unresolved_targets=unresolved,
        seeds={"Q100"},
        core_class_qids={"Q215627"},
        class_scope_hints={"person": ["Q215627"]},
        config={"fallback_enabled_mention_types": ["person"]},
    )

    matched_events = []
    for chunk_path in sorted(_chunks_dir(tmp_path).glob("*.jsonl")):
        for event in _iter_jsonl_events(chunk_path):
            if event.get("event_type") == "candidate_matched":
                matched_events.append(event)

    assert matched_events
    payload = matched_events[0].get("payload", {})
    assert payload.get("mention_id") == "m1"
    assert payload.get("candidate_id") == "Q1499182"


def test_fallback_requires_explicit_enabled_mention_types_config(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="fallback_enabled_mention_types"):
        run_fallback_string_matching_stage(
            tmp_path,
            unresolved_targets=[],
            seeds={"Q100"},
            core_class_qids={"Q215627"},
            class_scope_hints={"person": ["Q215627"]},
            config={},
        )
