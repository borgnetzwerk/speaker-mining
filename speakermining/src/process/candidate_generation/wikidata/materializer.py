from __future__ import annotations

import json
from pathlib import Path
from time import perf_counter

import pandas as pd

from .cache import _atomic_write_df, _atomic_write_parquet_df, _atomic_write_text, _entity_from_payload
from .bootstrap import load_core_classes, load_other_interesting_classes, load_root_classes
from .class_resolver import compute_class_rollups, resolve_class_path
from .common import (
    DEFAULT_WIKIDATA_FALLBACK_LANGUAGE,
    canonical_qid,
    effective_core_class_qids,
    language_projection_suffix,
    projection_languages,
)
from .event_log import get_query_event_field, get_query_event_response_data, iter_query_events
from .node_store import flush_node_store, iter_items, iter_properties
from .query_inventory import materialize_query_inventory
from .schemas import build_artifact_paths
from .schemas import core_instances_projection_filename
from .triple_store import flush_triple_events, iter_unique_triples


def _pick_lang_text(mapping: dict, lang: str) -> str:
    if not isinstance(mapping, dict):
        return ""

    node = mapping.get(lang, {})
    value = node.get("value", "") if isinstance(node, dict) else ""
    if value:
        return str(value)

    fallback_node = mapping.get(DEFAULT_WIKIDATA_FALLBACK_LANGUAGE, {})
    fallback = fallback_node.get("value", "") if isinstance(fallback_node, dict) else ""
    if fallback:
        return str(fallback)
    return ""


def _alias_pipe(mapping: dict, lang: str) -> str:
    if not isinstance(mapping, dict):
        return ""

    values: set[str] = set()

    for item in mapping.get(lang, []) or []:
        if isinstance(item, dict) and item.get("value"):
            values.add(str(item.get("value")))

    for item in mapping.get(DEFAULT_WIKIDATA_FALLBACK_LANGUAGE, []) or []:
        if isinstance(item, dict) and item.get("value"):
            values.add(str(item.get("value")))

    return "|".join(sorted(values))


def _projection_language_columns() -> tuple[list[str], list[str], list[str]]:
    languages = [language_projection_suffix(lang) for lang in projection_languages()]
    label_columns = [f"label_{lang}" for lang in languages]
    description_columns = [f"description_{lang}" for lang in languages]
    alias_columns = [f"alias_{lang}" for lang in languages]
    return label_columns, description_columns, alias_columns


def _extract_claim_qids(claims: dict, pid: str) -> list[str]:
    out: list[str] = []
    for claim in claims.get(pid, []) or []:
        mainsnak = claim.get("mainsnak", {}) if isinstance(claim, dict) else {}
        value = (mainsnak.get("datavalue", {}) or {}).get("value")
        if isinstance(value, dict) and value.get("entity-type") == "item":
            qid = canonical_qid(value.get("id", ""))
            if qid:
                out.append(qid)
    return sorted(set(out))


def _class_filename_lookup(repo_root: Path) -> dict[str, str]:
    lookup: dict[str, str] = {}
    setup_rows = load_core_classes(repo_root) + load_root_classes(repo_root) + load_other_interesting_classes(repo_root)
    for row in setup_rows:
        qid = canonical_qid(str(row.get("wikidata_id", "") or ""))
        filename = str(row.get("filename", "") or "")
        if qid and filename:
            lookup[qid] = filename
    return lookup


def _core_class_qids(repo_root: Path) -> set[str]:
    return effective_core_class_qids(
        {
            canonical_qid(str(row.get("wikidata_id", "") or ""))
            for row in load_core_classes(repo_root)
            if canonical_qid(str(row.get("wikidata_id", "") or ""))
        }
    )


def _root_class_qids(repo_root: Path) -> set[str]:
    return {
        canonical_qid(str(row.get("wikidata_id", "") or ""))
        for row in load_root_classes(repo_root)
        if canonical_qid(str(row.get("wikidata_id", "") or ""))
    }


def _latest_entity_cache_docs(repo_root: Path) -> dict[str, dict]:
    """Index latest entity_fetch payload per QID from v3 query_response events."""
    latest: dict[str, tuple[int, dict]] = {}
    for event in iter_query_events(repo_root) or []:
        if get_query_event_field(event, "source_step", "") != "entity_fetch":
            continue
        qid = canonical_qid(str(get_query_event_field(event, "key", "") or ""))
        if not qid:
            continue
        seq = event.get("sequence_num")
        if not isinstance(seq, int):
            continue
        payload = get_query_event_response_data(event)
        if not isinstance(payload, dict):
            continue
        prior = latest.get(qid)
        if prior is None or seq > prior[0]:
            latest[qid] = (seq, payload)

    docs: dict[str, dict] = {}
    for qid, (_seq, payload) in latest.items():
        node_doc = _entity_from_payload(payload, qid)
        if isinstance(node_doc, dict) and node_doc:
            docs[qid] = node_doc
    return docs


