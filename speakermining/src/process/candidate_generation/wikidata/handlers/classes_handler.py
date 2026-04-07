"""ClassesHandler: derives class projection from entity query_response events."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

from process.candidate_generation.wikidata.cache import _atomic_write_df
from process.candidate_generation.wikidata.bootstrap import load_core_classes, load_other_interesting_classes, load_root_classes
from process.candidate_generation.wikidata.class_resolver import resolve_class_path
from process.candidate_generation.wikidata.common import canonical_qid, effective_core_class_qids
from process.candidate_generation.wikidata.event_handler import EventHandler
from process.candidate_generation.wikidata.event_log import get_query_event_field, get_query_event_response_data
from process.candidate_generation.wikidata.handler_registry import HandlerRegistry


def _claim_item_qids(entity_doc: dict, pid: str) -> list[str]:
    out: list[str] = []
    claims = entity_doc.get("claims", {}) if isinstance(entity_doc.get("claims"), dict) else {}
    for claim in claims.get(pid, []) or []:
        mainsnak = claim.get("mainsnak", {}) if isinstance(claim, dict) else {}
        value = (mainsnak.get("datavalue", {}) or {}).get("value")
        if isinstance(value, dict) and value.get("entity-type") == "item":
            qid = canonical_qid(value.get("id", ""))
            if qid:
                out.append(qid)
    return sorted(set(out))


def _pick_lang_text(mapping: dict, lang: str) -> str:
    if not isinstance(mapping, dict):
        return ""
    node = mapping.get(lang, {})
    if isinstance(node, dict) and node.get("value"):
        return str(node.get("value"))
    for info in mapping.values():
        if isinstance(info, dict) and info.get("value"):
            return str(info.get("value"))
    return ""


def _alias_pipe(mapping: dict, lang: str) -> str:
    if not isinstance(mapping, dict):
        return ""
    values: set[str] = set()
    for item in mapping.get(lang, []) or []:
        if isinstance(item, dict) and item.get("value"):
            values.add(str(item.get("value")))
    for alias_items in mapping.values():
        for item in alias_items or []:
            if isinstance(item, dict) and item.get("value"):
                values.add(str(item.get("value")))
    return "|".join(sorted(values))


def _class_filename_lookup(repo_root: Path) -> dict[str, str]:
    lookup: dict[str, str] = {}
    setup_rows = load_core_classes(repo_root) + load_root_classes(repo_root) + load_other_interesting_classes(repo_root)
    for row in setup_rows:
        qid = canonical_qid(str(row.get("wikidata_id", "") or ""))
        filename = str(row.get("filename", "") or "")
        if qid and filename:
            lookup[qid] = filename
    return lookup


class ClassesHandler(EventHandler):
    """Builds `classes.csv` rollup rows from entity class-resolution outcomes."""

    def __init__(self, repo_root: Path, handler_registry: Optional[HandlerRegistry] = None):
        self.repo_root = Path(repo_root)
        self.handler_registry = handler_registry
        self._last_seq = 0
        self._entity_docs: dict[str, dict] = {}

    def name(self) -> str:
        return "ClassesHandler"

    def last_processed_sequence(self) -> int:
        if self.handler_registry:
            return self.handler_registry.get_progress(self.name())
        return self._last_seq

    def process_batch(self, events: list[dict]) -> None:
        for event in events:
            if event.get("event_type") != "query_response":
                continue
            if get_query_event_field(event, "source_step", "") != "entity_fetch":
                continue
            if get_query_event_field(event, "status", "") != "success":
                continue
            payload = get_query_event_response_data(event)
            if not isinstance(payload, dict):
                continue
            entities = payload.get("entities", {})
            if not isinstance(entities, dict):
                continue
            for qid, doc in entities.items():
                qid_norm = canonical_qid(qid)
                if qid_norm and isinstance(doc, dict):
                    self._entity_docs[qid_norm] = doc
            seq = event.get("sequence_num")
            if isinstance(seq, int):
                self._last_seq = max(self._last_seq, seq)

    def materialize(self, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        class_filename = _class_filename_lookup(self.repo_root)
        core_qids = effective_core_class_qids(set(class_filename.keys()))

        def _get_entity(qid: str) -> dict | None:
            qid_norm = canonical_qid(qid)
            if not qid_norm:
                return None
            return self._entity_docs.get(qid_norm)

        rollups: dict[str, dict] = {}
        for qid in sorted(self._entity_docs):
            doc = self._entity_docs[qid]
            resolution = resolve_class_path(doc, core_qids, _get_entity)
            class_id = str(resolution.get("class_id", "") or "")
            if not class_id:
                continue
            row = rollups.get(class_id)
            if row is None:
                meta = self._entity_docs.get(class_id, {})
                row = {
                    "id": class_id,
                    "label_en": _pick_lang_text(meta.get("labels", {}), "en"),
                    "label_de": _pick_lang_text(meta.get("labels", {}), "de"),
                    "description_en": _pick_lang_text(meta.get("descriptions", {}), "en"),
                    "description_de": _pick_lang_text(meta.get("descriptions", {}), "de"),
                    "alias_en": _alias_pipe(meta.get("aliases", {}), "en"),
                    "alias_de": _alias_pipe(meta.get("aliases", {}), "de"),
                    "path_to_core_class": str(resolution.get("path_to_core_class", "") or ""),
                    "subclass_of_core_class": bool(resolution.get("subclass_of_core_class", False)),
                    "discovered_count": 0,
                    "expanded_count": 0,
                    "class_filename": class_filename.get(class_id, ""),
                }
                rollups[class_id] = row
            row["discovered_count"] += 1
            if bool(resolution.get("subclass_of_core_class", False)):
                row["subclass_of_core_class"] = True
            path = str(resolution.get("path_to_core_class", "") or "")
            if path and not row.get("path_to_core_class"):
                row["path_to_core_class"] = path

        columns = [
            "id", "class_filename", "label_en", "label_de", "description_en", "description_de",
            "alias_en", "alias_de", "path_to_core_class", "subclass_of_core_class", "discovered_count", "expanded_count",
        ]
        
        # Write classes.csv (all classes) via atomic write
        if not rollups:
            df = pd.DataFrame(columns=columns)
        else:
            rows = [rollups[qid] for qid in sorted(rollups)]
            df = pd.DataFrame(rows)[columns]
        
        _atomic_write_df(output_path, df)
        
        # Write core_classes.csv (filtered to only core QIDs) via atomic write
        if rollups:
            core_rows = [rollups[qid] for qid in sorted(rollups) if qid in core_qids]
        else:
            core_rows = []
        
        if not core_rows:
            core_df = pd.DataFrame(columns=columns)
        else:
            core_df = pd.DataFrame(core_rows)[columns]
        
        core_classes_path = output_path.with_name("core_classes.csv")
        core_classes_path.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write_df(core_classes_path, core_df)

    def update_progress(self, last_seq: int) -> None:
        self._last_seq = last_seq
        if self.handler_registry:
            self.handler_registry.update_progress(self.name(), last_seq)
