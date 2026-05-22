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

Confidence values by parsing rule:

| `parsing_rule` | `confidence` | Condition |
|---|---|---|
| `single_parenthetical` | 0.95 | One name directly linked to one parenthetical descriptor |
| `last_name_parenthetical` | 0.82 | Last name in a multi-name chain gets the parenthetical |
| `group_parenthetical` | 0.70 | Group-style descriptor (`Familie`, `Eltern`, etc.) assigned to all names |
| `surname_primary_no_parenthetical` | 0.68 | Name found via uppercase pattern, no descriptor |
| `single_parenthetical_mononym` | 0.62 | Single artist/stage name with parenthetical |
| `name_without_local_parenthetical` | 0.55 | Chain member, no relation cue, no local descriptor |
| `name_without_local_parenthetical` | 0.45 | Chain member WITH a relation cue (relation cues indicate the person is not a direct guest) |
| `legacy_sachinhalt_fallback` | 0.50 | Legacy path — should not appear in current runs |

## Data Quality And Traceability

- Every person row must include `parsing_rule`, `confidence`, and `confidence_note`.
- Source traceability is mandatory via `source_text` and `source_context`.
- If a behavior update changes extraction assumptions, update this document and `documentation/findings.md` in the same change.

## Guest vs. Incidental Mentions

The parser classifies each person row with a `mention_category` field:

- `guest`: the default; the person appears without a relation-cue in the inter-name segment.
- `incidental`: a relation-cue word (e.g. `ehemann`, `ehefrau`, `mutter`, `vater`, `tochter`, `ihre`, `ihrem`) appears between the previous name's end and the current name's start, **and the person is not themselves present as a guest**. Guests may have such relationships described — the cue alone is not sufficient. The distinction is presence, not relation.

  Example: `Michelle Obama (Ehefrau von Präsident Barack Obama)` → `Michelle Obama` is `guest`;
  `Barack Obama` is `incidental` (mentioned in relation to Michelle, not present himself).

Cue-word detection is scoped to the inter-segment only to prevent spill-over from earlier names in a chain. If a relation word is consumed into the name match by `_NAME_PATTERN`, the inter-segment may only contain a pronoun not in the cue list; these rare cases fall back to `guest` conservatively.

## Known Boundaries

- Episodes with empty `infos` cannot yield person rows (source PDF had no parseable Sachinhalt block; ~3 episodes in the current corpus).
- Episodes where `infos` lists only topics, not names, cannot yield person rows even when the anchor matched (~1 episode in corpus; section contains topics only, no name entries).
- Documentary, travel, or special-format broadcasts (e.g. episodes covering Kuba!, Russland!, Amerika!, Heiliges Land, Südtirol) use prose narration without the studio-interview format. Names exist but appear in title-case without the ALL-CAPS surname signal. Adding a pattern for these risks false positives across the full corpus; accepted as not_extractable (~5 episodes in corpus).
- Collective broadcasts (e.g. "Das Jahr 2020", "Ukraine Abend") use "Studiogästen" as a collective noun with no individual names listed; not_extractable (~2 episodes).
- Retrospective interview formats where names appear in title-case after a mid-sentence anchor rather than an opening pattern; ROI near zero given fernsehserien.de coverage of these episodes (~2 episodes).
- `Familie SURNAME (given1, given2, ...)` entries: 2 occurrences in 10,390 person rows (0.02%). Not worth a dedicated parsing rule at current corpus size.
- Stage names without stable supporting context remain lower-confidence signals.
