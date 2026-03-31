### Migration Sequence
1. Revise required graph artifacts
- Identify if the Spec required graph artifacts are all truly required and modelled usefully. There is likely potential to further increase the modelling: `triples.csv`, class and instance csv/json partitions, properties json/csv, and materialization from node/triple events (`wikidata_future_V2.md`).
- The goal is to make the data sourced from all query responses more flexible and extensively detailed (.json) as well as structured and easy to look up (.csv). Potentially, only one json is required (entities.json) - but this may cause issues depending on filesize, particularly in the case of file corruption, requiring rebuild from query responses.
- Pros and cons of different approaches should be identified, weighed and brought to a final decision. 

1. Produce a concrete implementation blueprint
- module-by-module target APIs, event schemas, and acceptance tests mapped to each production-spec section.
- Output artifact: `documentation/Wikidata/2026-03-31_transition/step_2_implementation_blueprint.md`

1. Implement a canonical event schema.
- Add endpoint, normalized query descriptor, query hash, process step, status.
- Archive existing raw files; There is no need for versioning or schema adapters, dump them in an `archive` folder, they will be backed up outside of the repository and then deleted from the archive folder.
- Output artifact: `documentation/Wikidata/2026-03-31_transition/step_3_canonical_event_schema.md`

1. Separate graph expansion engine from candidate matching.
- The first and authoritative candidate discovery is the graph expansion. Expansion eligibility must follow direct-link plus core-class rule. It directly retrieves the knowledge a source has already connected to the broadcasting program. Since this works with direct links only and has no literal matching, it produces much less stress on the Wikidata services and should be exhausted before any other step.  
- The second step would then be string-based candidate matching, only for those entries that could not be discovered from graph expansion. Any such newly discovered candidates should also be checked for expansion eligibility. The string-based candidate matching should consider the instance-of-property to the known core classes where possible, to narrow down the scope within Wikidata that will be searched.

1. Implement node and triple stores with deterministic materialization.
- Persist discovered-only vs expanded payload states.
- Build triples.csv from event-level edge facts with dedup key subject,predicate,object. Keep in mind that the triples.csv is just a redundant lookup-table and does not fully represent statements (which can also have qualifiers and references). Any .csv information is always a redundant, easy-to-look-up layer used to ease access of the complex data stored in e.g., JSON.

1. Add checkpoint manifests and resume logic.
- Include run_id, stop_reason, seed progress counters, incomplete markers.

1. Only then align notebook orchestration.
- Notebook should call deterministic run API and display checkpoint summaries.
- Archive existing candidates.csv contract or similar deprecated files and concepts - we are still in development, the pipeline was never used outside of debugging, we can completely disregard backwards compatibility. The most important goal is to establish a new and improved Wikidata candidate generation.

1. Update authoritative docs together in one change set.
- Keep workflow.md, contracts.md, and repository-overview.md synchronized per doc governance: `README.md`.

1. Implement Testing structure
There are no visible tests covering the current Wikidata modules in the test tree. Add contract-level tests for artifact existence, schema headers, determinism, and resume behavior.