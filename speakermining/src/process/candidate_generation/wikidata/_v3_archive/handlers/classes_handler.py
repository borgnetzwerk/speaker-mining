"""ClassesHandler: derives class projection from class-resolution events."""

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
from process.candidate_generation.wikidata.node_store import iter_items


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
        self._rollups: dict[str, dict] = {}

    def name(self) -> str:
        return "ClassesHandler"

    def requires_materialize_without_pending(self) -> bool:
        """Keep classes projection in sync with node-store-derived lineage state.

        `classes.csv` can change due to local node-store hydration even when no
        new domain events are pending for this handler in the current run.
        """
        return True

    def last_processed_sequence(self) -> int:
        if self.handler_registry:
            return self.handler_registry.get_progress(self.name())
        return self._last_seq

    def bootstrap_from_projection(self, _output_path: Path) -> bool:
        """Hydrate rollups from the existing projection and refresh metadata from node store."""
        output_path = Path(_output_path)

        hydrated_rollups: dict[str, dict] = {}
        if output_path.exists() and output_path.stat().st_size > 0:
            try:
                df = pd.read_csv(output_path)
            except Exception:
                return False
            if not df.empty:
                df = df.fillna("")
                for row in df.to_dict(orient="records"):
                    class_id = canonical_qid(str(row.get("id", "") or ""))
                    if not class_id:
                        continue
                    hydrated_rollups[class_id] = {
                        "id": class_id,
                        "label_en": str(row.get("label_en", "") or ""),
                        "label_de": str(row.get("label_de", "") or ""),
                        "description_en": str(row.get("description_en", "") or ""),
                        "description_de": str(row.get("description_de", "") or ""),
                        "alias_en": str(row.get("alias_en", "") or ""),
                        "alias_de": str(row.get("alias_de", "") or ""),
                        "path_to_core_class": str(row.get("path_to_core_class", "") or ""),
                        "subclass_of_core_class": bool(row.get("subclass_of_core_class", False)),
                        "discovered_count": int(row.get("discovered_count", 0) or 0),
                        "expanded_count": int(row.get("expanded_count", 0) or 0),
                        "class_filename": str(row.get("class_filename", "") or ""),
                    }

        hydrated: dict[str, dict] = {}
        for item in iter_items(self.repo_root):
            qid = canonical_qid(str(item.get("id", "") or ""))
            if not qid or not isinstance(item, dict):
                continue
            hydrated[qid] = item
        self._entity_docs = hydrated
        self._rollups = hydrated_rollups
        return bool(hydrated_rollups)

    def _row_for_class_id(self, class_id: str) -> dict:
        class_id = canonical_qid(class_id)
        if not class_id:
            return {}

        class_filename = _class_filename_lookup(self.repo_root)
        row = self._rollups.get(class_id)
        if row is None:
            row = {
                "id": class_id,
                "label_en": "",
                "label_de": "",
                "description_en": "",
                "description_de": "",
                "alias_en": "",
                "alias_de": "",
                "path_to_core_class": "",
                "subclass_of_core_class": False,
                "discovered_count": 0,
                "expanded_count": 0,
                "class_filename": class_filename.get(class_id, ""),
            }
            self._rollups[class_id] = row
        elif not row.get("class_filename"):
            row["class_filename"] = class_filename.get(class_id, "")
        return row

    def _refresh_row_metadata(self, row: dict, class_id: str) -> None:
        meta = self._entity_docs.get(class_id, {})
        if not isinstance(meta, dict):
            meta = {}
        if not row.get("label_en"):
            row["label_en"] = _pick_lang_text(meta.get("labels", {}), "en")
        if not row.get("label_de"):
            row["label_de"] = _pick_lang_text(meta.get("labels", {}), "de")
        if not row.get("description_en"):
            row["description_en"] = _pick_lang_text(meta.get("descriptions", {}), "en")
        if not row.get("description_de"):
            row["description_de"] = _pick_lang_text(meta.get("descriptions", {}), "de")
        if not row.get("alias_en"):
            row["alias_en"] = _alias_pipe(meta.get("aliases", {}), "en")
        if not row.get("alias_de"):
            row["alias_de"] = _alias_pipe(meta.get("aliases", {}), "de")

    def process_batch(self, events: list[dict]) -> None:
        for event in events:
            seq = event.get("sequence_num")
            if isinstance(seq, int):
                self._last_seq = max(self._last_seq, seq)
            if event.get("event_type") == "query_response":
                if get_query_event_field(event, "source_step", "") != "entity_fetch":
                    continue
                if get_query_event_field(event, "status", "") != "success":
                    continue
                response_data = get_query_event_response_data(event)
                if not isinstance(response_data, dict):
                    continue
                entities = response_data.get("entities", {})
                if not isinstance(entities, dict):
                    continue
                for qid, doc in entities.items():
                    qid_norm = canonical_qid(qid)
                    if qid_norm and isinstance(doc, dict):
                        self._entity_docs[qid_norm] = doc
                continue
            if event.get("event_type") != "class_membership_resolved":
                continue

            payload = event.get("payload", {}) if isinstance(event.get("payload"), dict) else {}
            class_id = canonical_qid(str(payload.get("class_id", "") or ""))
            if not class_id:
                continue

            row = self._row_for_class_id(class_id)
            if not row:
                continue

            row["discovered_count"] = int(row.get("discovered_count", 0) or 0) + 1
            if bool(payload.get("subclass_of_core_class", False)):
                row["subclass_of_core_class"] = True
            path = str(payload.get("path_to_core_class", "") or "")
            if path and not row.get("path_to_core_class"):
                row["path_to_core_class"] = path

            if str(payload.get("is_class_node", "") or ""):
                row["expanded_count"] = int(row.get("expanded_count", 0) or 0) + 1

    def materialize(self, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        class_filename = _class_filename_lookup(self.repo_root)
        core_qids = effective_core_class_qids(set(class_filename.keys()))
        rollups: dict[str, dict] = {qid: dict(row) for qid, row in self._rollups.items()}

        for qid, row in rollups.items():
            row["class_filename"] = row.get("class_filename") or class_filename.get(qid, "")
            self._refresh_row_metadata(row, qid)

        def _get_entity(qid: str) -> dict | None:
            qid_norm = canonical_qid(qid)
            if not qid_norm:
                return None
            return self._entity_docs.get(qid_norm)

        for qid in sorted(self._entity_docs):
            if qid in core_qids:
                continue
            doc = self._entity_docs[qid]
            resolution = resolve_class_path(doc, core_qids, _get_entity)
            class_id = canonical_qid(str(resolution.get("class_id", "") or ""))
            if not class_id:
                continue
            row = rollups.get(class_id)
            if row is None:
                row = self._row_for_class_id(class_id)
                row = rollups.setdefault(class_id, dict(row))
            if not row.get("path_to_core_class"):
                row["path_to_core_class"] = str(resolution.get("path_to_core_class", "") or "")
            if bool(resolution.get("subclass_of_core_class", False)):
                row["subclass_of_core_class"] = True
            if row.get("class_filename", "") == "":
                row["class_filename"] = class_filename.get(class_id, "")
            self._refresh_row_metadata(row, class_id)

        columns = [
            "id", "class_filename", "label_en", "label_de", "description_en", "description_de",
            "alias_en", "alias_de", "path_to_core_class", "subclass_of_core_class", "discovered_count", "expanded_count",
        ]
        
        if not rollups:
            df = pd.DataFrame(columns=columns)
        else:
            rows = [rollups[qid] for qid in sorted(rollups)]
            df = pd.DataFrame(rows)[columns]
        
        _atomic_write_df(output_path, df)

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
