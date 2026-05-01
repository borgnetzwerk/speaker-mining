# Analysis Initialization — Open Tasks

Tasks specific to the Phase 5 analysis design and implementation. For pipeline-wide tasks, see `documentation/ToDo/open-tasks.md`.

---

## TASK-A01 — Meta-level structure for analysis angles
**Priority:** Immediate — prerequisite for implementation  
**Status:** ✅ Resolved — see `04_analysis_angle_structure.md`

What was missing was a document that finds the right solution to: a) capture, b) document, and c) scale the full space of analysis angles properly. The current combinations in `03_design_spec.md` (C1–C8) are now structured through the property type taxonomy in `04_analysis_angle_structure.md`.

**Core insight (resolved):** Properties are classified into four types (A: categorical multi-value hierarchical, B: categorical single-value, C: continuous/numeric, D: temporal), each mapping to generic parameterized functions (F1–F5). Gender is treated as categorical (Type B) — the value set is enumerated from data, never hardcoded as binary. New analyses are added by identifying property type + function type, then calling the generic function with appropriate parameters.

---

## TASK-A02 — Hierarchy visualizations for occupation/role data
**Priority:** Immediate  
**Status:** Open  
**Links:** Builds on TODO-025 patterns; implements in `50_analysis.ipynb` (not `51_visualization.ipynb`)

The patterns developed in `21_wikidata_visualization.ipynb` (Sunburst, Sankey, hierarchy view) are exactly what Phase 5 needs for occupation and role data. These were prematurely deferred — they are required now.

**Required outputs:**
1. Sunburst diagram of occupations — one combined (all shows), one per talk show; 5% "other" cutoff for subclasses; innermost ring = top-level occupation classes
2. Sankey diagram of occupation hierarchy — same scope rules as sunburst
3. Hierarchy view of occupations and roles
4. All diagrams exported as PNG + PDF to `data/50_analysis/visualizations/`

**Reference:** `speakermining/src/process/notebooks/21_wikidata_visualization.ipynb` as learning set. Multi-parent strategy needed for subclasses with multiple superclasses (primary-parent assignment or proportional count split).

**Known issues (2026-04-30):**
- The sunburst currently present in the analysis notebook is **in the wrong place**: visualizations belong in a dedicated visualization step, not the analysis notebook.
- The sunburst hierarchy is **broken**: the center section shows "Person" (meaningless), and each top-level class has only one child which is itself. Must be fixed before publishing any hierarchy visualization.
- **Q488205** (Singer-Songwriter) and similar occupation QIDs are not yet `class_hierarchy_resolved` — some QIDs are also not yet fully fetched. This is a MUST-fix before hierarchy visualizations can be correct. Use `entity_access.basic_fetch` and Phase 2 class hierarchy tools accordingly; do not bypass the Phase 2 interfaces.
- The "two kinds of Schauspieler, two kinds of teacher" visible in top-10 occupation lists is a direct symptom of this incomplete class hierarchy resolution.
  - **Clarification:** We should be interested in both: one Top 10 that is flat, just as they occur (e.g. biology teacher) - and one resolved to their top-level class (educational profession), or a mid-level more meaningful one (teacher).
- Visualizations should only be finalized once all immediate/critical tasks are resolved. Data is otherwise ready.
- Note on taxonomy: analysis categories are derived from underlying data type (scalar, temporal, categorical, hierarchical) — visualizations should match this taxonomy.
  - **Clarification:** This is also why we added `documentation/50_Analysis/2026-04-29_Initialization/04_analysis_angle_structure.md`. It should be used to structure visualization (and actually: analysis as well. Both are two sides of the same coin.)

---

## TASK-A03 — Page rank node visualization for Phase 5
**Priority:** Immediate  
**Status:** Open  
**Links:** Builds on TODO-032 patterns; implements in `50_analysis.ipynb`

