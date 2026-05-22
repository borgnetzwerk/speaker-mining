# Task Index

Single entry point for all open tasks. See [task-principles.md](../task-principles.md) for size definitions, naming rules, and the archiving process.

---

## Small tasks

*(code-scope, deferred — no individual file; captured here for visibility)*

- **atomic-write-csv-column-selection**: Add explicit column selection list before every `atomic_write_csv` call so that column order and presence are contract-defined, not derived from whatever DataFrame happens to exist at call time. Identified by: Veteran Developer (R01), Data Engineer (R05).
- **parsing-rule-frozenset-constant**: Define `VALID_PARSING_RULES: frozenset` constant in `mention_detection/config.py` so rule membership can be validated at parse time rather than discovered by inspection. Identified by: Veteran Developer (R01), task 5.
- **fetch-error-threshold-assertion**: Add an assertion after each network-backed fetch loop that raises if the error rate exceeds a configurable threshold (e.g., >10%). Prevents silent partial-fetch runs from propagating to downstream phases. Identified by: Data Engineer (R05), task 6.
- **fernsehserien-checkpoint-retention-policy**: Define and document a checkpoint retention policy for fernsehserien.de cache files — how long cached pages are considered fresh, when they are invalidated, and whether old checkpoints are ever deleted. Currently undocumented and potentially unbounded. Identified by: Data Engineer (R05), task 8.

---

## Medium tasks

### 2026-05-22_institution-extraction-responsibility — [2026-05-22_institution-extraction-responsibility.md](2026-05-22_institution-extraction-responsibility.md)
* priority: low
* scope: architecture
* summary: Institution extraction exists in deferred code but not in active default outputs; clarify which phase owns it and reconcile conflicting documentation.

### 2026-05-22_gender-framing-methodology — [2026-05-22_gender-framing-methodology.md](2026-05-22_gender-framing-methodology.md)
* priority: low
* scope: pipeline
* summary: Define a reproducible query and method for gender-framing analysis so results can be regenerated and interpreted consistently.

### 2026-05-22_merge-strategy-role-occupation — [2026-05-22_merge-strategy-role-occupation.md](2026-05-22_merge-strategy-role-occupation.md)
* priority: low
* scope: pipeline
* summary: Define merge semantics for role/occupation/position/institution entities and document required schema or pipeline changes.

### 2026-05-22_aligned-csv-column-footprint — [2026-05-22_aligned-csv-column-footprint.md](2026-05-22_aligned-csv-column-footprint.md)
* priority: medium
* scope: contracts
* status: in-progress
* summary: Reduce aligned_persons.csv from 2,531 columns to approximately 40 by removing raw_json_wikidata and duplicate normalized/raw column variants; re-run Notebook 31 to verify.

### 2026-05-22_gender-distribution-extended — [2026-05-22_gender-distribution-extended.md](2026-05-22_gender-distribution-extended.md)
* priority: medium
* scope: pipeline
* summary: Add grouped-bar gender chart (by-individual vs. by-occurrence side-by-side), occupation subclustering via P279 traversal, and age distribution violin plot.

### 2026-05-22_dataset-overview-statistics — [2026-05-22_dataset-overview-statistics.md](2026-05-22_dataset-overview-statistics.md)
* priority: medium
* scope: documentation
* summary: Create a structured overview of instance/class/subclass counts, Wikidata match rates, deduplication rates, and step-by-step pipeline statistics.

### 2026-05-22_wikidata-visualization-improvements — [2026-05-22_wikidata-visualization-improvements.md](2026-05-22_wikidata-visualization-improvements.md)
* priority: medium
* scope: pipeline
* summary: Fix QID label bug in candidate generation Cell 12, correct hierarchy view directionality, and add Sunburst and Sankey diagrams with PNG/PDF export.

### 2026-05-22_mention-category-propagation — [2026-05-22_mention-category-propagation.md](2026-05-22_mention-category-propagation.md)
* priority: medium
* scope: pipeline
* summary: Verify and enforce that mention_category flows from Phase 1 through Phase 31 and 32, producing separate guests.csv and others.csv outputs.

### 2026-05-22_pipeline-highlights-document — [2026-05-22_pipeline-highlights-document.md](2026-05-22_pipeline-highlights-document.md)
* priority: low
* scope: documentation
* summary: Compile the top 5–10 most interesting normalizations, edge cases, and challenges from the pipeline suitable for a talk or paper.