def _build_instances_df(repo_root: Path, core_class_qids: set[str]) -> pd.DataFrame:
    rows = []
    label_columns, description_columns, alias_columns = _projection_language_columns()
    languages = [column.replace("label_", "", 1) for column in label_columns]
    class_filename_lookup = _class_filename_lookup(repo_root)
    parent_doc_cache: dict[str, dict] = {}
    items = list(iter_items(repo_root))
    item_by_id = {
        canonical_qid(str(item.get("id", "") or "")): item
        for item in items
        if canonical_qid(str(item.get("id", "") or ""))
    }
    latest_entity_docs = _latest_entity_cache_docs(repo_root)

    def _get_entity(qid: str) -> dict | None:
        qid_norm = canonical_qid(qid)
        if not qid_norm:
            return None

        node = item_by_id.get(qid_norm)
        if node:
            return node
        if qid_norm in parent_doc_cache:
            return parent_doc_cache[qid_norm]

        node_doc = latest_entity_docs.get(qid_norm)
        if node_doc is None:
            return None
        parent_doc_cache[qid_norm] = node_doc if isinstance(node_doc, dict) else {}
        return parent_doc_cache[qid_norm]

    for item in items:
        claims = item.get("claims", {}) if isinstance(item.get("claims"), dict) else {}
        resolution = resolve_class_path(item, core_class_qids, _get_entity)
        class_id = str(resolution.get("class_id", "") or "")
        row = {
            "id": item.get("id", ""),
            "class_id": class_id,
            "class_filename": class_filename_lookup.get(class_id, ""),
            "path_to_core_class": str(resolution.get("path_to_core_class", "") or ""),
            "subclass_of_core_class": bool(resolution.get("subclass_of_core_class", False)),
            "discovered_at_utc": item.get("discovered_at_utc", ""),
            "expanded_at_utc": item.get("expanded_at_utc") or "",
        }
        for lang in languages:
            row[f"label_{lang}"] = _pick_lang_text(item.get("labels", {}), lang)
            row[f"description_{lang}"] = _pick_lang_text(item.get("descriptions", {}), lang)
            row[f"alias_{lang}"] = _alias_pipe(item.get("aliases", {}), lang)
        rows.append(row)
    columns = [
        "id", "class_id", "class_filename",
        *label_columns,
        *description_columns,
        *alias_columns,
        "path_to_core_class", "subclass_of_core_class", "discovered_at_utc", "expanded_at_utc",
    ]
    if not rows:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(rows)[columns].drop_duplicates(subset=["id"]).sort_values("id").reset_index(drop=True)


def _build_classes_df(repo_root: Path, instances_df: pd.DataFrame) -> pd.DataFrame:
    label_columns, description_columns, alias_columns = _projection_language_columns()
    languages = [column.replace("label_", "", 1) for column in label_columns]
    columns = [
        "id", *label_columns, *description_columns, *alias_columns,
        "path_to_core_class", "subclass_of_core_class", "discovered_count", "expanded_count",
    ]
    if instances_df.empty:
        return pd.DataFrame(columns=columns)

    rollup_rows = compute_class_rollups(instances_df.to_dict(orient="records"))
    class_meta: dict[str, dict[str, str]] = {}
    for item in iter_items(repo_root):
        qid = str(item.get("id", "") or "")
        if not qid:
            continue
        meta = {}
        for lang in languages:
            meta[f"label_{lang}"] = _pick_lang_text(item.get("labels", {}), lang)
            meta[f"description_{lang}"] = _pick_lang_text(item.get("descriptions", {}), lang)
            meta[f"alias_{lang}"] = _alias_pipe(item.get("aliases", {}), lang)
        class_meta[qid] = meta
    for row in rollup_rows:
        meta = class_meta.get(str(row.get("id", "") or ""), {})
        for key in [*label_columns, *description_columns, *alias_columns]:
            if meta.get(key):
                row[key] = meta[key]
    return pd.DataFrame(rollup_rows)[columns].sort_values("id").reset_index(drop=True)


