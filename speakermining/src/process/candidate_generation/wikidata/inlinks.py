"""Query and parse Wikidata inlinks (incoming references).

Inlinks are entities that point to a given entity via their claims.
Used to expand the Wikidata tree by discovering related entities.
"""
from __future__ import annotations

from .common import pid_from_uri, qid_from_uri


def build_inlinks_query(qid: str, limit: int = 200) -> str:
	"""Build a SPARQL query to find entities that reference a given Q-ID.
	
	Constructs a SPARQL query that finds all entity-to-entity relationships
	where the target is the given Q-ID. Results are limited to avoid excessive data.
	
	Args:
		qid: Target entity Q-ID (canonical form).
		limit: Maximum number of inlink results (default 200).
	
	Returns:
		SPARQL query string (ready for URL encoding and execution).
	"""
	safe_limit = max(1, int(limit))
	return f"""
SELECT ?source ?prop WHERE {{
  ?source ?prop wd:{qid} .
  FILTER(STRSTARTS(STR(?source), STR(wd:)))
  FILTER(STRSTARTS(STR(?prop), STR(wdt:)))
}}
LIMIT {safe_limit}
""".strip()


def parse_inlinks_results(payload: dict) -> list[dict[str, str]]:
	"""Parse SPARQL JSON response containing inlink query results.
	
	Extracts source Q-IDs and property P-IDs from a SPARQL query response.
	Handles URI parsing and validation.
	
	Args:
		payload: SPARQL JSON response dict.
	
	Returns:
		List of dicts with keys: {source_qid, pid}.
		Skips entries with missing or invalid source_qid.
	"""
	rows: list[dict[str, str]] = []
	bindings = payload.get("results", {}).get("bindings", [])
	for item in bindings:
		source_uri = item.get("source", {}).get("value", "")
		prop_uri = item.get("prop", {}).get("value", "")
		source_qid = qid_from_uri(source_uri)
		pid = pid_from_uri(prop_uri)
		if not source_qid:
			continue
		rows.append({"source_qid": source_qid, "pid": pid})
	return rows
