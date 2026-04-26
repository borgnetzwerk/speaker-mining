# Notebook 21 Redesign — Stage-wise Roadmap
> Created: 2026-04-26  
> Purpose: Track progress through the investigation and redesign phases. Each stage has a clear entry condition and a clear exit condition. Work should not proceed to the next stage until the exit condition of the current stage is met.

---

## Reading This Document

- ✅ = completed
- ⚠ = partially complete / in progress
- ❌ = not started
- 🔒 = blocked by an earlier item

Each stage lists its **exit condition** — the answer to "how do we know this stage is done?"

---

## Stage 0 — Investigation
**Goal:** Understand the current system well enough to design a replacement.  
**Exit condition:** All major findings documented; no critical unknowns about current behavior.

| Item | Status | Notes |
|------|--------|-------|
| Cell-by-cell analysis (`01_cell_analysis.md`) | ✅ | Step purposes, rules, issues |
| Data flow analysis (`02_data_flow.md`) | ✅ | What reads/writes what |
| Performance analysis (`03_performance_analysis.md`) | ✅ | Where the 20 minutes goes |
| Redesign goals (`04_redesign_goals.md`) | ✅ | Goals, anti-goals, constraints |
| Related tasks identification (`05_related_tasks.md`) | ✅ | All open TODOs wired in |
| Clarification.md first pass | ✅ | Sections 1–12 |
| Last run reference (`09_last_run_reference.md`) | ✅ | Final v3 run preserved; O1–O10 documented |

---

## Stage 1 — Pre-Design Scaffolding
**Goal:** Establish the vocabulary, rules, and constraints that will govern the design. Prevent concept drift from old code.  
**Exit condition:** Glossary has no unresolved ❓ terms; rules catalogue is complete; Clarification.md covers all raised concerns; old code strategy decided and documented.

| Item | Status | Notes |
|------|--------|-------|
| Old code strategy (`06_old_code_strategy.md`) | ✅ | Option 1 (Clean Archive) decided |
| Glossary first pass (`07_glossary.md`) | ✅ | All terms drafted |
| Glossary clarification ingestion | ✅ | Q3, Q4, Q8 resolved; Q2, Q7, Q9 partial |
| Known rules catalogue (`08_known_rules.md`) | ✅ | Groups A–I; ❓ rules marked |
| Clarification.md — glossary clarifications ingested | ✅ | Sections 14, 15, 16 added; C3.7, C7.3, C7.4 added |
| Glossary Q1 resolved (event type catalogue) | ❌ | Requires Stage 2 events catalogue work |
| Glossary Q2 resolved (fetch + traverse naming) | ⚠ | Partial — concept clear, naming not committed |
| Glossary Q5 resolved (class resolution trigger) | ✅ | ClassHierarchyHandler; see C7.5 |
| Glossary Q6 resolved (hydration_rules.csv structure) | ❌ | Deferred to design phase |
| Glossary Q7 fully resolved (expansion/relevancy rule overlap) | ⚠ | C7.4 documents the open question |
| Glossary Q9 resolved (projection_mode replacement) | ⚠ | Twofold + sub-projections agreed; naming TBD |
| Active Class renamed to agreed term | ✅ | `referenced_class` / `known_class` — see `11_naming_decisions.md` |

---

## Stage 2 — Design Prerequisites
**Goal:** Answer every open question that would require mid-design course corrections.  
**Exit condition:** Glossary Q1–Q9 all resolved; event catalogue drafted; no ❓ items in either glossary or rules catalogue.

| Item | Status | Notes |
|------|--------|-------|
| Decide fetch/traverse naming (Q2) | ✅ | `basic_fetch` + `full_fetch` + `expand` — see `11_naming_decisions.md` §1 |
| Decide "active class" replacement term (Q5 adjacent) | ✅ | `referenced_class` + `known_class` — see `11_naming_decisions.md` §3 |
| Design class resolution trigger in handler-driven system (Q5) | ✅ | ClassHierarchyHandler — see C7.5 |
| Design hydration_rules.csv structure (Q6) | ❌ | Column structure: subject_class? predicate? object_class? conditions? |
| Resolve expansion/relevancy rule overlap (Q7) | ❌ | Are these the same config or separate? |
| Decide projection_mode replacement approach (Q9) | ✅ | Retired — always produce both instance + subclass projections; see `11_naming_decisions.md` §5 |
| Events catalogue (`12_event_catalogue.md`) | ✅ | All event types documented; v4 names decided; `entity_basic_fetched` added as new event |
| Resolve open rules: A5, B7, C3, C7, D5, D6, E10, E11, F6, F7, G4 | ❌ | See `08_known_rules.md` for full list |

---

## Stage 3 — Design Document
**Goal:** Produce a complete, implementable specification for the v4 redesign.  
**Exit condition:** Architecture document exists; all EventHandlers named and their responsibilities defined; module layout clear; no code needed to understand the design.

| Item | Status | Notes |
|------|--------|-------|
| Architecture overview (`13_architecture_design.md`) | ❌ | Module layout, handler inventory, engine design |
| EventHandler inventory | ❌ | Each handler: what events it reads, what it writes, what projection it owns |
| Fetch engine design | ❌ | How basic_fetch/full_fetch/fetch_decision interact; event emission contract |
| Config file structure | ❌ | All parameters, format, auto-create behavior |
| Handover projection specification | ❌ | Complete list of output files; per-file schema |
| Rule config file designs | ❌ | `relevancy_relation_contexts.csv`, `hydration_rules.csv` column specs |

