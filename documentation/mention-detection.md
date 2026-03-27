# Mention Detection Conventions

This document defines the parser conventions for Phase 1 mention detection, with emphasis on person/guest extraction from `episodes.infos`.

## Scope

- Applies to extraction logic under `speakermining/src/process/mention_detection`.
- Primary output contracts affected: `data/10_mention_detection/persons.csv` and `data/10_mention_detection/topics.csv`.

## Person Mention Conventions

1. Primary identifier: uppercase surname signal.
2. Uppercase surname may include German special characters such as `Ä`, `Ö`, `Ü`, and `ß`.
3. Parenthetical descriptors remain the highest-confidence source for person-role linkage.
4. Precision first: when descriptor assignment is ambiguous, keep person mention but lower confidence and keep `beschreibung` empty.

## Guest Detection Strategy

The extractor follows a tiered strategy on `infos` text:

1. Host-anchor sections
- Preferred anchors are interview openings containing host phrasing around `LANZ` and `mit`.
- Additional opening patterns such as `Interview ...` and `Studiogast...` are recognized when strict host anchors are absent.

2. Parenthetical guest rows
- Pattern: `name block (descriptor)`.
- Name block is parsed with surname-focused matching and conservative cleaning.
- Mononym artist/stage names are allowed in parenthetical form with reduced confidence.

3. Surname-primary fallback without parenthetical descriptors
- If no parenthetical row is found in a candidate section, a fallback extracts names from the lead segment using uppercase surname patterns.
- Fallback rows use lower confidence and explicit `parsing_rule` metadata.

## Parsing Rule And Confidence Expectations

Common person parsing rules:

- `single_parenthetical`: one person directly linked to descriptor.
- `group_parenthetical`: descriptor intentionally shared across multiple names.
- `last_name_parenthetical`: descriptor assigned to nearest trailing name in chain.
- `name_without_local_parenthetical`: chain member retained without descriptor.
- `single_parenthetical_mononym`: mononym name linked to descriptor.
- `surname_primary_no_parenthetical`: surname-driven fallback when descriptor is unavailable.

Confidence behavior:

- Higher confidence for direct parenthetical linkage.
- Medium confidence for group and nearest-name assignment heuristics.
- Lower confidence for no-local-descriptor and surname-only fallback rows.

## Data Quality And Traceability

- Every person row must include `parsing_rule`, `confidence`, and `confidence_note`.
- Source traceability is mandatory via `source_text` and `source_context`.
- If a behavior update changes extraction assumptions, update this document and `documentation/findings.md` in the same change.

## Known Boundaries

- Episodes with empty `infos` cannot yield person rows.
- Documentary summaries without list-like guest phrasing may remain unextractable without semantic inference.
- Stage names without stable supporting context remain lower-confidence signals.
