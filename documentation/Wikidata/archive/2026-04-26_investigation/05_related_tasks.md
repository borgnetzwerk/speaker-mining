# Notebook 21 Redesign — Related Open Tasks and Findings
> Generated: 2026-04-26  
> Purpose: Identify all open tasks and findings that must be considered in the redesign so no known shortcoming is accidentally re-introduced or left out of scope.

---

## Framing: What We Are Doing

**This investigation IS TODO-044.**

TODO-044 ("Wikidata v4 conceptual rework") was explicitly deferred as "out of scope, document only." Its definition of done: *"Conceptual design for the rule-driven graph expansion engine is documented in documentation/workflow.md."* The note: *"The ideal is a single rule-driven graph expansion engine: find core node → apply rules → hydrate or expand linked objects → repeat. If all the logic from all the modules were to be correctly integrated into these rules — that would be the ideal state."*

The investigation documents in this folder, together with `Clarification.md`, constitute the conceptual design required by TODO-044. The redesign that follows will implement it.

**Implication:** The scope of this redesign is not a patch to Notebook 21. It is the v4 rework that was deferred. We must design it broadly enough to satisfy TODO-044's vision.

---

## Category 1 — Core Architecture (must be resolved by the redesign)

### TODO-042: Fix roles relevancy propagation
- **Status:** In-progress. Partial fix applied 2026-04-26 (`relevancy.py` + `relevancy_relation_contexts.csv`).
- **What remains:** Phase 2 re-run to verify `core_roles.json` is populated; Phase 31 re-run to verify `aligned_roles.csv` has Wikidata matches.
- **Design implication:** The fix implemented is a patch on the current architecture. The redesign must make this correct *by construction* — the rule-driven engine must handle class nodes natively, not as a special case added to a function that was instance-only.

### TODO-034: Resolve instances.csv dual-write architectural conflict
- **Status:** Open.
- **Finding:** `_materialize` writes `instances.csv` with `id` column (36,890 rows), then `run_handlers` overwrites it in InstancesHandler format with `qid` column (20,836 rows). The parquet sidecar is the only reliable comprehensive source.
- **Design implication:** In the redesign, `_materialize` must not write to any file owned by a handler. `instances.csv` is owned by `InstancesHandler`. The materializer may write to a separate artifact (e.g. `instances_full.parquet`) that is not the handler's projection. This is a concrete expression of Clarification C1.3.
    * **Clarification:** I think it is fair to say that a concept such as "_materialize" or "materializer" can just be deprecated. If we need more projections, we add more EventHandlers. If we need the projections to update, we call the EventHandler. If I understand the task of "materializer" correctly - it is fully irrelevant in an EventHandler-based system.

### TODO-038: Investigate Wikidata Node Integrity Pass performance
- **Status:** Open. The integrity pass took 1,648 seconds on first run and over 6,726 seconds on a second run without completing.
- **Finding:** This step exists because expansion can leave entities referenced in triples but not fully discovered. At 36,890 entities it iterates every known QID and every triple, making it O(entities × triples).
- **Design implication:** Clarification C6.1 already says: in a correct redesign this step should not be needed. The redesign eliminates the need for the integrity pass by ensuring that any QID referenced in a triple is discovered atomically as part of the same expansion step. If a final validation check exists, it reports only; it does not repair.

### TODO-043: Align property hydration config with relevancy propagation config
- **Status:** Open.
- **Finding:** Property hydration (P106, P102, P108, etc.) and relevancy propagation both follow the pattern: "if subject meets criteria, follow this property to hydrate/expand the object." They use different mechanisms and configs.
- **Design implication:** Both should use parallel, similarly-structured config files. The distinction is clear (hydration can target any subject; relevancy is scoped to core-class instances) but the structure should be analogous. The redesign must define both configs upfront and make them independently extensible. See `additional_input.md` batch 5 for the original note on this.
    * **Clarification:** Keep in mind the concept of "core-class instance" is no longer tht stable - sometimes, we must also look at core class subclasses, such as in the "roles" case. At the same time, we must be very careful when expanding classes, since thousands of instances will link to them. So: Be very careful this design is done right.
    * **Clarification:** Maybe this should also be a reason to begin with a very fundamental glossary of terms. What is a core class, was is a core class entity, what is "expansion", "hydration", what does "relevant" mean, etc.. We should do this to a) identify what terms we use, b) clarify what we really mean by them, c) see if we can find more descriptive and clearer names them and d) identify if concepts could be structured better (potentially deprecating some or splitting others). 

