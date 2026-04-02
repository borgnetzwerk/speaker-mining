from __future__ import annotations

# pyright: reportMissingImports=false

from pathlib import Path

from process.candidate_generation.wikidata.entity import (
    get_or_build_outlinks,
    get_or_fetch_entity,
    get_or_fetch_inlinks,
    get_or_fetch_property,
    get_or_search_entities_by_label,
)
from process.candidate_generation.wikidata.event_log import write_query_event


def test_get_or_fetch_entity_returns_unwrapped_cached_payload(tmp_path: Path) -> None:
    write_query_event(
        tmp_path,
        endpoint="wikidata_api",
        normalized_query="entity:Q1",
        source_step="entity_fetch",
        status="success",
        key="Q1",
        payload={"entities": {"Q1": {"id": "Q1"}}},
        http_status=200,
        error=None,
    )

    payload = get_or_fetch_entity(tmp_path, "Q1", cache_max_age_days=9999)
    assert "entities" in payload
    assert "response_data" not in payload


def test_get_or_fetch_property_returns_unwrapped_cached_payload(tmp_path: Path) -> None:
    write_query_event(
        tmp_path,
        endpoint="wikidata_api",
        normalized_query="property:P31",
        source_step="property_fetch",
        status="success",
        key="P31",
        payload={"entities": {"P31": {"id": "P31"}}},
        http_status=200,
        error=None,
    )

    payload = get_or_fetch_property(tmp_path, "P31", cache_max_age_days=9999)
    assert "entities" in payload
    assert "response_data" not in payload


def test_get_or_fetch_inlinks_returns_unwrapped_cached_payload(tmp_path: Path) -> None:
    cache_key = "Q1_limit50_offset0"
    write_query_event(
        tmp_path,
        endpoint="wikidata_sparql",
        normalized_query="inlinks:target=Q1;page_size=50;offset=0;order=source_prop",
        source_step="inlinks_fetch",
        status="success",
        key=cache_key,
        payload={"results": {"bindings": [{"source": {"value": "Q2"}}]}},
        http_status=200,
        error=None,
    )

    payload = get_or_fetch_inlinks(tmp_path, "Q1", cache_max_age_days=9999, inlinks_limit=50, offset=0)
    assert "results" in payload
    assert "response_data" not in payload


def test_get_or_build_outlinks_returns_unwrapped_cached_payload(tmp_path: Path) -> None:
    write_query_event(
        tmp_path,
        endpoint="derived_local",
        normalized_query="outlinks_from_entity:Q1",
        source_step="outlinks_build",
        status="success",
        key="Q1",
        payload={"qid": "Q1", "linked_qids": ["Q2"], "property_ids": ["P50"], "edges": []},
        http_status=None,
        error=None,
    )

    payload = get_or_build_outlinks(tmp_path, "Q1", entity_payload={}, cache_max_age_days=9999)
    assert payload.get("qid") == "Q1"
    assert "response_data" not in payload


def test_get_or_search_entities_by_label_returns_unwrapped_cached_payload(tmp_path: Path) -> None:
    key = "de|10|Markus Lanz"
    write_query_event(
        tmp_path,
        endpoint="wikidata_api",
        normalized_query="wbsearchentities:language=de;limit=10;search=Markus Lanz",
        source_step="entity_fetch",
        status="success",
        key=key,
        payload={"search": [{"id": "Q1499182", "label": "Markus Lanz"}]},
        http_status=200,
        error=None,
    )

    payload = get_or_search_entities_by_label(
        tmp_path,
        "Markus Lanz",
        cache_max_age_days=9999,
        language="de",
        limit=10,
    )
    assert "search" in payload
    assert "response_data" not in payload