A node-graph visualization of page rank is needed for Phase 5 analysis outputs:
1. Node graph for all person instances (nodes sized/colored by rank score)
2. Node graph for all classes
3. Combined view

All exported as PNG + PDF to `data/50_analysis/visualizations/`.

---

## TASK-A04 — Property value statistics table (generic pattern)
**Priority:** Immediate — user confirmed: "We really need these analysis tables"
**Status:** Open

A generic function that produces a per-value statistics table for any property:

| Property value | min/episode | max/episode | mean over episodes | std dev | median | episode % without | total appearances | unique persons |
|---|---|---|---|---|---|---|---|---|

This pattern applies to occupation, gender, age, party, and any other property. The same function parameterized by column name produces all variants.

**Interesting derived analyses:**
- Where is the gap between `unique` and `total` largest? (repeat-invite bias)
- How many episodes have zero women? Zero men? (representation gaps)
- Where is the median of "how many values does one person have" == 1, and what are the outlier multi-value cases? (e.g. singer+songwriter combinations)

**Second pass — per-property analysis (independent of "per episode"):**

For every property, produce a standardized analysis covering:
- Average number of values per entity
- Times a value was not present / empty
- Reference analysis: how many entities have references; most common reference properties + their most common values; unique reference properties + their unique values
- Qualifier analysis: how many entities have qualifiers; most common qualifier properties + their most common values
- Most common top-X values
- Most common combinations within the same property (+ unique combinations)
- Most common combinations between this property and each other property, one column per such property (+ unique combinations)

Note: the last two ("most common combinations") may each require their own dedicated table to be done correctly and meaningfully. This could warrant its own analysis and may feed into predictive analysis.

This is a standardized analysis that should be applicable to all properties.

---

## TASK-A06 — Full-fetch Wikidata property data for all guest QIDs
**Priority:** Immediate — prerequisite for meaningful property analysis  
**Status:** ✅ Resolved — fetch cell implemented and confirmed working; notebook ran successfully

Of 5,374 unique QIDs in `reconciled_data_summary`, only ~910 guests have cached Wikidata property data (P21/P106/P102/P108/P569/P19). The remaining ~4,464 have QIDs but no full entity doc in any cache — all their properties appear as "unknown" in the current analysis outputs.

`entity_access.ensure_basic_fetch()` is **not sufficient**: it fetches only labels + P31/P279. Full property data requires `entity_access.all_outlink_fetch(qid, repo_root)` — the Phase 2 public interface for full claims retrieval, cache-first, without inlinks expansion. Do not call `full_fetch.full_fetch()` directly from Phase 5 code.

**Action:** Implement a dedicated cell in `50_analysis.ipynb` (after data load, before Step A property extraction) that:
1. Identifies which reconciled QIDs have no cached full entity doc (`get_cached_entity_doc` returns None)
2. Fetches them via `entity_access.all_outlink_fetch()` at ~10 req/s
3. Resets the entity_access cache index after the fetch run
4. Supplements `qid_label` with labels from newly fetched docs
5. Reports coverage before and after

The cell is idempotent: cache hits are skipped immediately. First run estimated ~15 min for ~4,500 fetches; subsequent runs ~5–30 sec (index priming from event_store.jsonl).

**Implementation note:** `full_fetch` is in `process.candidate_generation.wikidata.full_fetch`. The source_step chain: `full_fetch` → writes `"entity_fetch"` → `get_cached_entity_doc("entity")` maps to `"entity_fetch"` in cache.py `_latest_cached_record`. Fully wired.

**Session-end state note (2026-04-30):** `all_outlink_fetch` is implemented and exported from `entity_access.py`. Notebook cell `nb50_c05c` calls `begin_request_context` / `end_request_context` correctly. Notebook regenerated (25 cells). Root cause of initial 0-fetch / 4,725-failed run: `begin_request_context` was missing — fixed before session end. Notebook confirmed running successfully. CRITICAL: Phase 2 Wikidata infrastructure has silent failure modes — `cache.py::_http_get_json` raises `RuntimeError` if `begin_request_context` has not been called; `full_fetch.full_fetch()` catches this silently and returns `None`. Read `cache.py`, `event_log.py`, `event_writer.py`, and `entity_access.py` in full before touching Phase 2 code.