### 2026-05-22_pagerank-node-graph — [2026-05-22_pagerank-node-graph.md](2026-05-22_pagerank-node-graph.md)
* priority: medium
* scope: pipeline
* summary: Replace the page rank bar chart in 51_visualization.ipynb with a proper node-graph visualization showing nodes sized or colored by rank score.

### 2026-05-22_gender-bias-scope-caveat — [2026-05-22_gender-bias-scope-caveat.md](2026-05-22_gender-bias-scope-caveat.md)
* priority: low
* scope: documentation
* summary: Add a clearly worded caveat to gender analysis output clarifying that bias metrics describe the sample only, not the total population.

### 2026-05-22_instances-csv-dual-write — [2026-05-22_instances-csv-dual-write.md](2026-05-22_instances-csv-dual-write.md)
* priority: medium
* scope: architecture
* summary: Remove _materialize's write to instances.csv so the file is exclusively owned by InstancesHandler, eliminating the 16,054-row discrepancy.

### 2026-05-22_extend-pipeline-scope — [2026-05-22_extend-pipeline-scope.md](2026-05-22_extend-pipeline-scope.md)
* priority: low
* scope: pipeline
* summary: Parameterize input discovery so the pipeline can process shows other than Markus Lanz by changing a config value, not code.

### 2026-05-22_node-integrity-pass-performance — [2026-05-22_node-integrity-pass-performance.md](2026-05-22_node-integrity-pass-performance.md)
* priority: medium
* scope: pipeline
* summary: Investigate why the Wikidata Node Integrity Pass took over 6726 seconds without completing and either optimize or make a principled decision to skip it.

### 2026-05-22_moderator-exclusion — [2026-05-22_moderator-exclusion.md](2026-05-22_moderator-exclusion.md)
* priority: medium
* scope: pipeline
* summary: Ensure moderators (e.g. Markus Lanz, Q43773) are excluded from all analysis outputs by introducing a dedicated "moderator" classification category.

### 2026-05-22_guest-classification-audit — [2026-05-22_guest-classification-audit.md](2026-05-22_guest-classification-audit.md)
* priority: medium
* scope: pipeline
* summary: Trace Elon Musk's misclassified guest_catalogue.csv entry to its Phase 1 source and audit a random sample of ≥20 entries to detect systematic topic-as-guest misclassification.

### 2026-05-22_time-sensitive-wikidata-claims — [2026-05-22_time-sensitive-wikidata-claims.md](2026-05-22_time-sensitive-wikidata-claims.md)
* priority: medium
* scope: pipeline
* summary: Filter Wikidata property values (party, occupation, employer) against episode dates so only claims valid at the time of appearance are used in analysis.

### 2026-05-22_roles-projection-fix — [2026-05-22_roles-projection-fix.md](2026-05-22_roles-projection-fix.md)
* priority: high
* scope: pipeline
* status: in-progress
* summary: Fix role-type projection to use P279 subclass nodes rather than P31 instances so core_roles.json contains actual journalist/politician entities after Phase 2 re-run.

### 2026-05-22_property-hydration-config-alignment — [2026-05-22_property-hydration-config-alignment.md](2026-05-22_property-hydration-config-alignment.md)
* priority: low
* scope: architecture
* summary: Create a dedicated hydration_properties.csv config file mirroring relevancy_relation_contexts.csv structure, replacing hardcoded predicate lists in Phase 2.1.

### 2026-05-22_fernsehserien-person-id-fix — [2026-05-22_fernsehserien-person-id-fix.md](2026-05-22_fernsehserien-person-id-fix.md)
* priority: medium
* scope: contracts
* summary: Fix Phase 31 alignment to populate fernsehserien_de_id with the person slug (e.g. andrej-gurkov) instead of the episode URL.

### 2026-05-22_visualization-reference-library — [2026-05-22_visualization-reference-library.md](2026-05-22_visualization-reference-library.md)
* priority: medium
* scope: pipeline
* summary: Build a reference notebook with one cell per Phase 5 plot type (violin, grouped bar, etc.) using dummy data, exported PNG/PDF, and documented principles.

### 2026-05-22_requirements-formalization — [2026-05-22_requirements-formalization.md](2026-05-22_requirements-formalization.md)
* priority: low
* scope: workflow
* summary: Research and document an established requirements formalization approach (user stories, structured contracts, etc.) appropriate for this cooperative human-agent project.

