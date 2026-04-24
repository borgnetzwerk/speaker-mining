# Normalization Policy

> Related tracker item: TODO-016  
> Referenced from: `documentation/workflow.md`

This document defines when and how normalization is applied across pipeline phases, which transformations are stored, and which are derived at comparison time.

---

## Two Categories of Normalization

### 1. Display Normalization (stored, Phase 1)

**What it is:** transformations applied to human-readable text fields before writing to output CSV, to improve readability without changing the underlying meaning.

**Current instances:**
- Abbreviation expansion in `beschreibung` — `ehem.` → `ehemalige(r)`, `Vors.` → `Vorsitzende(r)`, etc. (`_expand_abbreviations` in `mention_detection/guest.py`)

**Why it is safe at Phase 1:**
- The original source text is preserved in the `source_text` field; the expansion is cosmetic.
- The `beschreibung` field is not used for entity matching downstream — matching uses `name`. There is no asymmetry risk.

**Rule:** display normalization may be applied in Phase 1 and stored. It must not affect any field used as a matching key.

---

### 2. Match-Time Normalization (derived, never stored)

**What it is:** a deterministic transformation applied to name strings at comparison time to produce a canonical matching key. The key is ephemeral — it is computed, compared, and discarded. It is never stored in output files.

**Current implementation:** `normalize_name_for_matching(name)` in `speakermining/src/process/candidate_generation/person.py`.

Transformations applied (as of 2026-04-23):
- Lowercasing
- Umlaut/ß normalization (`ö → oe`, `ü → ue`, `ä → ae`, `ß → ss`)
- Title prefix stripping (`Dr.`, `Prof.`, `Professor`, etc.)
- Whitespace normalization

**Rule:** match-time normalization must be applied **symmetrically to both sides** of any comparison. Normalizing only one side (e.g. ZDF names but not fernsehserien.de names) creates asymmetry that silently breaks matching. The fix is always: apply the same function to both strings at comparison time.

---

## Per-Phase Policy

| Phase | Normalization applied | Stored? | Notes |
|-------|----------------------|---------|-------|
| Phase 1 (mention detection) | Abbreviation expansion in `beschreibung` | Yes | Safe: `source_text` preserves original; `beschreibung` not used for matching |
| Phase 1 (mention detection) | `name` field — **no normalization** | N/A | Raw name stored; normalization at match time only |
| Phase 2 (candidate generation) | None stored | N/A | Wikidata labels stored as-is |
| Phase 31 (disambiguation) | `normalize_name_for_matching` as a derived match key | No | Applied symmetrically to both ZDF and Wikidata/fernsehserien.de names |
| Phase 32 (deduplication) | `normalize_name_for_matching` for `cluster_key` | `cluster_key` stored | The normalized key is stored as a convenience column; the raw `canonical_label` is always the authoritative label |

---

## The Symmetric-Both-Sides Requirement

Any comparison that uses normalized keys must normalize **both sides with the same function**. Violations produce silent false negatives (matching pairs that should cluster fail to do so).

Examples of correct usage:
```python
# Comparing ZDF name to Wikidata label — both normalized:
key_zdf = normalize_name_for_matching(zdf_name)
key_wd = normalize_name_for_matching(wikidata_label)
if key_zdf == key_wd: ...

# Deduplication cluster key — all canonical_labels normalized the same way:
remaining["_cluster_key"] = remaining["canonical_label"].apply(normalize_name_for_matching)
```

Examples of incorrect usage (do not do this):
```python
# Normalizing only one side — WRONG:
if normalize_name_for_matching(zdf_name) == wikidata_label: ...

# Storing a normalized name and comparing to a raw name — WRONG:
if stored_normalized_name == wikidata_label: ...
```

---

## Adding New Normalizations

Before adding a new normalization step:

1. Determine which category it belongs to (display or match-time).
2. If match-time: add it to `normalize_name_for_matching` and update tests in `speakermining/test/process/candidate_generation/test_person.py`.
3. If display: apply it in Phase 1 only, and confirm the transformed field is not used downstream as a matching key.
4. Update this document.