def _build_properties_df(repo_root: Path) -> pd.DataFrame:
    label_columns, description_columns, alias_columns = _projection_language_columns()
    languages = [column.replace("label_", "", 1) for column in label_columns]
    columns = ["id", *label_columns, *description_columns, *alias_columns]
    rows = []
    for prop in iter_properties(repo_root):
        row = {
            "id": prop.get("id", ""),
        }
        for lang in languages:
            row[f"label_{lang}"] = _pick_lang_text(prop.get("labels", {}), lang)
            row[f"description_{lang}"] = _pick_lang_text(prop.get("descriptions", {}), lang)
            row[f"alias_{lang}"] = _alias_pipe(prop.get("aliases", {}), lang)
        rows.append(row)
    if not rows:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(rows)[columns].drop_duplicates(subset=["id"]).sort_values("id").reset_index(drop=True)


def _build_alias_df(instances_df: pd.DataFrame, lang: str) -> pd.DataFrame:
    column = f"alias_{language_projection_suffix(lang)}"
    rows = []
    for _, row in instances_df.iterrows():
        qid = str(row.get("id", ""))
        for alias in str(row.get(column, "")).split("|"):
            alias = alias.strip()
            if alias:
                rows.append({"alias": alias, "qid": qid})
    if not rows:
        return pd.DataFrame(columns=["alias", "qid"])
    return pd.DataFrame(rows).drop_duplicates(subset=["alias", "qid"]).sort_values(["alias", "qid"]).reset_index(drop=True)


def _remove_stale_alias_projections(paths, active_alias_files: set[str]) -> None:
    for alias_path in paths.projections_dir.glob("aliases_*.csv"):
        if alias_path.name not in active_alias_files and alias_path.is_file():
            alias_path.unlink()
        alias_parquet = alias_path.with_suffix(".parquet")
        if alias_path.name not in active_alias_files and alias_parquet.is_file():
            alias_parquet.unlink()


def _build_triples_df(repo_root: Path) -> pd.DataFrame:
    columns = ["subject", "predicate", "object", "discovered_at_utc", "source_query_file"]
    rows = list(iter_unique_triples(repo_root))
    if not rows:
        return pd.DataFrame(columns=columns)
    df = pd.DataFrame(rows)
    for col in columns:
        if col not in df.columns:
            df[col] = ""
    return df[columns].sort_values(["subject", "predicate", "object"]).reset_index(drop=True)


def _build_class_hierarchy_df(repo_root: Path, core_class_qids: set[str], root_class_qids: set[str]) -> pd.DataFrame:
    columns = [
        "class_id",
        "class_filename",
        "path_to_core_class",
        "subclass_of_core_class",
        "is_core_class",
        "is_root_class",
        "parent_count",
        "parent_qids",
    ]
    class_filename_lookup = _class_filename_lookup(repo_root)
    items = list(iter_items(repo_root))
    item_by_id = {
        canonical_qid(str(item.get("id", "") or "")): item
        for item in items
        if canonical_qid(str(item.get("id", "") or ""))
    }
    latest_entity_docs = _latest_entity_cache_docs(repo_root)

    def _get_entity(qid: str) -> dict | None:
        qid_norm = canonical_qid(qid)
        if not qid_norm:
            return None
        node = item_by_id.get(qid_norm)
        if node:
            return node
        node_doc = latest_entity_docs.get(qid_norm)
        if isinstance(node_doc, dict):
            return node_doc
        return None

    candidate_class_qids: set[str] = set()
    for item in items:
        qid = canonical_qid(str(item.get("id", "") or ""))
        if not qid:
            continue
        claims = item.get("claims", {}) if isinstance(item.get("claims"), dict) else {}
        p31 = _extract_claim_qids(claims, "P31")
        p279 = _extract_claim_qids(claims, "P279")
        if p279:
            candidate_class_qids.add(qid)
        candidate_class_qids.update(p31)
        candidate_class_qids.update(p279)

    rows: list[dict] = []
    for class_qid in sorted(candidate_class_qids):
        class_doc = _get_entity(class_qid) or {}
        claims = class_doc.get("claims", {}) if isinstance(class_doc.get("claims"), dict) else {}
        parent_qids = _extract_claim_qids(claims, "P279")
        resolution = resolve_class_path(class_doc, core_class_qids, _get_entity) if class_doc else {
            "path_to_core_class": "",
            "subclass_of_core_class": False,
        }
        rows.append(
            {
                "class_id": class_qid,
                "class_filename": class_filename_lookup.get(class_qid, ""),
                "path_to_core_class": str(resolution.get("path_to_core_class", "") or ""),
                "subclass_of_core_class": bool(resolution.get("subclass_of_core_class", False)),
                "is_core_class": bool(class_qid in core_class_qids),
                "is_root_class": bool(class_qid in root_class_qids),
                "parent_count": int(len(parent_qids)),
                "parent_qids": "|".join(parent_qids),
            }
        )

    if not rows:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(rows)[columns].sort_values(["is_core_class", "subclass_of_core_class", "class_id"], ascending=[False, False, True]).reset_index(drop=True)