### 2026-05-22_validation-pass-protocol — [2026-05-22_validation-pass-protocol.md](2026-05-22_validation-pass-protocol.md)
* priority: medium
* scope: workflow
* summary: Document a formal validation pass checklist (old vs. new output diff, runtime, event log, design vs. implementation) required for all larger reworks.

### 2026-05-22_seed-removal-propagation — [2026-05-22_seed-removal-propagation.md](2026-05-22_seed-removal-propagation.md)
* priority: medium
* scope: architecture
* summary: Design and implement a mechanism to propagate seed/core-class/rule removals to downstream pipeline outputs without requiring a full re-run.

### 2026-05-22_runtime-statistics — [2026-05-22_runtime-statistics.md](2026-05-22_runtime-statistics.md)
* priority: medium
* scope: workflow
* summary: Implement a lightweight statistics emitter (decorator or context manager) that records per-function timing and output counts to a JSON-lines log with configurable verbosity levels.

### 2026-05-22_episode-topic-classification — [2026-05-22_episode-topic-classification.md](2026-05-22_episode-topic-classification.md)
* priority: medium
* scope: pipeline
* summary: Define a 10–15 topic German-language taxonomy and implement a Phase 50 module classifying each episode from its description text, enabling topic × demographic analysis.

### 2026-05-22_predictive-analytics — [2026-05-22_predictive-analytics.md](2026-05-22_predictive-analytics.md)
* priority: low
* scope: pipeline
* summary: Identify which guest properties predict other properties using deterministic association rule mining and frequent pattern discovery — no ML or black-box approaches.

### 2026-05-22_guest-speaking-time — [2026-05-22_guest-speaking-time.md](2026-05-22_guest-speaking-time.md)
* priority: low
* scope: pipeline
* summary: Measure each guest's speaking time and word count per appearance using diarized Whisper transcripts, adding a voice_share metric alongside appearance_count.

### 2026-05-22_named-entity-co-mention — [2026-05-22_named-entity-co-mention.md](2026-05-22_named-entity-co-mention.md)
* priority: low
* scope: pipeline
* summary: Extract named entities from episode descriptions to characterize persons mentioned but never appearing as guests — revealing the "mentioned but never invited" population.

### 2026-05-22_topic-demographic-correlation — [2026-05-22_topic-demographic-correlation.md](2026-05-22_topic-demographic-correlation.md)
* priority: low
* scope: pipeline
* summary: Join episode topic labels with Phase 50 demographic data to test whether specific topics are discussed with systematically different guest demographics.

### 2026-05-22_data-privacy-catalogue — [2026-05-22_data-privacy-catalogue.md](2026-05-22_data-privacy-catalogue.md)
* priority: low
* scope: documentation
* summary: Define which pipeline properties (gender, age, party, employer) are sensitive under GDPR and living-persons protection, and document access tiers for public vs. research releases.

### 2026-05-22_mention-level-evaluation — [2026-05-22_mention-level-evaluation.md](2026-05-22_mention-level-evaluation.md)
* priority: medium
* scope: research
* summary: Construct a 100-row stratified sample from persons.csv and manually annotate for precision/recall; report results by parsing_rule in documentation/evaluation.md.

### 2026-05-22_cross-source-validation — [2026-05-22_cross-source-validation.md](2026-05-22_cross-source-validation.md)
* priority: medium
* scope: research
* summary: Compare ZDF PDF and fernsehserien.de guest attribution for shared episodes; document agreement rates and disagreement categories in documentation/evaluation.md.

### 2026-05-22_phase50-inferential-stats — [2026-05-22_phase50-inferential-stats.md](2026-05-22_phase50-inferential-stats.md)
* priority: low
* scope: research
* summary: Define and document the minimum inferential statistics standard for Phase 50 outputs — either confirm descriptive-only with rationale, or name test families and correction strategy.

### 2026-05-22_fixture-dataset — [2026-05-22_fixture-dataset.md](2026-05-22_fixture-dataset.md)
* priority: medium
* scope: testing
* status: deferred (code-scope; prerequisite: T27 CI setup)
* summary: Create a 5-episode plaintext fixture corpus in speakermining/test/fixtures/ covering all parsing_rule values; mark live-corpus tests with @pytest.mark.requires_corpus.

### 2026-05-22_event-log-health-notebook — [2026-05-22_event-log-health-notebook.md](2026-05-22_event-log-health-notebook.md)
* priority: low
* scope: operations
* status: deferred (code-scope)
* summary: Create a notebook/script that reads pipeline event logs and produces a one-page health_summary.md with success/failure ratios, error type distribution, and threshold alerts.

