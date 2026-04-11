from __future__ import annotations

import json
from pathlib import Path
from collections import Counter

import pandas as pd

from .bootstrap import load_core_classes
from .common import canonical_qid
from .node_store import iter_items

def _core_lookup(repo_root: Path) -> tuple[dict[str, str], dict[str, int]]:
    core_rows = load_core_classes(repo_root)
    qid_to_name: dict[str, str] = {}
    precedence: dict[str, int] = {}

    for idx, row in enumerate(core_rows):
        qid = canonical_qid(str(row.get("wikidata_id", "") or ""))
        name = str(row.get("filename", "") or "")
        if not qid:
            continue
        if qid not in qid_to_name:
            qid_to_name[qid] = name or qid
        if qid not in precedence:
            precedence[qid] = idx

    return qid_to_name, precedence


def _resolve_preferred_language(label_language_preference: str | list[str] | tuple[str, ...] | None) -> str:
    if isinstance(label_language_preference, str):
        lang = label_language_preference.strip().lower()
        return lang or "en"
    if isinstance(label_language_preference, (list, tuple)):
        for value in label_language_preference:
            lang = str(value or "").strip().lower()
            if lang:
                return lang
    return "en"


def _format_qid(qid: str, qid_labels: dict[str, str]) -> str:
    qid_norm = canonical_qid(qid)
    if not qid_norm:
        return ""
    label = str(qid_labels.get(qid_norm, "") or "").strip()
    if not label:
        label = qid_norm
    return f"{label} ({qid_norm})"


def _format_qid_pipe(qids: list[str], qid_labels: dict[str, str]) -> str:
    return "|".join(_format_qid(q, qid_labels) for q in qids if canonical_qid(q))


def _load_qid_labels(repo_root: Path, preferred_language: str) -> dict[str, str]:
    """Load best-effort QID labels from local projections (cache-first, no network)."""
    labels: dict[str, str] = {}
    classes_csv = repo_root / "data" / "20_candidate_generation" / "wikidata" / "projections" / "classes.csv"
    if not classes_csv.exists():
        return labels

    try:
        classes_df = pd.read_csv(classes_csv)
    except Exception:
        return labels

    if "id" not in classes_df.columns:
        return labels

    preferred_column = f"label_{preferred_language}"
    label_columns: list[str] = []
    if preferred_column in classes_df.columns:
        label_columns.append(preferred_column)
    if "label_en" in classes_df.columns and "label_en" not in label_columns:
        label_columns.append("label_en")
    if "label_de" in classes_df.columns and "label_de" not in label_columns:
        label_columns.append("label_de")
    for row in classes_df.to_dict("records"):
        qid = canonical_qid(str(row.get("id", "") or ""))
        if not qid:
            continue
        label_value = ""
        for col in label_columns:
            value = str(row.get(col, "") or "").strip()
            if value:
                label_value = value
                break
        if label_value:
            labels[qid] = label_value

    # Fill remaining labels from local node store cache when available.
    for item in iter_items(repo_root):
        qid = canonical_qid(str(item.get("id", "") or ""))
        if not qid or qid in labels:
            continue
        labels_dict = item.get("labels", {}) if isinstance(item.get("labels"), dict) else {}
        for lang in (preferred_language, "en", "de"):
            candidate = labels_dict.get(lang, {}) if isinstance(labels_dict.get(lang), dict) else {}
            value = str(candidate.get("value", "") or "").strip()
            if value:
                labels[qid] = value
                break
    return labels


def _parse_candidate_paths(raw_value: object) -> list[dict]:
    if isinstance(raw_value, list):
        return [row for row in raw_value if isinstance(row, dict)]
    raw_text = str(raw_value or "").strip()
    if not raw_text:
        return []
    try:
        parsed = json.loads(raw_text)
    except Exception:
        return []
    if isinstance(parsed, list):
        return [row for row in parsed if isinstance(row, dict)]
    return []