---

## Stage 4 — Code Setup
**Goal:** Clean slate in the working directory; old code archived; new notebook ready.  
**Exit condition:** No Category B/C/D modules in the main `wikidata/` directory; new empty notebook exists; Category A modules verified intact.

| Item | Status | Notes |
|------|--------|-------|
| Create `_v3_archive/` directory | ❌ | Under `speakermining/src/process/candidate_generation/wikidata/` |
| Move Category B modules to archive | ❌ | `materializer.py`, `expansion_engine.py`, `relevancy.py`, `bootstrap.py`, `node_store.py`, `checkpoint.py`, `node_integrity.py`, `fallback_matcher.py`, `notebook_orchestrator.py`, `triple_store.py`, `class_resolver.py` |
| Move Category C/D modules to archive | ❌ | Migration artifacts + analytics modules |
| Verify Category A modules intact | ❌ | `cache.py`, `event_log.py`, `event_handler.py`, etc. |
| Rename old notebook to `21_candidate_generation_wikidata_v3_archive.ipynb` | ❌ | |
| Create new empty `21_candidate_generation_wikidata.ipynb` | ❌ | Start clean |

---

## Stage 5 — Implementation
**Goal:** Working v4 implementation of all new modules and the new notebook.  
**Exit condition:** Cache-only run produces correct output; `core_roles.json` is populated; class resolution is incremental.

| Item | Status | Notes |
|------|--------|-------|
| Implement new EventHandler base + derivation handlers | ❌ | Uses existing `event_handler.py` base |
| Implement ClassResolutionHandler (incremental) | ❌ | The central redesign target — O(new classes) per run |
| Implement RelevancyHandler (rule-driven) | ❌ | Replaces `relevancy.py`; uses new rule config |
| Implement hydration operations (mass-capable) | ❌ | Structured fetch for label/P31/P279 in batches |
| Implement traversal engine | ❌ | Fetch + traverse + emit events |
| Implement output handlers (core_*.json writers) | ❌ | One per core class; instances + subclasses + sub-projections |
| Write new notebook cells | ❌ | Clean step sequence; no step 6.5 analog |
| Implement new config file + auto-create | ❌ | |
| Implement hydration_rules.csv loading | ❌ | TODO-043 |

---

## Stage 6 — Verification
**Goal:** Confirm the redesign solves the specific problems identified in the investigation.  
**Exit condition:** All verification items pass; key TODOs closed.

| Item | Status | Notes |
|------|--------|-------|
| TODO-042: `core_roles.json` populated after kernel restart | ❌ | Must run with v4 code |
| TODO-043: `hydration_rules.csv` replaces hardcoded predicate list | ❌ | |
| TODO-034: materializer no longer writes `instances.csv` | ❌ | Handler-owned now |
| TODO-038: node integrity pass eliminated | ❌ | Integrity-by-construction |
| Budget test: preflight uses O(new classes) not O(all) | ❌ | Step 2.4.3 equivalent must not re-walk known classes |
| Cache-only run: produces identical output to network run | ❌ | |
| Budget test: Step 6 (main expansion) gets the majority of budget | ❌ | Preflight must not dominate |

---

## Current Position

**We are in Stage 2.**

Stage 1 is complete. Stage 2 is in progress: Q1 (events catalogue) is now resolved; Q6, Q7, and the open rules remain.

### Stage 2 Progress

| Priority | Item | Status | Notes |
|----------|------|--------|-------|
| ✅ Done | Q5: ClassHierarchyHandler as class resolution trigger | Resolved C7.5 | |
| ✅ Done | Q2: basic_fetch / full_fetch / fetch_decision naming | Settled in `11_naming_decisions.md` | "expansion" fully retired |
| ✅ Done | Q9: projection_mode retired | Settled in `11_naming_decisions.md` §5 | |
| ✅ Done | Active Class renamed | `referenced_class` + `known_class` | |
| ✅ Done | Q1: Events catalogue | `12_event_catalogue.md` | All v3 types documented; v4 names decided; `entity_basic_fetched` added |
| ❌ Open | Q6: hydration_rules.csv column structure | Design proposal | Parallel to `relevancy_relation_contexts.csv` |
| ❌ Open | Q7 fully resolve: expansion/relevancy rule overlap | C7.4 design decision | Are expansion and relevancy rules the same config or separate? |
| ❌ Open | Rules: A5, B7, C3, C7, D5, D6, E10, E11, F6, F7, G4 | `08_known_rules.md` ❓ items | |

---

## Cross-Reference: Open Items by Document

| Document | Open Items |
|----------|-----------|
| `07_glossary.md` | Q6 (hydration rules config structure), Q7 (expansion/relevancy overlap) |
| `08_known_rules.md` | A5, B7, C3, C7, D5, D6, E10, E11, F6, F7, G4 |
| `Clarification.md` | C7.4 (expansion vs relevancy rule boundary) |
| `09_last_run_reference.md` | What are the 149 new QIDs from node integrity? Which 995 unexpanded seeds are priority? |
