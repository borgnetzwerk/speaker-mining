# Wikidata TODO Tracker

Date created: 2026-03-31
Scope: Wikidata candidate-generation and graph-quality tasks only

## Status Legend

- [ ] not started
- [~] in progress
- [x] completed

## Migration Triage Policy (v3)

- Preserve behavior that is already working in v2.
- Fix low-hanging issues when implementation is localized and low risk.
- Do not block migration rollout on known unsolved legacy issues.
- Validate v3 primarily on its own correctness guarantees (event integrity, determinism, recovery, handler correctness).
- When comparing v2 and v3 outputs, classify mismatches as:
  1. preserved behavior
  2. intentional low-hanging fix
  3. known unresolved legacy issue
  4. new regression (must fix before rollout)

## Priority Items

### WDT-001: Re-evaluate prior eligibility decisions when class lineage improves

- Status: [ ]
- Priority: P0
- Owner: unassigned
- Problem:
  Nodes previously marked as not eligible may become eligible once new subclass paths to core classes are discovered.
- Requirements:
  1. Recompute eligibility on all persisted known nodes each integrity pass.
  2. Detect state transitions from ineligible -> eligible.
  3. Trigger expansion for newly eligible, not-yet-expanded nodes.
  4. Persist audit evidence for each transition.
- Acceptance criteria:
  1. A node that becomes connected via `P279` to a core class is reclassified within the next integrity pass.
  2. The node is expanded in that same pass if not already expanded.
  3. A persistent diagnostics record captures old/new status and evidence path.

### WDT-002: Persist reclassification diagnostics for longitudinal analysis

- Status: [ ]
- Priority: P0
- Owner: unassigned
- Problem:
  We need durable evidence to identify recurring integrity failures and code hotspots.
- Requirements:
  1. Write per-run diagnostics artifacts that include all eligibility transitions.
  2. Include node id, previous reason, new reason, path-to-core-class, run id, and timestamp.
  3. Keep output append-only at run granularity.
- Acceptance criteria:
  1. Each run produces a transition artifact when transitions occur.
  2. Artifacts are stored in a stable path under `data/20_candidate_generation/wikidata/node_integrity`.
  3. Documentation artifacts are mirrored under `documentation/context/node_integrity`.

### WDT-003: Add regression tests for reclassification edge cases

- Status: [ ]
- Priority: P1
- Owner: unassigned
- Problem:
  Reclassification behavior can silently regress if not covered by tests.
- Requirements:
  1. Add tests for delayed class discovery (`Q5` style path discovered later).
  2. Add tests for no-op integrity pass when no transition occurs.
  3. Add tests that prevent duplicate expansion of already expanded nodes.
- Acceptance criteria:
  1. Tests fail when reclassification logic is disabled.
  2. Tests pass when integrity pass reclassifies and expands correctly.

### WDT-004: Data is wrongly fetched for all langauges, despite us only needing german, english and default.
* by default, when accessing wikidata, only the "default for all langauges" should always be loaded
* additional languages need to be explicitly specified - labels, descriptions, aliases and alike in a language that is not specified should never be pulled
* The goal would be an initial specification of required languages. This should be a list where the user can easily change any language from false to true. By default, every language should be set to false. If this state is loaded, it should throw an error "Please define at least one language".
  * For our case, every run will only proceed with "en" and "de". Still, the user should specify exactly this themselves.

### WDT-005: Not only default language aliases are added, but also all others
* There seems to be a bug in the current implementation of alias appending (see `documentation\context\findings-assets\wrong_alias_appending.csv`)
  * The intention was the following:
    * we fetch the label, description and aliases for our specified languages 
      * currently: 2 languages, "en" and "de", so we would have:
        * label_en
        * desciption_en
        * alias_en
        * label_de
        * desciption_de
        * alias_de
    * We then also fetch the "default for all languages"
      * for every specified language label and description field, we check if its empty. for example:
        * label_en: empty -> replace with "default for all languages" label
        * desciption_en: not empty -> don't replace with "default for all languages"
      * for the alias fields, we just append the alias from "default for all languages"
        * alias_en: ["...", "..."] -> ["...", "...", "first_alias_form_default_for_all_languages", "second_alias_form_default_for_all_languages", ...]
  * instead of that intended behaviour, all language alias are appended to all aliases. This is wrong.




## Notes

- This tracker is dedicated to Wikidata workflow internals and avoids overlap with OpenRefine/Wikidata Reconciliation Service terminology.