def _resolve_row_core_class_id(row: pd.Series, core_class_qids: set[str]) -> str:
    path = str(row.get("path_to_core_class", "") or "")
    if path:
        tokens = [canonical_qid(token) for token in path.split("|") if canonical_qid(token)]
        for token in reversed(tokens):
            if token in core_class_qids:
                return token
    class_id = canonical_qid(str(row.get("class_id", "") or ""))
    if class_id in core_class_qids and bool(row.get("subclass_of_core_class", False)):
        return class_id
    return ""


def _remove_stale_core_instance_projections(paths, active_projection_files: set[str]) -> None:
    for projection_path in paths.projections_dir.glob("instances_core_*.csv"):
        if projection_path.name not in active_projection_files and projection_path.is_file():
            projection_path.unlink()
        projection_parquet = projection_path.with_suffix(".parquet")
        if projection_path.name not in active_projection_files and projection_parquet.is_file():
            projection_parquet.unlink()


def _write_tabular_artifact(csv_path: Path, df: pd.DataFrame) -> None:
    _atomic_write_df(csv_path, df)
    _atomic_write_parquet_df(csv_path.with_suffix(".parquet"), df)


def _write_core_instance_projections(paths, instances_df: pd.DataFrame, class_hierarchy_df: pd.DataFrame, repo_root: Path, core_class_qids: set[str]) -> dict[str, int]:
    projection_row_counts: dict[str, int] = {}
    if instances_df.empty:
        _write_tabular_artifact(paths.instances_leftovers_csv, instances_df)
        _remove_stale_core_instance_projections(paths, set())
        return projection_row_counts

    class_node_ids: set[str] = set()
    if not class_hierarchy_df.empty and "class_id" in class_hierarchy_df.columns:
        class_node_ids = {
            canonical_qid(class_id)
            for class_id in class_hierarchy_df["class_id"].tolist()
            if canonical_qid(class_id)
        }

    non_class_instances_df = instances_df[~instances_df["id"].isin(class_node_ids)].copy()
    if non_class_instances_df.empty:
        _write_tabular_artifact(paths.instances_leftovers_csv, non_class_instances_df)
        _remove_stale_core_instance_projections(paths, set())
        return projection_row_counts

    non_class_instances_df["resolved_core_class_id"] = non_class_instances_df.apply(
        lambda row: _resolve_row_core_class_id(row, core_class_qids), axis=1
    )

    core_rows = load_core_classes(repo_root)
    active_projection_files: set[str] = set()
    for row in core_rows:
        class_filename = str(row.get("filename", "") or "")
        core_qid = canonical_qid(str(row.get("wikidata_id", "") or ""))
        if not class_filename or not core_qid:
            continue
        projection_name = core_instances_projection_filename(class_filename)
        projection_path = paths.projections_dir / projection_name
        active_projection_files.add(projection_name)
        core_projection_df = non_class_instances_df[non_class_instances_df["resolved_core_class_id"] == core_qid].copy()
        if "resolved_core_class_id" in core_projection_df.columns:
            core_projection_df = core_projection_df.drop(columns=["resolved_core_class_id"])
        core_projection_df = core_projection_df.sort_values("id").reset_index(drop=True)
        _write_tabular_artifact(projection_path, core_projection_df)
        projection_row_counts[projection_name] = int(len(core_projection_df))

    leftovers_df = non_class_instances_df[non_class_instances_df["resolved_core_class_id"] == ""].copy()
    if "resolved_core_class_id" in leftovers_df.columns:
        leftovers_df = leftovers_df.drop(columns=["resolved_core_class_id"])
    leftovers_df = leftovers_df.sort_values("id").reset_index(drop=True)
    _write_tabular_artifact(paths.instances_leftovers_csv, leftovers_df)
    projection_row_counts[paths.instances_leftovers_csv.name] = int(len(leftovers_df))

    _remove_stale_core_instance_projections(paths, active_projection_files)
    return projection_row_counts


