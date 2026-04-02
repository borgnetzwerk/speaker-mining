# Migration Validation Report Template (v3)

**Report ID:** `<YYYYMMDDTHHMMSSZ>__<short_slug>`  
**Date (UTC):** `<YYYY-MM-DD>`  
**Author(s):** `<name>`  
**Phase:** `<phase-1|phase-2|phase-3>`  
**Scope:** `<code paths / dataset / run mode>`

---

## 1. Validation Context

- Migration commit range:
  - from: `<git sha>`
  - to: `<git sha>`
- Dataset / input snapshot:
  - `<dataset id or path>`
- Runtime mode:
  - `<append|restart|revert|other>`
- Environment:
  - Python: `<version>`
  - OS: `<os>`

---

## 2. Validation Commands

List all commands used for validation.

```bash
# Example
python -m pytest speakermining/test/process/wikidata -q
```

Results summary:
- Tests passed: `<n>`
- Tests failed: `<n>`
- Runtime checks passed: `<n>`
- Runtime checks failed: `<n>`

---

## 3. Core v3 Quality Gates

- Event integrity (append-only, parseable, checksums): `<pass|fail>`
- Sequence continuity across chunks: `<pass|fail>`
- Boundary-event canonical chain validity: `<pass|fail>`
- Handler replay determinism: `<pass|fail>`
- Resume/recovery correctness: `<pass|fail>`
- Projection rebuild completion: `<pass|fail>`

Notes:
- `<details>`

---

## 4. Mismatch Inventory (Mandatory)

Every observed mismatch must be listed and classified using one of the required classes.

Required classification values:
- `preserved_behavior`
- `intentional_low_hanging_fix`
- `known_unresolved_legacy_issue`
- `new_regression`

### 4.1 Mismatch Table

| mismatch_id | area | artifact_or_behavior | old_value_summary | new_value_summary | classification (mandatory) | severity | rationale | owner | action |
|---|---|---|---|---|---|---|---|---|---|
| MM-001 | `<module>` | `<artifact>` | `<summary>` | `<summary>` | `<required value>` | `<low|medium|high|critical>` | `<why this class applies>` | `<name>` | `<fix|accept|defer>` |

### 4.2 Classification Totals

- preserved_behavior: `<n>`
- intentional_low_hanging_fix: `<n>`
- known_unresolved_legacy_issue: `<n>`
- new_regression: `<n>`

Rule:
- Any non-zero `new_regression` count blocks rollout until resolved or explicitly waived by decision owner.

---

## 5. Legacy-Issue Handling

Document known unresolved legacy issues observed in this run and why they do not block migration.

| issue_id | reference | observed_in_run | impact | mitigation | follow-up tracker |
|---|---|---|---|---|---|
| LEG-001 | `<link>` | `<yes|no>` | `<summary>` | `<summary>` | `<tracker item>` |

---

## 6. Low-Hanging Fixes Included

List low-risk fixes delivered as part of migration work.

| fix_id | area | change_summary | risk_assessment | validation_evidence |
|---|---|---|---|---|
| FIX-001 | `<module>` | `<summary>` | `<low risk rationale>` | `<tests/logs>` |

---

## 7. Decision

- Rollout decision: `<approve|approve_with_conditions|reject>`
- Decision owner: `<name>`
- Decision timestamp (UTC): `<timestamp>`

Decision notes:
- `<notes>`

---

## 8. Follow-up Actions

1. `<action>`
2. `<action>`
3. `<action>`

---

## 9. Attachments

- Validation logs: `<path>`
- Diff/report artifacts: `<path>`
- Determinism comparison outputs: `<path>`
- Recovery simulation outputs: `<path>`
