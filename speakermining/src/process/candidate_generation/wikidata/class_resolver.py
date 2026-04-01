from __future__ import annotations

from collections import deque

from .common import canonical_qid, effective_core_class_qids


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


def resolve_class_path(entity_doc: dict, core_class_qids: set[str], get_entity_fn) -> dict:
    core = effective_core_class_qids(core_class_qids)
    entity_id = canonical_qid(entity_doc.get("id", ""))
    if not entity_id:
        return {
            "class_id": "",
            "path_to_core_class": "",
            "subclass_of_core_class": False,
            "is_class_node": False,
        }

    p31 = _claim_item_qids(entity_doc, "P31")
    p279 = _claim_item_qids(entity_doc, "P279")
    is_class_node = bool(p279)

    if not core:
        class_id = p279[0] if is_class_node and p279 else (p31[0] if p31 else "")
        return {
            "class_id": class_id,
            "path_to_core_class": "",
            "subclass_of_core_class": False,
            "is_class_node": is_class_node,
        }

    starts = p279 if is_class_node and p279 else p31
    if not starts:
        return {
            "class_id": "",
            "path_to_core_class": "",
            "subclass_of_core_class": False,
            "is_class_node": is_class_node,
        }

    queue: deque[tuple[str, list[str]]] = deque()
    seen: set[str] = set()
    for qid in starts:
        queue.append((qid, [qid]))
        seen.add(qid)

    while queue:
        node_qid, path = queue.popleft()
        if node_qid in core:
            return {
                "class_id": path[0],
                "path_to_core_class": "|".join(path),
                "subclass_of_core_class": True,
                "is_class_node": is_class_node,
            }
        node_doc = get_entity_fn(node_qid) or {}
        for parent in _claim_item_qids(node_doc, "P279"):
            if parent in seen:
                continue
            seen.add(parent)
            queue.append((parent, path + [parent]))

    return {
        "class_id": starts[0],
        "path_to_core_class": "",
        "subclass_of_core_class": False,
        "is_class_node": is_class_node,
    }


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
