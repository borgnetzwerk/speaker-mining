"""Track and cache Wikidata classes observed during candidate expansion.

Captures instance-of (P31) and subclass-of (P279) Q-IDs for each processed entity,
fetches and caches those class entities, and maintains an aggregate classes.csv.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from .cache import _atomic_write_df, _atomic_write_text, _entity_from_payload, _latest_cached_record, _wikidata_dir
from .common import canonical_qid, pick_entity_label
from .entity import get_or_fetch_entity


def _classes_csv_path(root: Path) -> Path:
	return _wikidata_dir(root) / "classes.csv"


def _observations_path(root: Path) -> Path:
	return _wikidata_dir(root) / "class_observations.json"


def _load_setup_classes(root: Path) -> dict[str, dict[str, str]]:
	path = root / "data" / "00_setup" / "classes.csv"
	if not path.exists():
		return {}
	df = pd.read_csv(path)
	if df.empty:
		return {}
	lookup: dict[str, dict[str, str]] = {}
	for _, row in df.iterrows():
		qid = canonical_qid(row.get("wikidata_id", ""))
		if not qid:
			continue
		lookup[qid] = {
			"name": str(row.get("name", "") or ""),
			"alias": str(row.get("alias", "") or ""),
		}
	return lookup


def _extract_class_qids(entity_doc: dict) -> tuple[list[str], list[str]]:
	claims = entity_doc.get("claims", {})
	instance_qids: list[str] = []
	subclass_qids: list[str] = []
	for pid, target in (("P31", instance_qids), ("P279", subclass_qids)):
		for claim in claims.get(pid, []) or []:
			mainsnak = claim.get("mainsnak", {})
			datavalue = mainsnak.get("datavalue", {})
			value = datavalue.get("value")
			if isinstance(value, dict) and value.get("entity-type") == "item":
				qid = canonical_qid(value.get("id", ""))
				if qid:
					target.append(qid)
	return instance_qids, subclass_qids


def _load_observations(root: Path) -> dict[str, dict[str, list[str]]]:
	path = _observations_path(root)
	if not path.exists():
		return {}
	try:
		payload = json.loads(path.read_text(encoding="utf-8"))
		if isinstance(payload, dict):
			return payload
	except Exception:
		pass
	return {}


def _write_observations(root: Path, observations: dict[str, dict[str, list[str]]]) -> None:
	path = _observations_path(root)
	_atomic_write_text(path, json.dumps(observations, ensure_ascii=False, indent=2))


def _get_cached_class_label(root: Path, qid: str) -> str:
	cached = _latest_cached_record(root, "entity", qid)
	if not cached:
		return ""
	entity_doc = _entity_from_payload(cached[0].get("payload", {}), qid)
	return pick_entity_label(entity_doc)


def update_class_cache(
	root: Path | str,
	entity_qid: str,
	entity_payload: dict[str, Any],
	cache_max_age_days: int,
	*,
	timeout: int = 30,
) -> dict[str, int]:
	"""Update class observations for a newly processed entity.

	Returns counts for metrics:
	  - new_instance_classes
	  - new_subclass_classes
	"""
	repo_root = Path(root)
	qid = canonical_qid(entity_qid)
	if not qid:
		return {"new_instance_classes": 0, "new_subclass_classes": 0}

	observations = _load_observations(repo_root)
	if qid in observations:
		return {"new_instance_classes": 0, "new_subclass_classes": 0}

	entity_doc = _entity_from_payload(entity_payload, qid)
	instance_qids, subclass_qids = _extract_class_qids(entity_doc)

	# Cache class entities for richer labels and local availability.
	class_qids = sorted(set(instance_qids + subclass_qids))
	for class_qid in class_qids:
		get_or_fetch_entity(
			repo_root,
			class_qid,
			cache_max_age_days,
			timeout=timeout,
		)

	observations[qid] = {
		"instance_of": sorted(set(instance_qids)),
		"subclass_of": sorted(set(subclass_qids)),
	}
	_write_observations(repo_root, observations)

	# Aggregate counts across observed entities.
	instance_counts: dict[str, int] = {}
	subclass_counts: dict[str, int] = {}
	for entry in observations.values():
		for class_qid in entry.get("instance_of", []):
			instance_counts[class_qid] = instance_counts.get(class_qid, 0) + 1
		for class_qid in entry.get("subclass_of", []):
			subclass_counts[class_qid] = subclass_counts.get(class_qid, 0) + 1

	setup_lookup = _load_setup_classes(repo_root)
	all_class_qids = sorted(set(instance_counts) | set(subclass_counts))
	rows: list[dict[str, Any]] = []
	for class_qid in all_class_qids:
		label = _get_cached_class_label(repo_root, class_qid)
		if not label:
			label = setup_lookup.get(class_qid, {}).get("name", "")
		rows.append(
			{
				"class_label": label or class_qid,
				"class_qid": class_qid,
				"instance_count": int(instance_counts.get(class_qid, 0)),
				"subclass_count": int(subclass_counts.get(class_qid, 0)),
			}
		)

	classes_df = pd.DataFrame(rows)
	if classes_df.empty:
		classes_df = pd.DataFrame(
			columns=["class_label", "class_qid", "instance_count", "subclass_count"]
		)
	else:
		classes_df = classes_df.sort_values(
			by=["instance_count", "subclass_count", "class_label"],
			ascending=[False, False, True],
		).reset_index(drop=True)

	_atomic_write_df(_classes_csv_path(repo_root), classes_df)

	return {
		"new_instance_classes": len(set(instance_qids)),
		"new_subclass_classes": len(set(subclass_qids)),
	}
