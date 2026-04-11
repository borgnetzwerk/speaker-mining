from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


STOP_REASONS = {
    "seed_complete",
    "per_seed_budget_exhausted",
    "total_query_budget_exhausted",
    "queue_exhausted",
    "user_interrupted",
    "crash_recovery",
}


SOURCE_STEPS = {
    "entity_fetch",
    "inlinks_fetch",
    "subclass_inlinks_fetch",
    "outlinks_build",
    "property_fetch",
    "materialization_support",
}


@dataclass(frozen=True)
class ArtifactPaths:
    root: Path
    wikidata_dir: Path
    projections_dir: Path
    raw_queries_dir: Path
    checkpoints_dir: Path
    archive_dir: Path
    classes_csv: Path
    instances_csv: Path
    instances_leftovers_csv: Path
    properties_csv: Path
    aliases_en_csv: Path
    aliases_de_csv: Path
    triples_csv: Path
    class_hierarchy_csv: Path
    class_resolution_map_csv: Path
    entity_store_jsonl: Path
    property_store_jsonl: Path
    query_inventory_csv: Path
    entity_lookup_index_csv: Path
    entity_chunks_dir: Path
    summary_json: Path
    core_classes_csv: Path
    root_class_csv: Path
    other_interesting_classes_csv: Path
    broadcasting_programs_csv: Path
    graph_stage_resolved_targets_csv: Path
    graph_stage_unresolved_targets_csv: Path
    fallback_stage_candidates_csv: Path
    fallback_stage_eligible_for_expansion_csv: Path
    fallback_stage_ineligible_csv: Path

    # Backward-compatible aliases for pre-rework callers/tests.
    @property
    def entities_json(self) -> Path:
        return self.entity_store_jsonl

    @property
    def properties_json(self) -> Path:
        return self.property_store_jsonl

    @property
    def triples_events_json(self) -> Path:
        return self.projections_dir / "triple_events.json"


def core_instances_json_filename(class_filename: str) -> str:
    return f"instances_core_{canonical_class_filename(class_filename)}.json"


def canonical_class_filename(name: str) -> str:
    token = str(name or "").strip().lower().replace(" ", "_")
    if token == "organisations":
        raise ValueError("Use canonical class filename 'organizations', not 'organisations'.")
    return token


def build_artifact_paths(repo_root: Path) -> ArtifactPaths:
    repo_root = Path(repo_root)
    wikidata_dir = repo_root / "data" / "20_candidate_generation" / "wikidata"
    projections_dir = wikidata_dir / "projections"
    projections_dir.mkdir(parents=True, exist_ok=True)
    return ArtifactPaths(
        root=repo_root,
        wikidata_dir=wikidata_dir,
        projections_dir=projections_dir,
        raw_queries_dir=wikidata_dir / "raw_queries",
        checkpoints_dir=wikidata_dir / "checkpoints",
        archive_dir=wikidata_dir / "archive",
        classes_csv=projections_dir / "classes.csv",
        instances_csv=projections_dir / "instances.csv",
        instances_leftovers_csv=projections_dir / "instances_leftovers.csv",
        properties_csv=projections_dir / "properties.csv",
        aliases_en_csv=projections_dir / "aliases_en.csv",
        aliases_de_csv=projections_dir / "aliases_de.csv",
        triples_csv=projections_dir / "triples.csv",
        class_hierarchy_csv=projections_dir / "class_hierarchy.csv",
        class_resolution_map_csv=projections_dir / "class_resolution_map.csv",
        entity_store_jsonl=projections_dir / "entity_store.jsonl",
        property_store_jsonl=projections_dir / "property_store.jsonl",
        query_inventory_csv=projections_dir / "query_inventory.csv",
        entity_lookup_index_csv=projections_dir / "entity_lookup_index.csv",
        entity_chunks_dir=projections_dir / "entity_chunks",
        summary_json=projections_dir / "summary.json",
        core_classes_csv=projections_dir / "core_classes.csv",
        root_class_csv=projections_dir / "root_class.csv",
        other_interesting_classes_csv=projections_dir / "other_interesting_classes.csv",
        broadcasting_programs_csv=projections_dir / "broadcasting_programs.csv",
        graph_stage_resolved_targets_csv=projections_dir / "graph_stage_resolved_targets.csv",
        graph_stage_unresolved_targets_csv=projections_dir / "graph_stage_unresolved_targets.csv",
        fallback_stage_candidates_csv=projections_dir / "fallback_stage_candidates.csv",
        fallback_stage_eligible_for_expansion_csv=projections_dir / "fallback_stage_eligible_for_expansion.csv",
        fallback_stage_ineligible_csv=projections_dir / "fallback_stage_ineligible.csv",
    )
