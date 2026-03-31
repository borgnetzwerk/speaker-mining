from __future__ import annotations

# pyright: reportMissingImports=false

from process.candidate_generation.wikidata.inlinks import build_inlinks_query


def test_inlinks_query_includes_order_and_offset() -> None:
    query = build_inlinks_query("Q42", limit=200, offset=400)
    assert "ORDER BY ?source ?prop" in query
    assert "LIMIT 200" in query
    assert "OFFSET 400" in query