def _write_summary(paths, run_id: str, stage: str, stats: dict) -> None:
    summary = {
        "run_id": run_id,
        "stage": stage,
        **stats,
    }
    _atomic_write_text(paths.summary_json, json.dumps(summary, ensure_ascii=False, indent=2))


def _materialize(repo_root: Path, *, run_id: str, stage: str, seed_id: str | None) -> dict:
    total_t0 = perf_counter()
    print(f"[materializer] Start stage={stage} run_id={run_id}", flush=True)
    flush_node_store(repo_root)
    flush_triple_events(repo_root)
    paths = build_artifact_paths(Path(repo_root))
    core_class_qids = _core_class_qids(repo_root)
    root_class_qids = _root_class_qids(repo_root)

    t0 = perf_counter()
    instances_df = _build_instances_df(repo_root, core_class_qids)
    print(f"[materializer] build instances done in {perf_counter() - t0:.2f}s", flush=True)
    t0 = perf_counter()
    classes_df = _build_classes_df(repo_root, instances_df)
    print(f"[materializer] build classes done in {perf_counter() - t0:.2f}s", flush=True)
    t0 = perf_counter()
    properties_df = _build_properties_df(repo_root)
    print(f"[materializer] build properties done in {perf_counter() - t0:.2f}s", flush=True)
    t0 = perf_counter()
    alias_dfs: dict[str, pd.DataFrame] = {}
    for lang in projection_languages():
        alias_dfs[lang] = _build_alias_df(instances_df, lang)
    print(f"[materializer] build aliases done in {perf_counter() - t0:.2f}s", flush=True)
    t0 = perf_counter()
    triples_df = _build_triples_df(repo_root)
    print(f"[materializer] build triples done in {perf_counter() - t0:.2f}s", flush=True)
    t0 = perf_counter()
    class_hierarchy_df = _build_class_hierarchy_df(repo_root, core_class_qids, root_class_qids)
    print(f"[materializer] build class_hierarchy done in {perf_counter() - t0:.2f}s", flush=True)
    t0 = perf_counter()
    query_inventory_df = materialize_query_inventory(repo_root)
    print(f"[materializer] build query_inventory done in {perf_counter() - t0:.2f}s", flush=True)

    t0 = perf_counter()
    active_alias_files: set[str] = set()
    for lang, alias_df in alias_dfs.items():
        suffix = language_projection_suffix(lang)
        alias_filename = f"aliases_{suffix}.csv"
        alias_path = paths.projections_dir / alias_filename
        _write_tabular_artifact(alias_path, alias_df)
        active_alias_files.add(alias_filename)
    _remove_stale_alias_projections(paths, active_alias_files)
    _write_tabular_artifact(paths.triples_csv, triples_df)
    _write_tabular_artifact(paths.class_hierarchy_csv, class_hierarchy_df)
    _write_tabular_artifact(paths.query_inventory_csv, query_inventory_df)
    _write_tabular_artifact(paths.instances_csv, instances_df)
    _write_tabular_artifact(paths.classes_csv, classes_df)
    _write_tabular_artifact(paths.properties_csv, properties_df)
    core_projection_counts = _write_core_instance_projections(
        paths,
        instances_df,
        class_hierarchy_df,
        repo_root,
        core_class_qids,
    )
    print(f"[materializer] write tabular artifacts done in {perf_counter() - t0:.2f}s", flush=True)

    stats = {
        "seed_id": seed_id,
        "instances_rows": int(len(instances_df)),
        "classes_rows": int(len(classes_df)),
        "properties_rows": int(len(properties_df)),
        "triples_rows": int(len(triples_df)),
        "query_inventory_rows": int(len(query_inventory_df)),
        "core_instance_projection_files": int(len(core_projection_counts)),
        "instances_leftovers_rows": int(core_projection_counts.get(paths.instances_leftovers_csv.name, 0)),
    }
    _write_summary(paths, run_id, stage, stats)
    elapsed = perf_counter() - total_t0
    print(f"[materializer] Completed stage={stage} in {elapsed:.2f}s", flush=True)
    if elapsed > 20.0:
        print(
            f"[materializer][warning] Stage {stage} exceeded 20s target ({elapsed:.2f}s)",
            flush=True,
        )
    return stats


def materialize_checkpoint(repo_root: Path, *, run_id: str, checkpoint_ts: str, seed_id: str | None) -> dict:
    return _materialize(repo_root, run_id=run_id, stage=f"checkpoint:{checkpoint_ts}", seed_id=seed_id)


def materialize_final(repo_root: Path, *, run_id: str) -> dict:
    return _materialize(repo_root, run_id=run_id, stage="final", seed_id=None)
