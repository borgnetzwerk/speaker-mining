# Migration Commit Readiness (v3)

**Date:** 2026-04-02  
**Purpose:** Final gate checklist before creating the migration commit.

---

## 1. Scope Of This Gate

This checklist is for the migration commit that introduces and validates the v3 JSONL event-sourcing runtime.

It does not replace implementation docs. It is the release-owner checklist for:
- commit hygiene,
- validation confidence,
- migration policy compliance,
- explicit blocker tracking.

---

## 2. Current Validation Snapshot

Latest executed command:
- `.venv/Scripts/python.exe -m pytest speakermining/test/process/wikidata -q`

Latest observed result:
- `130 passed, 0 failed`

Open failing tests:
1. None.

Gate implication:
- Commit gate is **green**.

---

## 3. Pre-Commit Checklist

Mandatory:
- [x] Migration-critical test suite is green (`130 passed, 0 failed`).
- [x] `06_MIGRATION_VALIDATION_REPORT_TEMPLATE.md` populated for the final run.
- [x] Any non-empty `new_regression` count is explicitly approved or fixed.
- [x] `20_evaluation#3.md` remains the canonical evaluation artifact (older evaluation drafts are either retained intentionally or archived).
- [x] Documentation status fields reflect implementation-complete state.

Recommended hygiene:
- [x] Notebook output noise reviewed in `speakermining/src/process/notebooks/21_candidate_generation_wikidata.ipynb` (transient outputs intentionally retained for traceability in this migration session).
- [x] Large generated lists (for example `31_deletable_json_files_raw_queries.md`) are intentionally included and referenced from cleanup docs.
- [x] Commit message clearly scopes migration phases included.

---

## 4. Suggested Commit Structure

Single migration commit (if all green):
- `feat(wikidata): finalize v3 event-sourcing migration and validation docs`

Or split into two commits:
1. `feat(wikidata): finalize v3 event store, handlers, and migration wiring`
2. `docs(wikidata): finalize migration evaluation, validation, and cleanup guidance`

---

## 5. Final Go/No-Go Rule

Go:
- Full test gate green, or signed waiver for known failures.
- Validation report completed with mandatory mismatch classification.
- No unresolved critical migration regressions.

No-Go:
- Any unwaived failing tests in migration-critical suite.
- Missing final validation report.
- Documentation still claiming pre-implementation state.