### 2026-05-22_data-lineage-trace — [2026-05-22_data-lineage-trace.md](2026-05-22_data-lineage-trace.md)
* priority: low
* scope: operations
* status: deferred (code-scope)
* summary: Implement trace_entity(canonical_entity_id) that walks all pipeline stage outputs and returns a structured per-stage record for debugging entity value provenance.

### 2026-05-22_phase31-32-zenodo-dataset — [2026-05-22_phase31-32-zenodo-dataset.md](2026-05-22_phase31-32-zenodo-dataset.md)
* priority: low
* scope: dissemination
* status: deferred (requires legal review of ZDF data agreement)
* summary: Publish the Phase 31/32 deduplicated entity dataset as a standalone Zenodo dataset; legal review of ZDF and fernsehserien.de terms required before proceeding.

### 2026-05-22_v4-architecture-documentation — [2026-05-22_v4-architecture-documentation.md](2026-05-22_v4-architecture-documentation.md)
* priority: medium
* scope: documentation
* summary: Document the 6 v4 Wikidata architecture design principles from the investigation archive into a living Wikidata doc, unblocking T02 (V3 archive removal).

### 2026-05-22_claude-md-coding-conventions — [2026-05-22_claude-md-coding-conventions.md](2026-05-22_claude-md-coding-conventions.md)
* priority: high
* scope: workflow
* summary: Extend CLAUDE.md to explicitly warn against run_phase* wrapper functions and instruct placing all orchestration logic in notebook cells, referencing coding-principles.md.

---

## Large tasks

### github-ready-synthesis — [2026-05-21_GitHub_ready/](2026-05-21_GitHub_ready/)
* priority: high
* scope: documentation
* summary: Transform the research workspace into a publicly approachable GitHub repository — audit every file, extract knowledge into target docs, track what needs code work as tasks.

### reconciliation-csv-integration — [2026-05-22_reconciliation-csv-integration/](2026-05-22_reconciliation-csv-integration/)
* priority: high
* scope: pipeline
* status: in-progress
* summary: Integrate the OpenRefine 6-column reconciliation CSV into Phase 32 as the highest-confidence manual deduplication tier superseding automated strategies.

### guest-catalogue-completion — [2026-05-22_guest-catalogue-completion/](2026-05-22_guest-catalogue-completion/)
* priority: high
* scope: pipeline
* summary: Add the ~8,336 unmatched canonical entities to analysis output as a separate unmatched_persons.csv alongside the 640-row Wikidata-matched guest_catalogue.csv.

### prior-work-comparison — [2026-05-22_prior-work-comparison/](2026-05-22_prior-work-comparison/)
* priority: medium
* scope: pipeline
* summary: Compare this project against three prior works (Arrrrrmin, Spiegel, Omar/LanzMining) with a high-level summary table and a data-comparison analysis notebook.

### phase-orchestration-drift — [2026-05-22_phase-orchestration-drift/](2026-05-22_phase-orchestration-drift/)
* priority: high
* scope: pipeline
* summary: Fix the Phase 31/32 orchestration drift where run_phase31/run_phase32 wrappers violate notebook-first principles; each logical step must become a notebook cell.

### wikidata-v4-rework — [2026-05-22_wikidata-v4-rework/](2026-05-22_wikidata-v4-rework/)
* priority: medium
* scope: architecture
* status: in-progress
* summary: Design and implement a single rule-driven graph expansion engine replacing Phase 2.1's patchwork of inter-dependent repair modules.

### phase-50-analysis-implementation — [2026-05-22_phase-50-analysis-implementation/](2026-05-22_phase-50-analysis-implementation/)
* priority: medium
* scope: pipeline
* summary: Implement the full Phase 50 analysis and visualization suite: property distribution stats, cross-property charts, hierarchy visualizations, bug fixes in 50_analysis.ipynb, and output management. Contains 16 implementation sub-tasks and 7 bug fix sub-tasks.

### transcript-acquisition-pipeline — [2026-05-22_transcript-acquisition-pipeline/](2026-05-22_transcript-acquisition-pipeline/)
* priority: low
* scope: pipeline
* summary: Build a Whisper-based German transcription pipeline for ZDF talk show episodes, enabling content-level analysis (guest speaking time, named entity co-mentions).

---

## Notes

`documentation/tasks/2026-05-21_GitHub_ready/tasks/00_index.md` tracks the GitHub-readiness sub-tasks (T01–T16) within that large task folder. It is internal to that task, not a replacement for this index.
