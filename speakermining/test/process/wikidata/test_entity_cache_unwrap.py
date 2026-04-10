from __future__ import annotations

# pyright: reportMissingImports=false

from pathlib import Path
from urllib.parse import parse_qs, urlparse

from process.candidate_generation.wikidata.entity import (
    get_or_build_outlinks,
    get_or_fetch_entity,
    get_or_fetch_entities_batch,
    get_or_fetch_inlinks,
    get_or_fetch_property,
    get_or_search_entities_by_label,
    get_or_search_entities_by_label_in_class,
    get_or_search_entities_by_label_in_class_ranked,
)
from process.candidate_generation.wikidata.common import get_active_wikidata_languages, set_active_wikidata_languages
from process.candidate_generation.wikidata import cache as cache_module
from process.candidate_generation.wikidata import entity as entity_module
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


def test_get_or_fetch_entity_uses_index_after_first_lookup(tmp_path: Path, monkeypatch) -> None:
    write_query_event(
        tmp_path,
        endpoint="wikidata_api",
        normalized_query="entity:Q1",
        source_step="entity_fetch",
        status="success",
        key="Q1",
        payload={"entities": {"Q1": {"id": "Q1", "labels": {"en": {"language": "en", "value": "One"}}}}},
        http_status=200,
        error=None,
    )

    first_payload = get_or_fetch_entity(tmp_path, "Q1", cache_max_age_days=9999)
    assert first_payload["entities"]["Q1"]["labels"]["en"]["value"] == "One"

    def _fail_if_scanned(*_args, **_kwargs):
        raise AssertionError("iter_query_events should not be called after the cache index is primed")

    monkeypatch.setattr(cache_module, "iter_query_events", _fail_if_scanned)

    write_query_event(
        tmp_path,
        endpoint="wikidata_api",
        normalized_query="entity:Q1?revision=latest",
        source_step="entity_fetch",
        status="success",
        key="Q1",
        payload={"entities": {"Q1": {"id": "Q1", "labels": {"en": {"language": "en", "value": "Two"}}}}},
        http_status=200,
        error=None,
    )

    second_payload = get_or_fetch_entity(tmp_path, "Q1", cache_max_age_days=9999)
    assert second_payload["entities"]["Q1"]["labels"]["en"]["value"] == "Two"


def test_get_or_fetch_entity_filters_cached_payload_languages(tmp_path: Path) -> None:
    previous = get_active_wikidata_languages()
    try:
        set_active_wikidata_languages({"en": True})
        write_query_event(
            tmp_path,
            endpoint="wikidata_api",
            normalized_query="entity:Q1",
            source_step="entity_fetch",
            status="success",
            key="Q1",
            payload={
                "entities": {
                    "Q1": {
                        "id": "Q1",
                        "labels": {
                            "en": {"language": "en", "value": "One"},
                            "fr": {"language": "fr", "value": "Un"},
                            "mul": {"language": "mul", "value": "One Default"},
                        },
                        "descriptions": {
                            "en": {"language": "en", "value": "desc one"},
                            "fr": {"language": "fr", "value": "desc un"},
                            "mul": {"language": "mul", "value": "desc default"},
                        },
                        "aliases": {
                            "en": [{"language": "en", "value": "Alias EN"}],
                            "fr": [{"language": "fr", "value": "Alias FR"}],
                            "mul": [{"language": "mul", "value": "Alias Default"}],
                        },
                    }
                }
            },
            http_status=200,
            error=None,
        )

        payload = get_or_fetch_entity(tmp_path, "Q1", cache_max_age_days=9999)
        node = payload["entities"]["Q1"]

        assert set(node["labels"].keys()) == {"en", "mul"}
        assert set(node["descriptions"].keys()) == {"en", "mul"}
        assert set(node["aliases"].keys()) == {"en", "mul"}
    finally:
        set_active_wikidata_languages(previous)


def test_get_or_fetch_entity_fetches_only_missing_literal_languages(tmp_path: Path, monkeypatch) -> None:
    previous = get_active_wikidata_languages()
    try:
        set_active_wikidata_languages({"de": True, "en": True})
        write_query_event(
            tmp_path,
            endpoint="wikidata_api",
            normalized_query="entity:Q1",
            source_step="entity_fetch",
            status="success",
            key="Q1",
            payload={
                "entities": {
                    "Q1": {
                        "id": "Q1",
                        "labels": {
                            "de": {"language": "de", "value": "Eins"},
                            "en": {"language": "en", "value": "One"},
                            "mul": {"language": "mul", "value": "One Default"},
                        },
                        "descriptions": {
                            "de": {"language": "de", "value": "Beschreibung"},
                            "en": {"language": "en", "value": "Description"},
                            "mul": {"language": "mul", "value": "Description Default"},
                        },
                        "aliases": {
                            "de": [{"language": "de", "value": "Alias DE"}],
                            "en": [{"language": "en", "value": "Alias EN"}],
                            "mul": [{"language": "mul", "value": "Alias Default"}],
                        },
                        "claims": {"P31": [], "P279": []},
                        "_fetched_literal_languages": ["de", "en"],
                    }
                }
            },
            http_status=200,
            error=None,
        )

        observed_urls: list[str] = []

        def _fake_http_get_json(url: str, accept: str = "application/json", timeout: int = 30, **_kwargs):
            observed_urls.append(url)
            return {
                "entities": {
                    "Q1": {
                        "id": "Q1",
                        "labels": {"it": {"language": "it", "value": "Uno"}},
                        "descriptions": {"it": {"language": "it", "value": "Descrizione"}},
                        "aliases": {"it": [{"language": "it", "value": "Alias IT"}]},
                    }
                }
            }

        monkeypatch.setattr(entity_module, "_http_get_json", _fake_http_get_json)

        set_active_wikidata_languages({"de": True, "en": True, "it": True})
        payload = get_or_fetch_entity(tmp_path, "Q1", cache_max_age_days=9999)

        assert len(observed_urls) == 1
        query = parse_qs(urlparse(observed_urls[0]).query)
        assert query.get("props", [""])[0] == "labels|descriptions|aliases"
        assert query.get("languages", [""])[0] == "it|mul"

        node = payload["entities"]["Q1"]
        assert set(node["labels"].keys()) == {"de", "en", "it", "mul"}
        assert set(node["descriptions"].keys()) == {"de", "en", "it", "mul"}
        assert set(node["aliases"].keys()) == {"de", "en", "it", "mul"}
        assert "claims" in node
        assert set(node.get("_fetched_literal_languages", [])) == {"de", "en", "it"}
    finally:
        set_active_wikidata_languages(previous)


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


