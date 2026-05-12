#!/usr/bin/env python3
import sys
sys.path.insert(0, 'speakermining/src')

from process.entity_deduplication.orchestrator import run_phase32
import pandas as pd

print("Running Phase 32...")
result = run_phase32()
print(f"✓ Phase 32 completed")
print(f"  Canonical entities: {result.get('canonical_entities')}")
print(f"  Unresolved entities: {result.get('unresolved_entities')}")

# Check for duplicate wikidata_ids
print("\nChecking for duplicate wikidata_ids in dedup_persons.csv...")
dedup_df = pd.read_csv('data/32_entity_deduplication/dedup_persons.csv')

wd_duplicates = dedup_df[dedup_df['wikidata_id'].str.strip() != ''].groupby('wikidata_id')['canonical_entity_id'].nunique()
wd_duplicates = wd_duplicates[wd_duplicates > 1]

if len(wd_duplicates) > 0:
    print(f"⚠️ FAILED: Found {len(wd_duplicates)} wikidata_ids with multiple canonical entities:")
    for wd_id, count in wd_duplicates.items():
        print(f"  {wd_id}: {count} canonical entities")
        dup_rows = dedup_df[dedup_df['wikidata_id'] == wd_id]
        for _, row in dup_rows.iterrows():
            print(f"    - {row['canonical_entity_id']}: {row['cluster_strategy']} ({row['cluster_size']} members)")
else:
    print("✓ PASSED: No duplicate wikidata_ids found!")

# Check Q1332861 specifically
print("\nQ1332861 (Elmar Theveßen) check:")
q_check = dedup_df[dedup_df['wikidata_id'] == 'Q1332861']
if len(q_check) == 1:
    print(f"✓ PASSED: Single canonical entity for Q1332861")
    print(f"  {q_check.iloc[0]['canonical_entity_id']}: {q_check.iloc[0]['cluster_strategy']}, {q_check.iloc[0]['cluster_size']} members")
else:
    print(f"✗ FAILED: {len(q_check)} canonical entities for Q1332861")
    for _, row in q_check.iterrows():
        print(f"  {row['canonical_entity_id']}: {row['cluster_strategy']}, {row['cluster_size']} members")
