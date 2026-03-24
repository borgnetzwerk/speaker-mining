# Data Contracts

Contract-level names and columns are defined in phase config modules.

## Contract Source Files

1. speakermining/src/process/mention_detection/config.py
2. speakermining/src/process/candidate_generation/config.py
3. speakermining/src/process/entity_disambiguation/config.py
4. speakermining/src/process/entity_deduplication/config.py

## Phase Output Locations

1. data/10_mention_detection/
2. data/20_canidate_generation/
3. data/30_entity_disambiguation/
4. data/31_entity_deduplication/
5. data/40_link_prediction/

## Required Outputs by Phase

### P1 mention detection

Files:

1. episodes.csv
2. persons.csv
3. institutions.csv
4. topics.csv
5. seasons.csv

Core columns:

1. episodes.csv: episode_id, sendungstitel, publikationsdatum, dauer, season, staffel, folge, folgennr, infos
2. persons.csv: mention_id, episode_id, name, beschreibung, source_text
3. institutions.csv: mention_id, episode_id, institution, source_text
4. topics.csv: mention_id, episode_id, topic, source_text
5. seasons.csv: season_id, season_label, start_time, end_time, episode_count

### P2 candidate generation

Files:

1. candidates.csv
2. links.csv
3. cache/*.csv

Core columns:

1. candidates.csv: mention_id, mention_label, candidate_id, candidate_label, source, score, context
2. links.csv: src_candidate_id, property, value, target_candidate_id, source

### P3.1 entity disambiguation

Files:

1. similarity.csv
2. recommendations.csv
3. selections.csv (manual required)

Core columns:

1. similarity.csv: mention_id, candidate_id, score, method, explanation
2. recommendations.csv: mention_id, recommended_candidate_id, confidence, reasons
3. selections.csv: mention_id, selected_candidate_id, decision, reason, reviewer, reviewed_at

### P3.2 entity deduplication

Files:

1. similarity.csv
2. recommendations.csv
3. selections.csv (manual required)

Core columns:

1. similarity.csv: entity_id_left, entity_id_right, score, method, explanation
2. recommendations.csv: entity_id_left, entity_id_right, recommended_action, confidence, reasons
3. selections.csv: entity_id_left, entity_id_right, decision, merged_entity_id, reason, reviewer, reviewed_at

### P4 link prediction

Files:

1. rel.csv

Core columns:

1. rel.csv: source_id, property, target_id, confidence, reason
