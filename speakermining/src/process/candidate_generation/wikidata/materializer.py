from __future__ import annotations

import json
from pathlib import Path
from time import perf_counter

import pandas as pd

from .cache import _atomic_write_df, _atomic_write_text, _entity_from_payload, _load_raw_record
from .class_resolver import compute_class_rollups, resolve_class_path
from .common import canonical_qid, effective_core_class_qids
from .node_store import iter_items, iter_properties
from .query_inventory import rebuild_query_inventory, to_dataframe
from .schemas import build_artifact_paths
from .triple_store import iter_unique_triples


def _pick_lang_text(mapping: dict, lang: str) -> str:
    if not isinstance(mapping, dict):
        return ""
    node = mapping.get(lang, {})
    return str(node.get("value", "") if isinstance(node, dict) else "")


def _alias_pipe(mapping: dict, lang: str) -> str:
    if not isinstance(mapping, dict):
        return ""
    values = []
    for item in mapping.get(lang, []) or []:
        if isinstance(item, dict) and item.get("value"):
            values.append(str(item.get("value")))
    return "|".join(sorted(set(values)))


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
    path = Path(repo_root) / "data" / "00_setup" / "classes.csv"
    if not path.exists():
        return {}
    try:
        df = pd.read_csv(path)
    except Exception:
        return {}
    lookup: dict[str, str] = {}
    for _, row in df.iterrows():
        qid = canonical_qid(str(row.get("wikidata_id", "") or ""))
        filename = str(row.get("filename", "") or "")
        if qid and filename:
            lookup[qid] = filename
    return lookup


def _latest_entity_cache_paths(repo_root: Path) -> dict[str, Path]:
    """Index latest entity_fetch event file per QID using filename tokens.

    This avoids repeated full raw_queries scans when resolving parent classes.
    """
    raw_dir = Path(repo_root) / "data" / "20_candidate_generation" / "wikidata" / "raw_queries"
    if not raw_dir.exists():
        return {}

    latest: dict[str, tuple[str, Path]] = {}
    for path in raw_dir.glob("*__entity_fetch__*__*.json"):
        parts = path.name.split("__", 3)
        if len(parts) < 4:
            continue
        stamp, source_step, key, _rest = parts
        if source_step != "entity_fetch":
            continue
        qid = canonical_qid(key)
        if not qid:
            continue
        prior = latest.get(qid)
        if prior is None or stamp > prior[0]:
            latest[qid] = (stamp, path)

    return {qid: data[1] for qid, data in latest.items()}


def _build_instances_df(repo_root: Path, core_class_qids: set[str]) -> pd.DataFrame:
    rows = []
    class_filename_lookup = _class_filename_lookup(repo_root)
    parent_doc_cache: dict[str, dict] = {}
    items = list(iter_items(repo_root))
    item_by_id = {
        canonical_qid(str(item.get("id", "") or "")): item
        for item in items
        if canonical_qid(str(item.get("id", "") or ""))
    }
    latest_entity_paths = _latest_entity_cache_paths(repo_root)

    def _get_entity(qid: str) -> dict | None:
        qid_norm = canonical_qid(qid)
        if not qid_norm:
            return None

        node = item_by_id.get(qid_norm)
        if node:
            return node
        if qid_norm in parent_doc_cache:
            return parent_doc_cache[qid_norm]

        path = latest_entity_paths.get(qid_norm)
        if path is None:
            return None

        record = _load_raw_record(path)
        if not record:
            return None

        node_doc = _entity_from_payload(record.get("payload", {}), qid_norm)
        parent_doc_cache[qid_norm] = node_doc if isinstance(node_doc, dict) else {}
        return parent_doc_cache[qid_norm]

    for item in items:
        claims = item.get("claims", {}) if isinstance(item.get("claims"), dict) else {}
        resolution = resolve_class_path(item, core_class_qids, _get_entity)
        class_id = str(resolution.get("class_id", "") or "")
        rows.append(
            {
                "id": item.get("id", ""),
                "class_id": class_id,
                "class_filename": class_filename_lookup.get(class_id, ""),
                "label_en": _pick_lang_text(item.get("labels", {}), "en"),
                "label_de": _pick_lang_text(item.get("labels", {}), "de"),
                "description_en": _pick_lang_text(item.get("descriptions", {}), "en"),
                "description_de": _pick_lang_text(item.get("descriptions", {}), "de"),
                "alias_en": _alias_pipe(item.get("aliases", {}), "en"),
                "alias_de": _alias_pipe(item.get("aliases", {}), "de"),
                "path_to_core_class": str(resolution.get("path_to_core_class", "") or ""),
                "subclass_of_core_class": bool(resolution.get("subclass_of_core_class", False)),
                "discovered_at_utc": item.get("discovered_at_utc", ""),
                "expanded_at_utc": item.get("expanded_at_utc") or "",
            }
        )
    columns = [
        "id", "class_id", "class_filename", "label_en", "label_de", "description_en", "description_de",
        "alias_en", "alias_de", "path_to_core_class", "subclass_of_core_class", "discovered_at_utc", "expanded_at_utc",
    ]
    if not rows:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(rows)[columns].drop_duplicates(subset=["id"]).sort_values("id").reset_index(drop=True)