def _canonical_qid_set_from_pipe(raw_value: object) -> set[str]:
    raw_text = str(raw_value or "")
    out: set[str] = set()
    for token in raw_text.split("|"):
        qid = canonical_qid(token)
        if qid:
            out.add(qid)
    return out


def _format_qid_list(qids: list[str], qid_to_name: dict[str, str]) -> str:
    return "|".join(qid_to_name.get(q, q) for q in qids)


def _align_tokens(paths: list[list[str]]) -> tuple[list[str], int, int]:
    """Return common prefix tokens and common suffix lengths for a list of paths."""
    if not paths:
        return [], 0, 0

    min_len = min(len(path) for path in paths)
    prefix_len = 0
    for idx in range(min_len):
        token = paths[0][idx]
        if all(path[idx] == token for path in paths):
            prefix_len += 1
        else:
            break

    suffix_len = 0
    for offset in range(1, min_len + 1):
        token = paths[0][-offset]
        if all(path[-offset] == token for path in paths):
            suffix_len += 1
        else:
            break

    return paths[0][:prefix_len], prefix_len, suffix_len


def _candidate_depth_signature(candidate_paths: list[dict], candidate_qids: list[str]) -> str:
    min_depth_by_core: dict[str, int] = {}
    for entry in candidate_paths:
        core_qid = canonical_qid(str(entry.get("core_class_id", "") or ""))
        if not core_qid:
            continue
        try:
            depth = int(entry.get("depth"))
        except Exception:
            path = [canonical_qid(str(x or "")) for x in (entry.get("path") or [])]
            path = [x for x in path if x]
            depth = max(0, len(path) - 1)
        current = min_depth_by_core.get(core_qid)
        if current is None or depth < current:
            min_depth_by_core[core_qid] = depth

    tokens: list[str] = []
    for qid in candidate_qids:
        depth_value = min_depth_by_core.get(qid)
        if depth_value is None:
            tokens.append(f"{qid}:na")
        else:
            tokens.append(f"{qid}:{depth_value}")
    return "|".join(tokens)


def _candidate_depth_signature_display(signature: str, qid_labels: dict[str, str]) -> str:
    out: list[str] = []
    for token in str(signature or "").split("|"):
        token = token.strip()
        if not token:
            continue
        if ":" not in token:
            qid = canonical_qid(token)
            if qid:
                out.append(_format_qid(qid, qid_labels))
            continue
        qid_part, depth_part = token.split(":", 1)
        qid = canonical_qid(qid_part)
        if not qid:
            continue
        out.append(f"{_format_qid(qid, qid_labels)}:{depth_part}")
    return "|".join(out)


def _series_mode(values: list[str]) -> str:
    non_empty = [str(v) for v in values if str(v)]
    if not non_empty:
        return ""
    return Counter(non_empty).most_common(1)[0][0]


