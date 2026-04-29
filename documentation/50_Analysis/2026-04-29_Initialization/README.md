# Analysis Initialization
The goal of this folder is to provide a structure to the coming Analysis. The task is to read the `00_immutable_input.md` and create an analysis design from it, then implement this. To do so:
* Raise any questions that require clarification, e.g.
  * Refining Terminology
  * Defining Data sources,
  * etc.
* Only when all questions are resolved: Write a Design specification in Markdown.
* Only when this Design specification is without unresolved Clarification: Implement.
* When Implementation is done: Conclude with a final evaluation and keep track of identified issues in a Markdown document and fix them.
* At all times: Use this README to provide a very minimalistic overview of the folder state and next tasks. Don't duplicate - just reference.

The `00_immutable_input.md` is to be kept verbatim and unchanged. Downstream documentation (01_..., 02_...) needs to be verified against upstream concepts so that concept drift is minimized. This verification is to be done and documented once when moving from step to step, and once as a comprehensive validation at the very end, verifying consistency with every document from 00 to XX.

---

## Current State (2026-04-29)

**Step completed:** Design specification — ready for implementation.

| File | Status | Purpose |
|------|--------|---------|
| `00_immutable_input.md` | ✅ Authoritative | Analysis goals, building blocks, minimum analysis combinations |
| `01_existing_context.md` | ✅ Done | Data sources, approach, reference to open-tasks |
| `02_open_tasks_triage.md` | ✅ Done | All open tasks categorized: immediate / deferred / time-permitting; data access strategy |
| `03_design_spec.md` | ✅ Done | Full analysis design: data model, role separation, Steps A–D, notebook structure |
| `04_analysis_angle_structure.md` | ✅ Done | Property type taxonomy, generic function signatures (F1–F5), mapping C1–C8 to functions |
| `open-tasks.md` | 🔄 Active | Analysis-specific tasks: TASK-A01 (resolved), TASK-A02 through TASK-A05 |

**Next step:** Resolve TODO-040 (guest classification audit), then implement `50_analysis.ipynb` cell by cell per `03_design_spec.md` and `04_analysis_angle_structure.md`.

**Immediate blockers before first analysis output:**
1. **TODO-019** — Build complete person catalogue from `reconciled_data_summary.csv` (see `03_design_spec.md` Step A)
2. **TODO-039** — Role-based classification: data-driven via `guest_role` field; no person is dropped, only sorted. When Markus Lanz appears as a guest on another show, he is a guest there. See `03_design_spec.md` §2.1.
3. **TODO-040** — Guest classification audit (Elon Musk case) — see explanation below
4. **TODO-027** — Verify mention_category propagation; approach: compare IDs across files; audit the difference

**TODO-040 explained — Guest classification audit:**  
Fernsehserien.de and ZDF source data capture two distinct types of person mentions: (a) persons who **physically appeared** as guests, and (b) persons who were **discussed as topics** (e.g. "Trump's policies" discussed without Trump being present). Both types can end up in the person records after Phase 1 and 3.

Elon Musk is the canonical test case: he was carried forward from an early Wikidata discovery run and is **not matched to any episode** in any of the three sources (Wikidata episodes, ZDF PDFs, Fernsehserien.de). He should never appear in the guest catalogue.

Step A produces a `person_catalogue_unclassified.csv` — persons with no episode match in any source. If the classification logic is correct, Musk appears there, not in the guest list. The audit is: run Step A, check which list he is in. If he is in the guest list, the classification has a defect affecting all statistics.

The broader check: take a random sample of 20 entries from the unclassified list and verify they are all genuinely unmatched (not missed guests). If systematic misclassification is found in either direction, raise a blocker.