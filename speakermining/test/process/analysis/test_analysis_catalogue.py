#!/usr/bin/env python3
import sys
sys.path.insert(0, 'speakermining/src')
import pandas as pd
from analysis.occurrence_matrix import build_person_catalogue

# Load corrected phase 32 outputs
dedup_persons = pd.read_csv('data/32_entity_deduplication/dedup_persons.csv')
dedup_members = pd.read_csv('data/32_entity_deduplication/dedup_cluster_members.csv')

# Load episode metadata
episodes = pd.read_csv('data/10_mention_detection/episodes.csv')

print(f'Inputs:')
print(f'  dedup_persons: {len(dedup_persons)} rows')
print(f'  dedup_members: {len(dedup_members)} rows')
print(f'  episodes: {len(episodes)} rows')

# Call the helper function
catalogue, unmatched, unclassified, ri_with_role, ep_appearances = build_person_catalogue(
    dedup_persons, dedup_members, episodes
)

print(f'\nOutputs:')
print(f'  catalogue: {len(catalogue)} rows')
print(f'  unmatched: {len(unmatched)} rows')
print(f'  unclassified: {len(unclassified)} rows')
print(f'  ri_with_role: {len(ri_with_role)} rows')
print(f'  ep_appearances: {len(ep_appearances)} rows')

# Check Q1332861 in the catalogue
q_check = catalogue[catalogue['wikidata_id'] == 'Q1332861']
print(f'\nQ1332861 in catalogue:')
print(f'  Entries: {len(q_check)}')
if len(q_check) > 0:
    row = q_check.iloc[0]
    print(f'  appearance_count: {row["appearance_count"]}')
    print(f'  canonical_entity_id: {row["canonical_entity_id"]}')
    print(f'  ✓ Q1332861 verified in catalogue')
else:
    print(f'  ✗ Q1332861 not found in catalogue!')

print(f'\n✓ build_person_catalogue test completed successfully')
