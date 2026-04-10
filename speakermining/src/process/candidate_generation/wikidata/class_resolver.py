from __future__ import annotations

import csv
from collections import deque
from dataclasses import dataclass
from pathlib import Path

from .common import canonical_qid, effective_core_class_qids


@dataclass(frozen=True)
class RecoveredLineageEvidence:
    class_to_path: dict[str, str]
    class_to_subclass_of_core: dict[str, bool]
    class_to_parent_qids: dict[str, tuple[str, ...]]
    diagnostics: dict[str, int]


_RESOLUTION_POLICY_RUNTIME_ONLY = "runtime_only"
_RESOLUTION_POLICY_RUNTIME_THEN_RECOVERED = "runtime_then_recovered"
_RESOLUTION_POLICY_RUNTIME_THEN_RECOVERED_THEN_NETWORK = "runtime_then_recovered_then_network"


def _normalize_resolution_policy(value: object) -> str:
    policy = str(value or "").strip().lower()
    allowed = {
        _RESOLUTION_POLICY_RUNTIME_ONLY,
        _RESOLUTION_POLICY_RUNTIME_THEN_RECOVERED,
        _RESOLUTION_POLICY_RUNTIME_THEN_RECOVERED_THEN_NETWORK,
    }
    if policy in allowed:
        return policy
    return _RESOLUTION_POLICY_RUNTIME_THEN_RECOVERED_THEN_NETWORK


def _parse_bool(value: object) -> bool:
    token = str(value or "").strip().lower()
    return token in {"1", "true", "yes", "y"}


def _parse_qid_path(raw_path: object) -> tuple[tuple[str, ...], bool]:
    text = str(raw_path or "").strip()
    if not text:
        return (), False
    tokens: list[str] = []
    for part in text.split("|"):
        qid = canonical_qid(part)
        if qid:
            tokens.append(qid)
    return tuple(tokens), bool(text and not tokens)


def _parse_qid_list(raw_values: object) -> tuple[tuple[str, ...], bool]:
    text = str(raw_values or "").strip()
    if not text:
        return (), False
    out: list[str] = []
    seen: set[str] = set()
    for part in text.split("|"):
        qid = canonical_qid(part)
        if not qid or qid in seen:
            continue
        seen.add(qid)
        out.append(qid)
    return tuple(out), bool(text and not out)


def load_recovered_class_hierarchy(path: Path | str) -> RecoveredLineageEvidence:
    """Load reverse-engineering class hierarchy evidence with strict normalization.

    This loader is intentionally side-effect-free. It does not mutate runtime state
    and can be called repeatedly to produce deterministic results.
    """

    csv_path = Path(path)
    diagnostics = {
        "total_rows": 0,
        "loaded_rows": 0,
        "skipped_missing_class_id": 0,
        "skipped_no_lineage_signal": 0,
        "malformed_path_rows": 0,
        "malformed_parent_rows": 0,
        "file_missing": 0,
    }
    class_to_path: dict[str, str] = {}
    class_to_subclass_of_core: dict[str, bool] = {}
    class_to_parent_qids: dict[str, tuple[str, ...]] = {}

    if not csv_path.exists():
        diagnostics["file_missing"] = 1
        return RecoveredLineageEvidence(
            class_to_path=class_to_path,
            class_to_subclass_of_core=class_to_subclass_of_core,
            class_to_parent_qids=class_to_parent_qids,
            diagnostics=diagnostics,
        )

    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            diagnostics["total_rows"] += 1
            class_id = canonical_qid(row.get("class_id", ""))
            if not class_id:
                diagnostics["skipped_missing_class_id"] += 1
                continue

            path_tokens, path_malformed = _parse_qid_path(row.get("path_to_core_class", ""))
            parent_qids, parents_malformed = _parse_qid_list(row.get("parent_qids", ""))
            subclass_flag = _parse_bool(row.get("subclass_of_core_class", ""))

            if path_malformed:
                diagnostics["malformed_path_rows"] += 1
            if parents_malformed:
                diagnostics["malformed_parent_rows"] += 1

            resolved_path = "|".join(path_tokens)
            derived_subclass = bool(subclass_flag or path_tokens)
            has_signal = bool(derived_subclass or parent_qids)
            if not has_signal:
                diagnostics["skipped_no_lineage_signal"] += 1
                continue

            class_to_path[class_id] = resolved_path
            class_to_subclass_of_core[class_id] = derived_subclass
            class_to_parent_qids[class_id] = parent_qids
            diagnostics["loaded_rows"] += 1

    return RecoveredLineageEvidence(
        class_to_path=class_to_path,
        class_to_subclass_of_core=class_to_subclass_of_core,
        class_to_parent_qids=class_to_parent_qids,
        diagnostics=diagnostics,
    )


