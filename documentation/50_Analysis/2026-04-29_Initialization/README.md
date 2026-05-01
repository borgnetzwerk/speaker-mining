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

## Current State (2026-04-30)

**Step completed:** Full notebook run successful; TASK-A06 resolved; TASK-A07–A11 defined; output rewiring and dataset prep in progress.

| File | Status | Purpose |
|------|--------|---------|
| `00_immutable_input.md` | ✅ Authoritative | Analysis goals, building blocks, minimum analysis combinations |
| `01_existing_context.md` | ✅ Done | Data sources, approach, reference to open-tasks |
| `02_open_tasks_triage.md` | ✅ Done | All open tasks categorized: immediate / deferred / time-permitting; data access strategy |
| `03_design_spec.md` | ✅ Done | Full analysis design: data model, role separation, Steps A–D, notebook structure |
| `04_analysis_angle_structure.md` | ✅ Done | Property type taxonomy, generic function signatures (F1–F5), mapping C1–C8 to functions |
| `05_implementation_context.md` | ✅ Done | Data source decisions, join strategy, role taxonomy, property fetch coverage, run findings |
| `open-tasks.md` | 🔄 Active | TASK-A01/A06/A07/A08 resolved; TASK-A02–A05/A09–A11 open |

**Next step:** Re-run `50_analysis.ipynb` (now 27 cells). Cell 5b fetches missing Wikidata data (~15 min first run). Cell 22b copies reference data to `reference/`. Verify all outputs land in `data/50_analysis/` with correct subdirectory structure.

**Post-full-run status (2026-04-30):**
- ✅ TASK-A06 resolved: `all_outlink_fetch` implemented in `entity_access.py`; notebook cell 5b fetches ~4,464 missing QIDs (~15 min first run); `begin_request_context` / `end_request_context` correctly wired; confirmed running successfully.
- ✅ TODO-040 audit passed: all 3,238 unclassified persons have `role=incidental`, `appearance_count=0`. No systematic misclassification.
- ✅ TODO-027 completeness check ran: 6,011 pairs in reconciled not matched in episode_guests (name-join gap); 7,731 in episode_guests not in reconciled (unreconciled Fernsehserien persons). Both are acceptable gaps.
- ✅ Role distribution: 5,738 guests, 3,238 incidental, 17 moderators, 5 staff.
- ✅ Occupation/party Cartesian-product bug fixed in `gen_50_analysis.py` (zip-before-explode pattern).
- ℹ Phoenix Runde: no episode data in `episode_metadata_normalized.csv` — data gap from Phase 1, not a notebook bug. See `05_implementation_context.md` §5.
- ✅ TASK-A07 resolved: all outputs now go to `data/50_analysis/all/`, `persons/`, per-show `<show_id>/`.
- ✅ TASK-A08 resolved: notebook cell 22b copies non-human reference data to `reference/`; person catalogue isolated in `persons/`.