def _annotate_conflicts(
    conflicts_df: pd.DataFrame,
    qid_to_name: dict[str, str],
    precedence: dict[str, int],
    qid_labels: dict[str, str],
) -> pd.DataFrame:
    rows: list[dict] = []
    for row in conflicts_df.to_dict("records"):
        class_id = canonical_qid(str(row.get("class_id", "") or ""))
        resolved_core_qid = canonical_qid(str(row.get("resolved_core_class_id", "") or ""))
        candidate_qids = sorted(_canonical_qid_set_from_pipe(row.get("candidate_core_class_ids", "")))
        candidate_paths = _parse_candidate_paths(row.get("candidate_paths_json", "[]"))

        best_path: list[str] = []
        best_depth = None
        depth_by_core: dict[str, int] = {}
        all_paths_for_alignment: list[list[str]] = []
        for candidate in candidate_paths:
            candidate_core = canonical_qid(str(candidate.get("core_class_id", "") or ""))
            path = [canonical_qid(str(x or "")) for x in (candidate.get("path") or [])]
            path = [x for x in path if x]
            if path:
                all_paths_for_alignment.append(path)
            depth_val = candidate.get("depth")
            try:
                depth_int = int(depth_val)
            except Exception:
                depth_int = len(path) - 1 if path else None
            if depth_int is not None and candidate_core:
                current_depth = depth_by_core.get(candidate_core)
                if current_depth is None or depth_int < current_depth:
                    depth_by_core[candidate_core] = depth_int
            if candidate_core != resolved_core_qid:
                continue
            if best_depth is None or (depth_int is not None and depth_int < best_depth):
                best_depth = depth_int
                best_path = path

        ranked_candidates: list[tuple[str, int | None, int]] = []
        for qid in candidate_qids:
            depth = depth_by_core.get(qid)
            ranked_candidates.append((qid, depth, int(precedence.get(qid, 10_000))))
        ranked_candidates = sorted(
            ranked_candidates,
            key=lambda x: (
                10_000 if x[1] is None else int(x[1]),
                x[2],
                x[0],
            ),
        )

        winner_depth = ranked_candidates[0][1] if ranked_candidates else None
        winner_precedence = ranked_candidates[0][2] if ranked_candidates else 10_000
        runner_up_depth = ranked_candidates[1][1] if len(ranked_candidates) > 1 else None
        runner_up_precedence = ranked_candidates[1][2] if len(ranked_candidates) > 1 else None

        depth_margin = pd.NA
        precedence_margin = pd.NA
        if winner_depth is not None and runner_up_depth is not None:
            depth_margin = int(runner_up_depth - winner_depth)
        if runner_up_precedence is not None:
            precedence_margin = int(runner_up_precedence - winner_precedence)

        if len(ranked_candidates) <= 1:
            decision_mode = "single_candidate"
            decision_confidence = "high"
        elif winner_depth is None or runner_up_depth is None:
            decision_mode = "incomplete_depth_data"
            decision_confidence = "low"
        elif winner_depth < runner_up_depth:
            decision_mode = "depth_advantage"
            decision_confidence = "high"
        else:
            decision_mode = "precedence_tiebreak"
            decision_confidence = "medium"

        prefix_tokens, prefix_len, suffix_len = _align_tokens(all_paths_for_alignment)
        candidate_signature = "|".join(candidate_qids)
        depth_signature = _candidate_depth_signature(candidate_paths, candidate_qids)
        branch_span = max(0, (len(best_path) - prefix_len - suffix_len)) if best_path else 0
        pattern_key = "::".join(
            [
                candidate_signature,
                depth_signature,
                resolved_core_qid,
            ]
        )
        coarse_pattern_key = "::".join([candidate_signature, resolved_core_qid])

        rows.append(
            {
                "class_id": class_id,
                "class_label": qid_labels.get(class_id, class_id),
                "class_display": _format_qid(class_id, qid_labels),
                "resolved_core_class_id": resolved_core_qid,
                "resolved_core_class": qid_to_name.get(resolved_core_qid, resolved_core_qid),
                "resolved_core_label": qid_labels.get(resolved_core_qid, qid_to_name.get(resolved_core_qid, resolved_core_qid)),
                "resolved_core_display": _format_qid(resolved_core_qid, qid_labels),
                "resolution_depth": row.get("resolution_depth", pd.NA),
                "resolution_reason": str(row.get("resolution_reason", "") or ""),
                "candidate_core_class_ids": "|".join(candidate_qids),
                "candidate_core_classes": "|".join(qid_to_name.get(q, q) for q in candidate_qids),
                "candidate_core_labels": "|".join(qid_labels.get(q, qid_to_name.get(q, q)) for q in candidate_qids),
                "candidate_core_display": _format_qid_pipe(candidate_qids, qid_labels),
                "candidate_count": len(candidate_qids),
                "winner_precedence": int(precedence.get(resolved_core_qid, 10_000)),
                "depth_margin": depth_margin,
                "precedence_margin": precedence_margin,
                "decision_mode": decision_mode,
                "decision_confidence": decision_confidence,
                "winner_path_qids": "|".join(best_path),
                "winner_path_names": "|".join(qid_labels.get(q, qid_to_name.get(q, q)) for q in best_path),
                "winner_path_display": _format_qid_pipe(best_path, qid_labels),
                "path_prefix_qids": "|".join(prefix_tokens),
                "path_prefix_names": "|".join(qid_labels.get(q, qid_to_name.get(q, q)) for q in prefix_tokens),
                "path_prefix_display": _format_qid_pipe(prefix_tokens, qid_labels),
                "aligned_prefix_len": int(prefix_len),
                "aligned_suffix_len": int(suffix_len),
                "winner_branch_span": int(branch_span),
                "candidate_depth_signature": depth_signature,
                "candidate_depth_signature_display": _candidate_depth_signature_display(depth_signature, qid_labels),
                "discovered_pattern_key": pattern_key,
                "coarse_pattern_key": coarse_pattern_key,
            }
        )

    if not rows:
        return pd.DataFrame(
            columns=[
                "class_id",
                "class_label",
                "class_display",
                "resolved_core_class_id",
                "resolved_core_class",
                "resolved_core_label",
                "resolved_core_display",
                "resolution_depth",
                "resolution_reason",
                "candidate_core_class_ids",
                "candidate_core_classes",
                "candidate_core_labels",
                "candidate_core_display",
                "candidate_count",
                "winner_precedence",
                "depth_margin",
                "precedence_margin",
                "decision_mode",
                "decision_confidence",
                "winner_path_qids",
                "winner_path_names",
                "winner_path_display",
                "path_prefix_qids",
                "path_prefix_names",
                "path_prefix_display",
                "aligned_prefix_len",
                "aligned_suffix_len",
                "winner_branch_span",
                "candidate_depth_signature",
                "candidate_depth_signature_display",
                "discovered_pattern_key",
                "coarse_pattern_key",
            ]
        )

    df = pd.DataFrame(rows)
    df["resolution_depth"] = pd.to_numeric(df["resolution_depth"], errors="coerce").astype("Int64")
    return df.sort_values(
        ["candidate_count", "winner_precedence", "resolution_depth", "class_id"],
        ascending=[False, True, True, True],
    ).reset_index(drop=True)