def test_get_or_fetch_entities_batch_continues_after_fallback_timeout(tmp_path: Path, monkeypatch) -> None:
    calls: list[str] = []

    def _fake_http_get_json(url: str, accept: str = "application/json", timeout: int = 30, **_kwargs):
        _ = (url, accept, timeout)
        # Return no entities so the batch path must fall back to per-qid fetches.
        return {"entities": {}}

    def _fake_get_or_fetch_entity(root: Path, qid: str, cache_max_age_days: int, timeout: int = 30):
        _ = (root, cache_max_age_days, timeout)
        calls.append(qid)
        if qid == "Q100":
            raise TimeoutError("The read operation timed out")
        return {"entities": {qid: {"id": qid}}}

    monkeypatch.setattr(entity_module, "_http_get_json", _fake_http_get_json)
    monkeypatch.setattr(entity_module, "get_or_fetch_entity", _fake_get_or_fetch_entity)

    payloads = get_or_fetch_entities_batch(
        tmp_path,
        ["Q100", "Q101"],
        cache_max_age_days=0,
        timeout=1,
    )

    assert calls == ["Q100", "Q101"]
    assert "Q100" not in payloads
    assert payloads["Q101"]["entities"]["Q101"]["id"] == "Q101"


def test_get_or_search_entities_by_label_in_class_returns_unwrapped_cached_payload(tmp_path: Path) -> None:
    key = "Q215627|de|5|exact|Markus Lanz"
    write_query_event(
        tmp_path,
        endpoint="wikidata_sparql",
        normalized_query=(
            "class_scoped_label_search:exact:"
            "class=Q215627;language=de;limit=5;search=Markus Lanz"
        ),
        source_step="entity_fetch",
        status="success",
        key=key,
        payload={"search": [{"id": "Q1499182", "label": "Markus Lanz"}]},
        http_status=200,
        error=None,
    )

    payload = get_or_search_entities_by_label_in_class(
        tmp_path,
        "Markus Lanz",
        "Q215627",
        cache_max_age_days=9999,
        language="de",
        limit=5,
    )
    assert "search" in payload
    assert payload["search"][0]["id"] == "Q1499182"


def test_get_or_search_entities_by_label_in_class_issues_sparql_query(tmp_path: Path, monkeypatch) -> None:
    observed_urls: list[str] = []

    def _fake_http_get_json(url: str, accept: str = "application/json", timeout: int = 30, **_kwargs):
        observed_urls.append(url)
        assert accept == "application/sparql-results+json"
        _ = timeout
        return {
            "results": {
                "bindings": [
                    {
                        "item": {"value": "http://www.wikidata.org/entity/Q1499182"},
                        "itemLabel": {"value": "Markus Lanz"},
                    }
                ]
            }
        }

    monkeypatch.setattr(entity_module, "_http_get_json", _fake_http_get_json)

    payload = get_or_search_entities_by_label_in_class(
        tmp_path,
        "Markus Lanz",
        "Q215627",
        cache_max_age_days=0,
        language="de",
        limit=3,
        timeout=7,
    )

    assert observed_urls
    assert "query=" in observed_urls[0]
    assert payload["search"][0]["id"] == "Q1499182"


def test_get_or_search_entities_by_label_in_class_ranked_prefers_exact_then_prefix(
    tmp_path: Path,
    monkeypatch,
) -> None:
    calls: list[str] = []

    def _fake_http_get_json(url: str, accept: str = "application/json", timeout: int = 30, **_kwargs):
        calls.append(url)
        _ = (accept, timeout)
        if len(calls) == 1:
            return {"results": {"bindings": []}}
        return {
            "results": {
                "bindings": [
                    {
                        "item": {"value": "http://www.wikidata.org/entity/Q1499182"},
                        "itemLabel": {"value": "Markus Lanz"},
                    }
                ]
            }
        }

    monkeypatch.setattr(entity_module, "_http_get_json", _fake_http_get_json)

    payload = get_or_search_entities_by_label_in_class_ranked(
        tmp_path,
        "Markus",
        "Q215627",
        cache_max_age_days=0,
        language="de",
        limit=3,
        timeout=7,
    )

    assert len(calls) == 2
    assert payload["search"][0]["id"] == "Q1499182"
    assert payload["search"][0]["match_mode"] == "prefix"
