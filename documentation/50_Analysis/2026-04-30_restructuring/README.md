# Analysis Restructuring

Fresh-start redesign of the analysis and visualization layer. See `00_plan.md` for the full four-phase execution plan.

**Approach:** Requirements → Design → Concept finalization → Prior initiative aggregation. Each phase completes before the next begins.

---

## Current State (2026-05-01)

| File | Status | Purpose |
|------|--------|---------|
| `00_plan.md` | ✅ Done | Four-phase execution plan with status |
| `00_requirements.md` | ✅ Complete | 68 requirements (REQ-G/A/C/P/U/I/T/Q/S/PER/EPS/META/H/V); all clarifications resolved |
| `01_design.md` | ✅ Complete | Full spec: 8 design principles, architecture, data model, config schemas, 8 analysis modules, 16 visualization modules, output tree, definition of done |
| `open-tasks.md` | ✅ Complete | 27 implementation tasks (TASK-B01–B27); all blockers cleared |
| `open_additional_input.md` | ✅ Clean | Awaiting new human input |
| `02_design_review.md` | ✅ Processed | Phase 4 source — fully mined; all actionable items incorporated |
| `archive/additional_input.md` | ✅ Archived | All verbatim input including Phase 2 Q&A and new input (2026-05-01) |

---

## Implementation Progress

- `data/00_setup/analysis_properties.csv`, `loop_resolution.csv`, `midlevel_classes.csv`, and `party_colors.csv` are in place as human-editable config files.
- `speakermining/src/analysis/{config,color_registry,viz_base,__init__}.py` now provides the shared analysis foundation, including runtime temporal inference and deterministic QID color assignment.
- `documentation/visualizations/visualization-principles.md` has been extended to reflect the current palette rules and reserved colors.

## Phase Status

| Phase | Goal | Status |
|---|---|---|
| 1 — Requirements extraction | Split into `00_requirements.md`, `01_design.md`, `open-tasks.md` | ✅ Complete |
| 2 — Internal gap analysis | Inspect new design; fix clear gaps; resolve all ambiguous items | ✅ Complete |
| 3 — Concept finalization | Hierarchical overview (3a) + full spec (3b) | ✅ Complete |
| 4 — Prior initiative aggregation | Inspect `2026-04-29_Initialization/`; merge learnings | ✅ Complete |

---

## Latest additions (2026-05-01, post Phase 2)

From new `open_additional_input.md` input processed today:

**Implementation principles (REQ-A01, REQ-A02):**
- REQ-A01: Notebooks orchestrate / modules contain logic / configs for user input
- REQ-A02: Visualization caching via triple checksum (input data + file exists + output checksum)

**Person-level analysis (REQ-G04, REQ-PER01–PER06):**
- REQ-G04: Guest appearance frequency distribution + Pareto
- REQ-PER01–PER06: Top guests by show, per-show top guests, individuals within category, occupation-combination individuals, birth-year individuals, person × person encounter matrix

**Episode-level analysis (REQ-EPS01–EPS02):**
- REQ-EPS01: Episode statistics + broadcast frequency calendar heatmap
- REQ-EPS02: Per-show dashboard (party sunburst + gender over time + occupation sunburst + frequency)

**LanzMining comparison:** All LanzMining visualizations either already covered by existing requirements or captured in the additions above. New task: TASK-B21 (guest freq), TASK-B22 (person-level viz), TASK-B23 (episode viz + dashboard), TASK-B20 (viz caching).

**Meta-level analysis (REQ-META01):** Source coverage and data completeness visualization — which source(s) provided data for each episode, plus completeness gap highlighting. Described as "very vital." TASK-B24 added (high priority, independent of other tasks).

---

## Phase 4 additions (2026-05-01)

From prior initiative inspection (`02_design_review.md`, `04_analysis_angle_structure.md`, `05_implementation_context.md`):

**New requirements:**
- REQ-P01: employer (P108) added to Item property list
- REQ-P07: Temporal properties flagged via `temporal_variable` column in `properties.csv`; snapshot mode default; P102/P39/P108 are seed examples, not a hardcoded list
- REQ-U10: Multi-value counting rule — each value counted independently; REQ-H05 mid-level deduplication is the sole exception
- REQ-G05: Cross-show comparison visualization (grouped bar + heatmap) for key properties
- REQ-A03: Raw individual-level tabular data in `persons/` directory; visualizations of public figures are not restricted
- REQ-META02: Property coverage dashboard — % with value, pipeline match rate, % with references
- REQ-V13: "Other" bar — light gray `#CCCCCC`, always above "Unknown"; visually distinct from Unknown `#999999`
- REQ-V14: Scalable color system — 12–16 colorblind-safe colors; specifiable (party colors); consistent per QID; wrapping acceptable; no pattern fills
- REQ-V15: Geographic choropleth map for P19 (place of birth) as primary visualization

**New design principles (01_design.md):** idempotency (P6), German-first label resolution (P7), progress reporting (P8)

**New design sections (01_design.md):** modules 3n (geo map), 3o (cross-show comparison), 3p (property coverage); definition of done; extended color palette spec in Layer 0

**New tasks:**
- TASK-B25: Define extended color palette (12–16 colorblind-safe colors), define Other/Unknown color distinction, update `visualization-principles.md`
- TASK-B26: Cross-show comparison visualizations
- TASK-B27: Property coverage dashboard

**Deferred (out-of-scope or nice-to-have):** page rank, career arc patterns, subset dominance, person property timeline, Bundestag overlay, population benchmarks, diversity metrics, seasonal patterns, interactive HTML dashboard
  * **Clarification:** Page Rank is not out-of-scope, but yes - first, we should implement everything else, then the page rank node graph - and then, everything else is post deadline.

---

## Open Questions

None.

---

## Next Step

**Implementation begins.** All four phases complete; the design is authoritative. Start with **TASK-B19** (create config files in `data/00_setup/`), then TASK-B25 (CDU-black conflict), then TASK-B01 (color registry) and TASK-B08 (viz infrastructure) in parallel. See `open-tasks.md` for the full dependency order.