def inspect_class_resolution_conflicts(
    repo_root: Path | str,
    *,
    min_cluster_size: int = 2,
    top_clusters: int = 12,
    label_language_preference: str | list[str] | tuple[str, ...] | None = None,
) -> dict[str, object]:
    """Inspect class-resolution conflicts and discover conflict patterns from all rows."""

    repo_root = Path(repo_root)
    class_resolution_map_path = (
        repo_root / "data" / "20_candidate_generation" / "wikidata" / "projections" / "class_resolution_map.csv"
    )
    if not class_resolution_map_path.exists():
        raise FileNotFoundError(f"Missing class-resolution map: {class_resolution_map_path}")

    qid_to_name, precedence = _core_lookup(repo_root)
    preferred_language = _resolve_preferred_language(label_language_preference)
    qid_labels = _load_qid_labels(repo_root, preferred_language)
    class_resolution_map_df = pd.read_csv(class_resolution_map_path)

    if "conflict_flag" not in class_resolution_map_df.columns:
        raise ValueError("class_resolution_map.csv does not contain 'conflict_flag' column")

    conflict_mask = class_resolution_map_df["conflict_flag"].fillna(False).astype(bool)
    conflicts_raw = class_resolution_map_df.loc[conflict_mask].copy().reset_index(drop=True)
    conflicts_df = _annotate_conflicts(conflicts_raw, qid_to_name, precedence, qid_labels)

    if conflicts_df.empty:
        empty = pd.DataFrame()
        return {
            "summary": {
                "class_resolution_rows": int(len(class_resolution_map_df)),
                "conflict_rows": 0,
                "clustered_rows": 0,
                "outlier_rows": 0,
            },
            "pattern_summary_df": empty,
            "clustered_conflicts_df": empty,
            "outlier_conflicts_df": empty,
            "all_conflicts_df": conflicts_df,
            "class_resolution_map_path": class_resolution_map_path,
        }

    strict_cluster_counts = Counter(conflicts_df["discovered_pattern_key"].tolist())
    coarse_cluster_counts = Counter(conflicts_df["coarse_pattern_key"].tolist())
    conflicts_df = conflicts_df.copy()
    conflicts_df["strict_cluster_size"] = conflicts_df["discovered_pattern_key"].map(strict_cluster_counts).astype(int)
    conflicts_df["cluster_size"] = conflicts_df["coarse_pattern_key"].map(coarse_cluster_counts).astype(int)

    clustered_df = conflicts_df[conflicts_df["cluster_size"] >= int(min_cluster_size)].copy().reset_index(drop=True)
    outlier_df = conflicts_df[conflicts_df["cluster_size"] < int(min_cluster_size)].copy().reset_index(drop=True)

    pattern_summary_df = (
        clustered_df.groupby("coarse_pattern_key", as_index=False)
        .agg(
            rows=("class_id", "count"),
            candidate_core_classes=("candidate_core_display", "first"),
            winner_core_class=("resolved_core_display", "first"),
            avg_resolution_depth=("resolution_depth", lambda s: float(pd.to_numeric(s, errors="coerce").dropna().mean()) if len(pd.to_numeric(s, errors="coerce").dropna()) else float("nan")),
            median_branch_span=("winner_branch_span", "median"),
            max_aligned_prefix_len=("aligned_prefix_len", "max"),
            dominant_decision_mode=("decision_mode", lambda values: _series_mode([str(v) for v in values])),
            dominant_confidence=("decision_confidence", lambda values: _series_mode([str(v) for v in values])),
            shared_prefix_labels=("path_prefix_display", lambda values: _series_mode([str(v) for v in values])),
            examples=("class_display", lambda values: "|".join(sorted(set(str(v) for v in values if str(v)))[:5])),
        )
        .sort_values(["rows", "candidate_core_classes", "winner_core_class"], ascending=[False, True, True])
        .head(int(top_clusters))
        .reset_index(drop=True)
        if not clustered_df.empty
        else pd.DataFrame(
            columns=[
                "coarse_pattern_key",
                "rows",
                "candidate_core_classes",
                "winner_core_class",
                "avg_resolution_depth",
                "median_branch_span",
                "max_aligned_prefix_len",
                "dominant_decision_mode",
                "dominant_confidence",
                "shared_prefix_labels",
                "examples",
            ]
        )
    )

    strict_pattern_summary_df = (
        clustered_df.groupby("discovered_pattern_key", as_index=False)
        .agg(
            rows=("class_id", "count"),
            candidate_core_classes=("candidate_core_display", "first"),
            winner_core_class=("resolved_core_display", "first"),
            depth_signature=("candidate_depth_signature_display", "first"),
            dominant_decision_mode=("decision_mode", lambda values: _series_mode([str(v) for v in values])),
            dominant_confidence=("decision_confidence", lambda values: _series_mode([str(v) for v in values])),
            examples=("class_display", lambda values: "|".join(sorted(set(str(v) for v in values if str(v)))[:5])),
        )
        .sort_values(["rows", "candidate_core_classes", "winner_core_class"], ascending=[False, True, True])
        .head(int(top_clusters))
        .reset_index(drop=True)
        if not clustered_df.empty
        else pd.DataFrame(
            columns=[
                "discovered_pattern_key",
                "rows",
                "candidate_core_classes",
                "winner_core_class",
                "depth_signature",
                "dominant_decision_mode",
                "dominant_confidence",
                "examples",
            ]
        )
    )

    top_pattern_keys = set(pattern_summary_df["coarse_pattern_key"].tolist())
    clustered_display_df = (
        clustered_df[clustered_df["coarse_pattern_key"].isin(top_pattern_keys)]
        .sort_values(
            [
                "cluster_size",
                "strict_cluster_size",
                "candidate_core_labels",
                "resolved_core_display",
                "resolution_depth",
                "class_id",
            ],
            ascending=[False, False, True, True, True, True],
        )
        .reset_index(drop=True)
    )

    summary = {
        "class_resolution_rows": int(len(class_resolution_map_df)),
        "conflict_rows": int(len(conflicts_df)),
        "clustered_rows": int(len(clustered_df)),
        "outlier_rows": int(len(outlier_df)),
        "cluster_count": int(pattern_summary_df.shape[0]),
        "largest_cluster_size": int(pattern_summary_df["rows"].max()) if not pattern_summary_df.empty else 0,
        "strict_cluster_count": int(strict_pattern_summary_df.shape[0]),
    }

    return {
        "summary": summary,
        "pattern_summary_df": pattern_summary_df,
        "strict_pattern_summary_df": strict_pattern_summary_df,
        "clustered_conflicts_df": clustered_display_df,
        "outlier_conflicts_df": outlier_df,
        "all_conflicts_df": conflicts_df,
        "class_resolution_map_path": class_resolution_map_path,
    }


