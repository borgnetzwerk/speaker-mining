from __future__ import annotations

# pyright: reportMissingImports=false

import pytest

from process.candidate_generation.wikidata.event_log import (
    build_class_membership_resolved_event,
    build_eligibility_transition_event,
    build_query_event,
    build_triple_discovered_event,
    compute_query_hash,
)


def test_event_schema_required_fields() -> None:
    event = build_query_event(
        endpoint="wikidata_api",
        normalized_query="entity:Q1499182",
        source_step="entity_fetch",
        status="success",
        key="Q1499182",
        payload={"entities": {}},
        http_status=200,
        error=None,
    )

    required = {
        "event_version",
        "event_type",
        "timestamp_utc",
        "payload",
    }
    assert required.issubset(set(event.keys()))
    assert event["event_version"] == "v3"
    assert event["payload"]["query_hash"] == compute_query_hash("wikidata_api", "entity:Q1499182")
    assert event["payload"]["endpoint"] == "wikidata_api"
    assert event["payload"]["source_step"] == "entity_fetch"


def test_query_hash_is_deterministic() -> None:
    h1 = compute_query_hash("wikidata_sparql", "inlinks:target=Q1;page_size=200;offset=0;order=source_prop")
    h2 = compute_query_hash("wikidata_sparql", "inlinks:target=Q1;page_size=200;offset=0;order=source_prop")
    assert h1 == h2


def test_event_rejects_unknown_source_step() -> None:
    with pytest.raises(ValueError, match="Unsupported source_step"):
        build_query_event(
            endpoint="wikidata_api",
            normalized_query="entity:Q1499182",
            source_step="unknown_step",
            status="success",
            key="Q1499182",
            payload={"entities": {}},
            http_status=200,
            error=None,
        )


def test_build_triple_discovered_event_schema() -> None:
    event = build_triple_discovered_event(
        subject_qid="Q100",
        predicate_pid="P31",
        object_qid="Q5",
        source_step="outlinks_build",
    )
    assert event["event_type"] == "triple_discovered"
    payload = event["payload"]
    assert payload["subject_qid"] == "Q100"
    assert payload["predicate_pid"] == "P31"
    assert payload["object_qid"] == "Q5"
    assert payload["source_step"] == "outlinks_build"


def test_build_class_membership_resolved_event_schema() -> None:
    event = build_class_membership_resolved_event(
        entity_qid="Q200",
        class_id="Q5",
        path_to_core_class="Q5|Q215627",
        subclass_of_core_class=True,
        is_class_node=False,
    )
    assert event["event_type"] == "class_membership_resolved"
    payload = event["payload"]
    assert payload["entity_qid"] == "Q200"
    assert payload["class_id"] == "Q5"
    assert payload["path_to_core_class"] == "Q5|Q215627"
    assert payload["subclass_of_core_class"] is True
    assert payload["is_class_node"] is False


def test_build_eligibility_transition_event_schema() -> None:
    event = build_eligibility_transition_event(
        entity_qid="Q200",
        previous_eligible=False,
        current_eligible=True,
        previous_reason="no_core_class_match",
        current_reason="direct_seed_link_and_core_match",
        path_to_core_class="Q5|Q215627",
    )
    assert event["event_type"] == "eligibility_transition"
    payload = event["payload"]
    assert payload["entity_qid"] == "Q200"
    assert payload["previous_eligible"] is False
    assert payload["current_eligible"] is True
    assert payload["previous_reason"] == "no_core_class_match"
    assert payload["current_reason"] == "direct_seed_link_and_core_match"
    assert payload["path_to_core_class"] == "Q5|Q215627"