---

## Category 2 — Output Contract Requirements (what Phase 2 must produce)

### TODO-041: Respect time-sensitive Wikidata claims using episode date
- **Status:** Open.
- **Requirement:** Wikidata properties with start/end qualifiers (P102 party, P106 occupation, P39 position, P108 employer) should be evaluated against the episode's broadcast date, not the current Wikidata snapshot. A politician who left a party in 2018 should not be labeled as that party's member for a 2015 appearance.
- **Design implication:** The event store must preserve qualifier data (start/end dates) alongside the triple event itself. When writing `core_persons.json`, the output must include qualifier data so that downstream phases can filter by episode date. This is a data completeness requirement on what events are emitted and what fields are written to the core JSON files.

### TODO-025, item 1: QID label bug in Notebook 21 Cell 12
- **Status:** Open (TODO-031 fixed the symptom elsewhere; this source bug in Notebook 21 was not fixed).
- **Finding:** QID labels in Cell 12 show raw QID strings instead of entity labels.
- **Design implication:** The redesign must ensure that the entity lookup index (built by `_write_entity_lookup_artifacts`) is correctly populated from the entity store so that all QIDs appearing in output have labels. This is a correctness requirement on the lookup artifact.

### TODO-020: Occupation subclustering via P279
- **Status:** Open.
- **Requirement:** Occupation analysis should use Wikidata P279 subclass hierarchy to cluster related occupation types (e.g. "university professor" and "primary school teacher" roll up to "teacher"). This requires that `core_roles.json` / class hierarchy exports include the full subclass path, not just the leaf QID.
- **Design implication:** `class_hierarchy.csv` and the core roles output must preserve the full parent chain from leaf role to core class. The redesign must ensure this information is available in the projection, not lost during materialization.

---

## Category 3 — Operational Requirements (must inform the redesign's operational model)

### TODO-035: Extend pipeline scope beyond Markus Lanz
- **Status:** Open (low priority, but must not be made harder by the redesign).
- **Requirement:** A different show should be processable by changing a config value, not code.
- **Design implication:** The seed list (`broadcasting_programs.csv`) is already config-driven. The redesign must not introduce any hardcoded show-specific assumptions. The config file (see Clarification C4) must parameterize which `broadcasting_programs.csv` to use as seed input.

### TODO-036/037: Notebook orchestration drift + CLAUDE.md
- **Status:** Open (high priority).
- **Requirement:** Notebooks must be the orchestrators. Single-function wrappers like `run_graph_expansion_stage` that swallow all logic into one call violate the notebook-first principle.
- **Design implication:** The redesign of Notebook 21 must not produce a replacement `run_graph_expansion_stage` monolith. Step-by-step expansion logic must be represented as cells, each calling granular module functions, each with visible intermediate output. Module functions must be individually callable.

---

## Category 4 — Findings That Must Inform the Redesign

### F-012: Class Miswiring Should Be Fixed Upstream
- **Finding:** Downstream diagnostics (Phase 31) found season-like Wikidata classes entering broadcasting_program paths. A rewiring catalogue (`data/00_setup/learning_scope_registry.md`) was created as a downstream mitigation.
- **Design implication:** In a correct redesign, class miswiring is caught and fixed in Phase 2's class resolution map. The redesign must include a mechanism for operators to define forced resolution rules (override `class_resolution_map` entries) without code changes. This is related to the `rewiring.csv` concept in the current setup — it must be made first-class config.

