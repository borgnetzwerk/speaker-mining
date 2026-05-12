#!/usr/bin/env python3
import sys
sys.path.insert(0, 'speakermining/src')
import pandas as pd
import json
from pathlib import Path
from analysis import build_person_catalogue

# Setup paths
repo_root = Path.cwd()
ARCH = Path("data/20_candidate_generation/wikidata/projections/archive")

# Load data
print("Loading data...")
broadcasting_programs = pd.read_csv("data/00_setup/broadcasting_programs.csv", dtype=str).fillna("")
IN_SCOPE_SHOW_IDS = {
    s.strip() for s in broadcasting_programs["fernsehserien_de_id"]
    if s.strip() and s.strip() != "NONE"
}

dedup_persons = pd.read_csv("data/32_entity_deduplication/dedup_persons.csv", dtype=str).fillna("")
dedup_persons_unresolved = pd.read_csv("data/32_entity_deduplication/dedup_persons_unresolved.csv", dtype=str).fillna("")
cluster_members = pd.read_csv("data/32_entity_deduplication/dedup_cluster_members.csv", dtype=str).fillna("")
episode_meta = pd.read_csv("data/31_entity_disambiguation/raw_import/episode_metadata_normalized.csv", dtype=str).fillna("")

core_persons = json.loads((ARCH / "core_persons.json").read_text(encoding="utf-8"))
instances = pd.read_csv(ARCH / "instances.csv", dtype=str).fillna("")

qid_label = {}
for _, row in instances.iterrows():
    label = row.get("labels_de", "") or row.get("labels_en", "") or row.get("label", "")
    if row["qid"] and label:
        qid_label[row["qid"]] = label
for qid, entity in core_persons.items():
    labels = entity.get("labels", {})
    label = labels.get("de", {}).get("value", "") or labels.get("en", {}).get("value", "")
    if label:
        qid_label[qid] = label

print("Calling build_person_catalogue...")
MODERATOR_QIDS = {"Q43773"}  # Markus Lanz
catalogue, unmatched, unclassified, ri_with_role, episode_appearances = build_person_catalogue(
    dedup_persons=dedup_persons,
    cluster_members=cluster_members,
    episode_meta=episode_meta,
    in_scope_show_ids=IN_SCOPE_SHOW_IDS,
    core_persons=core_persons,
    qid_label=qid_label,
    moderator_qids=MODERATOR_QIDS,
    repo_root=repo_root,
)

print("\nCatalogue structure:")
print(f"  Shape: {catalogue.shape}")
print(f"  Columns: {list(catalogue.columns)}")
print(f"\nFirst few rows:")
print(catalogue.head(2))

print("\n✓ build_person_catalogue() returned successfully")
print(f"  Q1332861 in catalogue: {len(catalogue[catalogue['wikidata_id'] == 'Q1332861']) > 0}")