---

## TASK-A05 — Additional analysis angles (time-permitting)
**Priority:** Time-permitting  
**Status:** Open

Additional analysis types to implement after the core C1–C8 set:

**Subset dominance analysis:**  
Which values of property A explain the over-presence of a value from property B? Example: if removing politicians from the guest list drops the journalist share from 80% to 5%, that subset is load-bearing for the journalist statistic. Also: identify individuals who over-represent their group (one female scientist invited 100× while others are invited 5×).

**Cross-show guest presence:**  
Which guests appear across multiple shows vs. only one? Which are over-concentrated in one show relative to others? Which are balanced?

**Career arc patterns:**  
Identify guest trajectory types (provisional terminology):
- "Shooting star": many invitations in quick succession, rarely before or after
- "Evergreen": frequently invited over a long time span

**Property co-occurrence:**  
Which property value combinations are most common (e.g. journalist+politician, singer+songwriter)? Predictive analysis: does having property value X predict property value Y?

**Temporal chunking:**  
Customs have changed over time. Analyze data by year and decade: how do gender, occupation, party distributions shift across time periods? Track episode and guest counts per show per year/decade to contextualize trends.

**Party affiliation history:**  
Differentiate party membership more precisely over time. Example: test for explicit SED members; show party affiliation history for guests with multiple affiliations.

---

## TASK-A07 — Output folder rewiring + structure
**Priority:** Immediate  
**Status:** ✅ Resolved — implemented in `gen_50_analysis.py`; notebook regenerated (27 cells)

All analysis outputs now use `data/50_analysis/`. Directory structure implemented:
- `data/50_analysis/all/` — combined all-shows analysis (occurrence matrix, distributions, summary, sunburst)
- `data/50_analysis/<show_id>/` — per-show occurrence matrices (e.g. `markus_lanz/occurrence_matrix.csv`)
- `data/50_analysis/persons/` — GDPR-sensitive person catalogue (see TASK-A08)
- `data/50_analysis/reference/` — non-human Wikidata reference data (see TASK-A08)

`gen_50_analysis.py` defines `ALL_DIR`, `PERSONS_DIR`, `REF_DIR` off `OUTPUT_DIR = Path("data/50_analysis")`.

---

## TASK-A08 — Self-contained analysis dataset preparation (GDPR-aware)
**Priority:** Immediate  
**Status:** ✅ Resolved — implemented as notebook cell 22b in `gen_50_analysis.py`

`data/50_analysis/` is now a self-contained dataset directory:

- **`all/`** — all combined analysis outputs (occurrence matrix, distributions, summary, sunburst)
- **`<show_id>/`** — per-show occurrence matrices, one subdirectory per show
- **`persons/`** — GDPR-sensitive: `guest_catalogue.csv`, `guest_catalogue_unmatched.csv`, `person_catalogue_unclassified.csv` — isolate from public releases by excluding this subdirectory
- **`reference/`** — non-human Wikidata data copied from Phase 2 archive: classes, class_hierarchy, instances, core_classes, core_roles, core_organizations, core_broadcasting_programs

The dataset prep cell (nb50_c22b) copies reference data on each run (idempotent). Notebook must be re-run to populate these directories.

---

## TASK-A09 — Age distribution data quality investigation
**Priority:** Immediate — data quality blocker before publishing age results  
**Status:** Open

The age distribution output shows implausible ages: a ~3-year-old and a ~117-year-old guest. Investigate:
1. Which canonical persons are these? What QIDs / canonical_labels?
2. Are their birth years correct in Wikidata (P569)?
3. Are the episode premiere dates correct for those appearances?
4. Is the formula correct: `appearance_age = premiere_year − birth_year`?
5. Fix if data/calculation error; document as a data limitation caveat if confirmed real.