def _resolve_via_recovered_lineage(
    start_qid: str,
    core_class_qids: set[str],
    recovered_lineage: RecoveredLineageEvidence | None,
) -> list[str]:
    if not recovered_lineage:
        return []
    start = canonical_qid(start_qid)
    if not start:
        return []

    raw_path = str(recovered_lineage.class_to_path.get(start, "") or "")
    path_tokens = [canonical_qid(token) for token in raw_path.split("|") if canonical_qid(token)]
    if path_tokens and path_tokens[0] != start:
        path_tokens = [start] + path_tokens

    if path_tokens:
        for idx, token in enumerate(path_tokens):
            if token in core_class_qids:
                return path_tokens[: idx + 1]

    parent_qids = recovered_lineage.class_to_parent_qids.get(start, tuple())
    for parent in parent_qids:
        if parent in core_class_qids:
            return [start, parent]

    if bool(recovered_lineage.class_to_subclass_of_core.get(start, False)) and start in core_class_qids:
        return [start]

    return []


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


def resolve_class_path(
    entity_doc: dict,
    core_class_qids: set[str],
    get_entity_fn,
    on_resolved=None,
    *,
    recovered_lineage: RecoveredLineageEvidence | None = None,
    resolution_policy: str = _RESOLUTION_POLICY_RUNTIME_THEN_RECOVERED_THEN_NETWORK,
) -> dict:
    def _emit(result: dict, reason: str) -> dict:
        if callable(on_resolved):
            on_resolved({**result, "resolution_reason": reason})
        return result

    core = effective_core_class_qids(core_class_qids)
    policy = _normalize_resolution_policy(resolution_policy)
    entity_id = canonical_qid(entity_doc.get("id", ""))
    if not entity_id:
        return _emit({
            "class_id": "",
            "path_to_core_class": "",
            "subclass_of_core_class": False,
            "is_class_node": False,
        }, "invalid_entity")

    p31 = _claim_item_qids(entity_doc, "P31")
    p279 = _claim_item_qids(entity_doc, "P279")
    is_class_node = bool(p279)

    if not core:
        class_id = p279[0] if is_class_node and p279 else (p31[0] if p31 else "")
        return _emit({
            "class_id": class_id,
            "path_to_core_class": "",
            "subclass_of_core_class": False,
            "is_class_node": is_class_node,
        }, "no_core_classes")

    starts = p279 if is_class_node and p279 else p31
    if not starts:
        return _emit({
            "class_id": "",
            "path_to_core_class": "",
            "subclass_of_core_class": False,
            "is_class_node": is_class_node,
        }, "no_class_claims")

    queue: deque[tuple[str, list[str]]] = deque()
    seen: set[str] = set()
    for qid in starts:
        queue.append((qid, [qid]))
        seen.add(qid)

    while queue:
        node_qid, path = queue.popleft()
        if node_qid in core:
            return _emit({
                "class_id": path[0],
                "path_to_core_class": "|".join(path),
                "subclass_of_core_class": True,
                "is_class_node": is_class_node,
            }, "core_match")
        if policy == _RESOLUTION_POLICY_RUNTIME_ONLY:
            continue
        if policy in {
            _RESOLUTION_POLICY_RUNTIME_THEN_RECOVERED,
            _RESOLUTION_POLICY_RUNTIME_THEN_RECOVERED_THEN_NETWORK,
        }:
            recovered_path = _resolve_via_recovered_lineage(node_qid, core, recovered_lineage)
            if recovered_path:
                return _emit({
                    "class_id": recovered_path[0],
                    "path_to_core_class": "|".join(recovered_path),
                    "subclass_of_core_class": True,
                    "is_class_node": is_class_node,
                }, "core_match_recovered")
        if policy != _RESOLUTION_POLICY_RUNTIME_THEN_RECOVERED_THEN_NETWORK:
            continue
        node_doc = get_entity_fn(node_qid) or {}
        for parent in _claim_item_qids(node_doc, "P279"):
            if parent in seen:
                continue
            seen.add(parent)
            queue.append((parent, path + [parent]))

    return _emit({
        "class_id": starts[0],
        "path_to_core_class": "",
        "subclass_of_core_class": False,
        "is_class_node": is_class_node,
    }, "no_core_match")


def compute_class_rollups(items_iterable) -> list[dict]:
    rollups: dict[str, dict] = {}
    for item in items_iterable:
        class_id = str(item.get("class_id", "") or "")
        if class_id not in rollups:
            rollups[class_id] = {
                "id": class_id,
                "label_en": "",
                "label_de": "",
                "description_en": "",
                "description_de": "",
                "alias_en": "",
                "alias_de": "",
                "path_to_core_class": str(item.get("path_to_core_class", "") or ""),
                "subclass_of_core_class": bool(item.get("subclass_of_core_class", False)),
                "discovered_count": 0,
                "expanded_count": 0,
            }
        rollups[class_id]["discovered_count"] += 1
        if str(item.get("expanded_at_utc", "") or ""):
            rollups[class_id]["expanded_count"] += 1
    return [rollups[key] for key in sorted(rollups)]
