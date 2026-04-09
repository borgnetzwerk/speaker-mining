# Wikidata Great Rework - Status Quo Closeout

Date: 2026-04-09
Scope: Candidate generation (Notebook 21, Stage A, Node Integrity, fallback, projections, checkpointing)

## Purpose

Catastrophic backup loss means the next large Wikidata run should happen only after a clean closeout and one final pre-rework commit. This document captures the current state from tracker, design docs, and open git changes.

## What Was Completed In This Wave

1. Rule contract consolidation:
   - Added canonical rule source: `documentation/Wikidata/expansion_and_discovery_rules.md`.
   - Updated migration/spec/design docs to reference one canonical eligibility contract.
2. Stage A reliability and determinism:
   - Eligibility now uses seed-neighborhood degree (`1` or `2`) and direct-or-subclass core match.
   - Added deterministic neighbor ranking before cap.
   - Append resume now scans from seed 1 and skips completed seeds.
   - Expensive materialization moved from per-seed checkpoint loop to final stage path.
3. Chunk/index lookup infrastructure:
   - Added `entity_lookup_index.csv` and `entity_chunks/*.jsonl` projection artifacts.
   - Added chunk-backed runtime lookup fallbacks in node store (`get_item`, `iter_items`).
   - Added checkpoint snapshot support for lookup index and chunk files.
4. Core-output hardening:
   - Added explicit two-hop boundary enforcement for `instances_core_*` projections.
5. Fallback config hardening:
   - `fallback_enabled_mention_types` is now required and validated in fallback runtime.
6. Backup/archive safety hardening:
   - Added delete guardrails (`safe_rmtree`, `safe_unlink`) and protected-path checks.
   - Added overwrite refusal for existing checkpoint backup dirs.

## Current Tracker Closeout State

Closed or closed-with-transfer items in `wikidata_todo_tracker.md`:

1. Fully completed and retained as resolved history:
   - WDT-001, WDT-002, WDT-004, WDT-005, WDT-006, WDT-007, WDT-008, WDT-009, WDT-010, WDT-012, WDT-017, WDT-018, WDT-019
2. Closed for this wave and explicitly transferred to Great Rework backlog:
   - WDT-011 -> GRW-001
   - WDT-013 -> GRW-002
   - WDT-014 -> GRW-003
   - WDT-015 -> GRW-004
   - WDT-016 -> GRW-005
   - WDT-020 -> GRW-006

## Design Improvements Closeout State

Status updates in `documentation/Wikidata/2026-04-09_design_improvements`:

1. Resolved:
   - 02_entity_lookup_and_chunk_infrastructure.md
   - 03_stage_a_reliability.md
   - 04_core_class_output_hardening.md
2. Unresolved and transferred to Great Rework:
   - 05_legacy_json_cutover.md -> GRW-007
   - 06_triple_events_decision.md -> GRW-008

## Rework Readiness Summary

The codebase now has stronger deterministic behavior, better safety around backup deletion, and a scalable lookup/index layer. The remaining work is concentrated in full legacy cutover, strict event-sourcing completion, long-run network efficiency, and hard runtime validation under very large refresh workloads.

All unresolved work is consolidated in:

- `documentation/Wikidata/2026-04-10_great_rework/01_rework_backlog.md`
- `documentation/Wikidata/2026-04-10_great_rework/02_additional_codebase_findings.md`
