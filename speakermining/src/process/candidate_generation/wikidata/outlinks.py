"""Extract entity-to-entity and entity-to-property links from Wikidata entities.

Parses Wikidata entity claims to discover which other entities (Q-IDs) and
properties (P-IDs) are referenced by the current entity. Used to expand
the Wikidata tree during candidate discovery.
"""
from __future__ import annotations

from .common import canonical_pid, canonical_qid


def extract_outlinks(qid: str, entity_doc: dict) -> dict:
	"""Extract outgoing links from a Wikidata entity.
	
	Parses the entity's claims to find all referenced entities (Q-IDs) and
	properties (P-IDs). Only processes entity-type datavalues (ignores strings,
	times, etc.).
	
	Args:
		qid: The source entity Q-ID (canonical form).
		entity_doc: Wikidata entity JSON document.
	
	Returns:
		Dict with keys:
		  - qid: The entity Q-ID.
		  - property_ids: Sorted list of P-IDs referenced in claims.
		  - linked_qids: Sorted list of Q-IDs referenced in entity-type claims.
		  - edges: List of {from_qid, pid, to_qid} tuples.
	"""
	property_ids: set[str] = set()
	linked_qids: set[str] = set()
	edges: list[dict[str, str]] = []

	claims = entity_doc.get("claims", {})
	for raw_pid, claim_list in claims.items():
		pid = canonical_pid(raw_pid)
		if not pid:
			continue
		property_ids.add(pid)

		for claim in claim_list or []:
			mainsnak = claim.get("mainsnak", {})
			datavalue = mainsnak.get("datavalue", {})
			value = datavalue.get("value")

			if isinstance(value, dict) and value.get("entity-type") == "item":
				to_qid = canonical_qid(value.get("id", ""))
				if not to_qid:
					continue
				linked_qids.add(to_qid)
				edges.append({"from_qid": canonical_qid(qid), "pid": pid, "to_qid": to_qid})

	return {
		"qid": canonical_qid(qid),
		"property_ids": sorted(property_ids),
		"linked_qids": sorted(linked_qids),
		"edges": edges,
	}
