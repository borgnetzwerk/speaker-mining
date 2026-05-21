# Notebook 21 Redesign — Old Code Strategy
> Created: 2026-04-26  
> Purpose: Decide how to handle the 37 existing Python modules in `speakermining/src/process/candidate_generation/wikidata/` before redesign work begins.

---

## The Problem: Concept Drift

When redesigning from scratch, existing code exerts gravitational pull. Old function names get reused. Old import patterns get copied. Old structural decisions get accepted without scrutiny because "it was already done that way". The investigation documents captured the goals and rules of the old system deliberately so that we can design from *those*, not from the code itself.

The question is: how do we prevent old code from drifting into the new design while still being able to consult it when implementing specific algorithms?

---

## Inventory: What Exists

The 37 modules fall into three natural categories:

### Category A — Infrastructure (cache, network, event log primitives)
These modules implement low-level capabilities that are correct, well-tested, and architecturally neutral. They should survive the redesign unchanged.

| Module | Role |
|--------|------|
| `cache.py` | Cache-first HTTP/SPARQL query caching |
| `backoff_learning.py` | Rate-limit backoff and delay learning |
| `contact_loader.py` | User-Agent / Wikidata contact info |
| `graceful_shutdown.py` | Stop handler (Ctrl-C / RuntimeError interception) |
| `heartbeat_monitor.py` | Heartbeat emission during long runs |
| `event_log.py` | Append-only JSONL chunk file management |
| `event_writer.py` | Event construction and append primitives |
| `event_handler.py` | EventHandler base class |
| `handler_registry.py` | Handler registration and dispatch |
| `schemas.py` | Event type definitions and schemas |
| `chunk_catalog.py` | Chunk file indexing and catalog |
| `checksums.py` | Event store integrity checksums |
| `entity.py` | Wikidata entity document utilities |
| `outlinks.py` | Outlink (P31 etc.) query patterns |
| `inlinks.py` | Inlink query patterns |
| `common.py` | Shared low-level utilities |
| `candidate_targets.py` | Phase 1 mention target loading |
| `runtime_evidence.py` | Runtime evidence bundle writing |
| `query_inventory.py` | Query budget tracking |
| `phase_contracts.py` | Output contract definitions |
| `contact_loader.py` | Contact info / User-Agent |

### Category B — Business Logic (redesigned from scratch)
These modules implement the high-level concepts that are being replaced. They contain the patterns identified as wrong in the investigation: monolithic materializer, checkpoint system, unconditional integrity pass, fallback string matching, ad-hoc projection writes.

| Module | Why it is redesigned |
|--------|---------------------|
| `materializer.py` | Deprecated per C1.6 — replaced by EventHandlers |
| `expansion_engine.py` (v4: `fetch_engine`) | Redesigned around event-sourced, rule-driven traversal |
| `relevancy.py` | Redesigned as a proper EventHandler with progress tracking |
| `bootstrap.py` | Redesigned; initialization logic moves into notebook cells |
| `node_store.py` | Redesigned; entity state flows through events and handlers |
| `checkpoint.py` | Deprecated per C2 — checkpoints replaced by event log continuity |
| `node_integrity.py` | Deprecated per C6 — integrity-by-construction replaces post-hoc repair |
| `fallback_matcher.py` | Removed per C9 — Phase 2 is graph traversal only |
| `notebook_orchestrator.py` | Removed per TODO-036 — monolith wrappers are the wrong pattern |
| `triple_store.py` | Redesigned; triple state is an EventHandler projection |
| `class_resolver.py` | Partially redesigned — P279 BFS algorithm is sound but the caller contract changes |

### Category C — Migration / Legacy Artifacts
These already carry "migration" or "legacy" in their names and are clearly artifacts of past versions. They are archived.

| Module | Status |
|--------|--------|
| `migration_v3.py` | Archive |
| `v2_to_v3_data_migration.py` | Archive |
| `legacy_artifact_inventory.py` | Archive |

### Category D — Analytics / Optional
These support analysis or benchmarking, not the pipeline itself. They belong in analysis notebooks, not the production module.

