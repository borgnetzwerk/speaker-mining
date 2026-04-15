# Wikidata TODO Tracker

Date created: 2026-03-31
Scope: Wikidata candidate-generation and graph-quality tasks only

## Status Legend

- [ ] not started
- [~] in progress
- [x] completed


### Fix Projections
* entity_store.jsonl 
* property_store.jsonl
This currently seems to be a json file dumped into a jsonl file. It is probably a failed sidecar of the `entity_chunks` and `entity_lookup_index.csv` entity writing rework. Very likely, it can be deprecated. 
In case of property_store.jsonl, there is no similar structure for properties - we need to fix this.

### Add additional projections
* classes.json
A projection of all information we have on all classes.
* properties.json 
A projection of all information we have on all properties.