def _build_classes_df(repo_root: Path, instances_df: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "id", "label_en", "label_de", "description_en", "description_de", "alias_en", "alias_de",
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
        class_meta[qid] = {
            "label_en": _pick_lang_text(item.get("labels", {}), "en"),
            "label_de": _pick_lang_text(item.get("labels", {}), "de"),
            "description_en": _pick_lang_text(item.get("descriptions", {}), "en"),
            "description_de": _pick_lang_text(item.get("descriptions", {}), "de"),
            "alias_en": _alias_pipe(item.get("aliases", {}), "en"),
            "alias_de": _alias_pipe(item.get("aliases", {}), "de"),
        }
    for row in rollup_rows:
        meta = class_meta.get(str(row.get("id", "") or ""), {})
        for key in ["label_en", "label_de", "description_en", "description_de", "alias_en", "alias_de"]:
            if meta.get(key):
                row[key] = meta[key]
    return pd.DataFrame(rollup_rows)[columns].sort_values("id").reset_index(drop=True)


def _build_properties_df(repo_root: Path) -> pd.DataFrame:
    columns = ["id", "label_en", "label_de", "description_en", "description_de", "alias_en", "alias_de"]
    rows = []
    for prop in iter_properties(repo_root):
        rows.append(
            {
                "id": prop.get("id", ""),
                "label_en": _pick_lang_text(prop.get("labels", {}), "en"),
                "label_de": _pick_lang_text(prop.get("labels", {}), "de"),
                "description_en": _pick_lang_text(prop.get("descriptions", {}), "en"),
                "description_de": _pick_lang_text(prop.get("descriptions", {}), "de"),
                "alias_en": _alias_pipe(prop.get("aliases", {}), "en"),
                "alias_de": _alias_pipe(prop.get("aliases", {}), "de"),
            }
        )
    if not rows:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(rows)[columns].drop_duplicates(subset=["id"]).sort_values("id").reset_index(drop=True)


def _build_alias_df(instances_df: pd.DataFrame, lang: str) -> pd.DataFrame:
    column = "alias_en" if lang == "en" else "alias_de"
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
    paths = build_artifact_paths(Path(repo_root))
    class_filename_lookup = _class_filename_lookup(repo_root)
    core_class_qids = effective_core_class_qids(set(class_filename_lookup.keys()))

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
    aliases_en_df = _build_alias_df(instances_df, "en")
    print(f"[materializer] build aliases_en done in {perf_counter() - t0:.2f}s", flush=True)
    t0 = perf_counter()
    aliases_de_df = _build_alias_df(instances_df, "de")
    print(f"[materializer] build aliases_de done in {perf_counter() - t0:.2f}s", flush=True)
    t0 = perf_counter()
    triples_df = _build_triples_df(repo_root)
    print(f"[materializer] build triples done in {perf_counter() - t0:.2f}s", flush=True)
    t0 = perf_counter()
    query_inventory_df = to_dataframe(rebuild_query_inventory(repo_root))
    print(f"[materializer] build query_inventory done in {perf_counter() - t0:.2f}s", flush=True)

    t0 = perf_counter()
    _atomic_write_df(paths.instances_csv, instances_df)
    _atomic_write_df(paths.classes_csv, classes_df)
    _atomic_write_df(paths.properties_csv, properties_df)
    _atomic_write_df(paths.aliases_en_csv, aliases_en_df)
    _atomic_write_df(paths.aliases_de_csv, aliases_de_df)
    _atomic_write_df(paths.triples_csv, triples_df)
    _atomic_write_df(paths.query_inventory_csv, query_inventory_df)
    print(f"[materializer] write csv artifacts done in {perf_counter() - t0:.2f}s", flush=True)

    stats = {
        "seed_id": seed_id,
        "instances_rows": int(len(instances_df)),
        "classes_rows": int(len(classes_df)),
        "properties_rows": int(len(properties_df)),
        "triples_rows": int(len(triples_df)),
        "query_inventory_rows": int(len(query_inventory_df)),
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