| Module | Destination |
|--------|-------------|
| `conflict_analysis.py` | Move to analysis notebook per C10 |
| `handler_benchmark.py` | Archive (benchmarking concern, not production) |
| `mention_type_config.py` | Keep — config loading, architecturally neutral |

---

## Options

### Option 1 — Clean Archive (Recommended)
Move all Category B, C, and D modules into `speakermining/src/process/candidate_generation/wikidata/_v3_archive/`. They remain in git history AND are immediately accessible for intentional reference. They are no longer in the Python import path — they cannot be accidentally imported. New modules are written in the `wikidata/` directory, starting clean.

**Pros:**
- Eliminates accidental import of old modules
- Old code is still one click away for intentional reference
- Git history also preserves everything
- No information is lost

**Cons:**
- Does not prevent a developer from opening an archived file and copying patterns from it
- Requires keeping the archive folder tidy

### Option 2 — Git Branch Isolation
Create a `redesign/phase2-v4` branch. Old code stays on `main` as-is. The redesign branch starts clean. Old code is accessible via `git show main:path/to/file` for intentional reference only.

**Pros:**
- Absolute clean slate on the working branch
- Old code is completely inaccessible in the working tree by default
- Standard git practice for major rewrites

**Cons:**
- Cannot merge partial improvements back to `main` easily until the redesign is complete
- If the redesign spans multiple sessions, git merge management becomes complex
- The investigation documents on `main` may diverge from the branch

### Option 3 — Full Deletion
Delete Category B, C, D modules entirely. Rely solely on git history + investigation documents as reference.

**Pros:**
- Absolute maximum concept isolation
- Forces clean-room design from documentation

**Cons:**
- Harder to recover individual algorithms (git log search required)
- High risk of accidentally re-inventing something that was already working (e.g., the P279 BFS algorithm)
- Irreversible in the working tree (though git history is safe)

### Option 4 — Inline Annotation
Keep all files but add a `# DEPRECATED: do not import — see documentation/Wikidata/2026-04-26_investigation/` header to each Category B module. No files move.

**Pros:**
- Least disruptive
- Easiest to do

**Cons:**
- Old modules remain importable — highest concept drift risk
- Does not prevent patterns from bleeding into new code during review

---

## Recommendation

**Option 1 (Clean Archive) is the recommended approach.** It eliminates the import-path risk and the IDE autocomplete risk (old symbols won't be suggested), while keeping old code accessible for intentional reference. The git history is the ultimate backup regardless.

**Execution:**
1. Create `speakermining/src/process/candidate_generation/wikidata/_v3_archive/`
2. Move Category B modules there
3. Move Category C and D modules there
4. Keep Category A modules in place
5. Keep `data/00_setup/` config files in place — they are not code, they are config
6. Keep `data/20_candidate_generation/wikidata/chunks/` entirely — the event store is immutable
7. Do NOT touch projection files in `data/20_candidate_generation/wikidata/projections/` — they can be regenerated but should not be deleted yet

The notebook `21_candidate_generation_wikidata.ipynb` should similarly be renamed to `21_candidate_generation_wikidata_v3_archive.ipynb` and a new empty `21_candidate_generation_wikidata.ipynb` created for the redesign.

---

## What Remains Accessible After the Archive

After executing Option 1, the following remains directly accessible:

- All Category A infrastructure modules (importable, no changes needed)
- All `data/00_setup/` config files
- The full event store (`chunks/`)
- All investigation documents in `documentation/Wikidata/2026-04-26_investigation/`
- All archived modules in `_v3_archive/` for intentional reference

The redesign starts from the investigation documents and the Clarification.md, not from the archived code.

---

## Decision Required

This document presents options. The decision must be made before implementation begins. Once chosen, the decision should be noted here as:

> **Decision (date):** Option 1 chosen. Reason: Fully agree with the statements above; archiving to a dedicated folder is already the established approach in this repository. We must however be extra careful to not let the old implementation influence our coding. As such, we must make very clear in our implementation plan that the new design plan is the guiding reference point, not some archived code bits.