---

## TASK-A10 — Summary statistics improvement + "Most relevant person"
**Priority:** Immediate  
**Status:** Open

Two deficiencies in current analysis outputs:
1. **Numbers missing from top-X lists**: every top-X list must show the count that placed each entry there. A top-occupations list without person_count is nearly meaningless.
2. **No "most relevant person" metric**: define and implement a "most relevant person" output. Candidate metrics: highest appearance_count, widest cross-show presence, highest page rank score, or a composite.

---

## TASK-A11 — Intermediate implementation vs specification evaluation
**Priority:** Immediate  
**Status:** Open

Systematically check the current implementation against specifications in `00_immutable_input.md`, `03_design_spec.md`, `04_analysis_angle_structure.md`:
- What is correctly implemented? → mark `fully_implemented`
- What is not yet implemented? → create tasks or update existing ones
- What is wrong or producing incorrect outputs? → create bug tasks
- What has further potential to be implemented, discussed, or refined?

---

## TASK-A12 — Structural consistency enforcement: analysis angles + visualization taxonomy
**Priority:** Immediate  
**Status:** Open

The analysis angle taxonomy (property types A/B/C/D, function types F1–F5) and its visualization mapping (§6 of `04_analysis_angle_structure.md`) must be consistently applied across all documentation and all notebooks. This is a documentation-and-compliance task, not an implementation task.

**Two compliance checks required:**

**1. Documentation consistency:**
- Every analysis angle described anywhere (open-tasks.md, 03_design_spec.md, 02_open_tasks_triage.md, 05_implementation_context.md) must reference the correct property type (A/B/C/D) and function type (F1–F5).
- No analysis angle may be described only in narrative terms without a function-type label.
- The §3 mapping table in `04_analysis_angle_structure.md` must list every analysis angle currently implemented or planned.
- The §6 visualization mapping table must cover every F-type and match `visualization-principles.md`.

**2. Notebook structural consistency:**
- `50_analysis.ipynb`: each Step C cell must open with a comment identifying its function type (e.g. `# F1 — gender distribution`). Cells that implement F1 must follow the generic `analyze_distribution` signature from §4; F3 cells must follow `analyze_cross_tab`, etc.
- `51_visualization.ipynb`: each chart cell must open with a comment identifying its function type and the analysis it visualizes. Chart types must match the §6 mapping table. PALETTE and helpers must be imported from the setup cell, never redefined inline. Every chart must call `save_fig()`.
- Future analysis notebooks must follow the same structural pattern: F-type label in cell heading, generic function call, chart type from §6 mapping.

**Scope:** documentation review + in-notebook comment additions. No new analysis or visualization logic required.

---

## TASK-A13 — Unclassified persons episode-link investigation
**Priority:** Time-permitting (after visualizations resolved)  
**Status:** Open

215 canonical persons have `match_strategy=wikidata_person_only_baseline` and no episode link (all `unresolved` tier). At least one confirmed false negative: Marie-Agnes Strack-Zimmermann (Q15391841) appears in multiple episodes but has no fernsehserien_de_id link.

This is a large-scale, potentially manual search task. Approach:
1. Export the 215 persons with QIDs (all have `wikidata_id`)
2. For each person: check Fernsehserien.de episode pages for name matches
3. If a match is found: add or correct the `fernsehserien_de_id` link in the reconciliation data
4. Re-run Phase 31 → Phase 32 → Phase 5 for any corrected entries

**Definition of done:** All 215 persons have been individually verified. True missing-link cases have been corrected upstream. Remaining persons confirmed as genuinely unlinked (e.g. discovered via Wikidata graph but never appeared in any scraped episode) are documented as such.

**Note:** Can be done manually or with an agent without budget limit. Volume: 215 persons.