def print_conflict_report(conflict_report: dict, repo_root: Path | str | None = None) -> None:
    """Render a compact, human-readable conflict report for notebooks."""

    try:
        from IPython.display import display as ipy_display
    except Exception:
        ipy_display = print

    root_path = Path(repo_root) if repo_root is not None else None

    summary = conflict_report.get("summary", {}) or {}
    source_path = conflict_report.get("class_resolution_map_path")
    if root_path is not None and source_path is not None:
        try:
            source_display = Path(source_path).relative_to(root_path)
        except Exception:
            source_display = source_path
    else:
        source_display = source_path

    print("Conflict summary:")
    print(f"  class_resolution_rows: {summary.get('class_resolution_rows', 0)}")
    print(f"  conflict_rows: {summary.get('conflict_rows', 0)}")
    print(f"  clustered_rows (patterned): {summary.get('clustered_rows', 0)}")
    print(f"  outlier_rows (unclustered): {summary.get('outlier_rows', 0)}")
    print(f"  discovered_cluster_count (coarse): {summary.get('cluster_count', 0)}")
    print(f"  discovered_cluster_count (strict): {summary.get('strict_cluster_count', 0)}")
    print(f"  largest_cluster_size: {summary.get('largest_cluster_size', 0)}")
    print(f"  source: {source_display}")

    print("\nDiscovered coarse conflict clusters (labels + decision rationale):")
    pattern_df = conflict_report.get("pattern_summary_df", pd.DataFrame())
    ipy_display(
        pattern_df[
            [
                "rows",
                "candidate_core_classes",
                "winner_core_class",
                "dominant_decision_mode",
                "dominant_confidence",
                "avg_resolution_depth",
                "median_branch_span",
                "max_aligned_prefix_len",
                "shared_prefix_labels",
                "examples",
            ]
        ]
    )

    print("\nDiscovered strict subclusters (depth-aware breakdown):")
    strict_df = conflict_report.get("strict_pattern_summary_df", pd.DataFrame())
    ipy_display(
        strict_df[
            [
                "rows",
                "candidate_core_classes",
                "winner_core_class",
                "depth_signature",
                "dominant_decision_mode",
                "dominant_confidence",
                "examples",
            ]
        ]
    )

    print("\nRows in top discovered clusters (class labels + winner paths):")
    clustered_df = conflict_report.get("clustered_conflicts_df", pd.DataFrame())
    ipy_display(
        clustered_df[
            [
                "class_display",
                "candidate_core_display",
                "resolved_core_display",
                "decision_mode",
                "decision_confidence",
                "depth_margin",
                "precedence_margin",
                "resolution_depth",
                "path_prefix_display",
                "winner_path_display",
                "cluster_size",
                "strict_cluster_size",
            ]
        ]
    )

    print("\nOutlier conflicts (class labels + winner paths):")
    outlier_df = conflict_report.get("outlier_conflicts_df", pd.DataFrame())
    ipy_display(
        outlier_df[
            [
                "class_display",
                "candidate_core_display",
                "resolved_core_display",
                "decision_mode",
                "decision_confidence",
                "depth_margin",
                "precedence_margin",
                "resolution_depth",
                "path_prefix_display",
                "winner_path_display",
            ]
        ]
    )