### Finding (additional_input.md): "Our starting assumption that we look for core class instances was not even correct"
- **Finding:** For roles, what we look for are core class *subclasses*, not instances. The current pipeline was built assuming P31 (instance-of) relationships were sufficient; the roles case revealed that P279 (subclass-of) must be handled as a first-class discovery path.
- **Design implication:** The redesign must treat "instance of core class" and "subclass of core class" as two equally valid discovery paths, governed by `projection_mode` per core class. Roles use subclass mode; persons use instance mode. The engine must not default to one mode and treat the other as a special case.
    * **Clarification:** This is not that clear. It will not be a simple binary "roles uses subclass mode", but it will be a "for each class, different rules will determin what is relevant". For example, not every instance of human is a relevant guest, only those listed as "guest" in some relevant episde. We will have  guest_persons, we will have host_persons, we will roles_subclasses and we may even have role-instances. Two things are evident here: The naming convention is not clear yet (roles_subclasses puts the core class first, host_persons put it last), and the scope is also not clear yet (since I don't know if there are role instances). Ultimately, we will need a system that can meet the requirements we already know, without being overly fine-tuned to them. We got to the current state because we kept overfitting to our small set of known variables and then realised there is an exception to a rule, a false assumption, and then we needed to patch and mend and fix everything over and over again. We should not lump too much together - we should begin to list rules that can be expanded upon again and again. Once we know more about our rule-set, yes, we can start to cluster rules, maybe have some instance-only rules, maybe some class-only rules, maybe some rules that care for only links via some property and maybe others that ignore properties all together. But what we must make sure is: What we built is not overly lumping things together which we need to untangle again in a week or two when we realize we applied to many assumptions that did not hold true in the end. It is not a problem if our rules look overly complex in the beginning. It is a problem if they are fundamentally wrong, however.

### Finding (additional_input.md): Conflict patterns are ontologically interesting
- **Finding:** 1,381 conflict rows in `class_resolution_map.csv` include cases like "Arabic Speaker" resolving to both role and person. These are legitimate ontological ambiguities, not errors.
- **Design implication:** The redesign must not try to eliminate ambiguity by picking one class — it must expose it. The operator must be able to define priority or accept multi-class membership. The `rewiring.csv` override mechanism is the right pattern; the redesign must formalize it.
    * **Clarification:** This provides some context to the lengthy clarification above. There are so many vast unexpected pattern conflicts in the database. We will need to learn and adapt to them not by forcing them through our predefined conceptions, but by expanding our rule catalogue to accomodate for real world complexity.

### F-017: Wikidata String-Matching Belongs in Reconciliation, Not Candidate Generation
- **Finding:** The fallback string-matching stage in Notebook 21 is conceptually a reconciliation step, not a graph traversal step.
- **Design implication:** This reinforces Clarification C9: the fallback string-matching cells (Steps 8/9) are removed from Notebook 21. Phase 2 is graph traversal only. Any string/label-based reconciliation against Wikidata belongs in Phase 3.

---

## Consolidated Design Requirements

The following table maps every open task/finding to a concrete requirement for the redesign:

| Source | Requirement for the redesign |
|--------|------------------------------|
| TODO-044 | The redesign IS the v4 conceptual rework: rule-driven graph expansion, all logic integrated |
| TODO-042 | Class nodes (P279 subclasses) are first-class expansion targets, not a special case in relevancy |
| TODO-034 | EventHandlers own their projection files; materializer never writes to handler-owned files |
| TODO-038 | No post-hoc integrity repair step; expansion is correct by construction |
| TODO-043 | Hydration rules and relevancy rules use parallel, independently-structured config files |
| TODO-041 | Triple events must preserve qualifier data (start/end dates); core JSON output includes qualifiers |
| TODO-025 item 1 | Entity lookup index is correctly populated; all QIDs in output have labels |
| TODO-020 | Class hierarchy projection preserves full parent chain from leaf to core class |
| TODO-035 | No hardcoded show-specific assumptions; seed source is config-driven |
| TODO-036/037 | Redesigned notebook follows notebook-first orchestration; no monolith wrappers |
| F-012 | Forced class resolution overrides (`rewiring.csv`) are first-class config, not a workaround |
| Finding: class modes | P31 instance mode and P279 subclass mode are equally supported per core class |
| Finding: ambiguity | Multi-class ontological ambiguity is exposed and configurable, not silently resolved |
| F-017 + C9 | Fallback string matching is removed from Phase 2; Phase 2 is graph traversal only |
