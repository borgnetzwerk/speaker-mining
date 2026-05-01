# Open Additional Input rules:
This is used as an unstructured document to provide additional input for current or future ToDos.
This Document is filled by human users.

Content here can be used to create or modify `documentation/50_Analysis/2026-04-29_Initialization/open-tasks.md`. If this is done, the respective content should be moved to `documentation/50_Analysis/2026-04-29_Initialization/archive/additional_input.md` so that this current file (`open_additional_input.md`) remains a clean notepad for additional human input.

**ARCHIVAL PRESERVATION RULE — MUST NOT BE VIOLATED:**
When moving content from this file to `documentation/50_Analysis/2026-04-29_Initialization/archive/additional_input.md`, the text **must be copied verbatim**. No summarizing, compressing, paraphrasing, or reformatting is permitted. Every word the human wrote must survive in the archive exactly as written. Loss of nuance is loss of information.

If something here is not clear yet and requires further clarification, raise "**QUESTION: ...**" here to request clarification before additional input from here can be further processed into `documentation/50_Analysis/2026-04-29_Initialization/open-tasks.md` and `documentation/50_Analysis/2026-04-29_Initialization/archive/additional_input.md`.

---

## Inspect Persons with no episode link
Explicitly ToDo once visualizations are resolved. This is a large-scale laborous search task that can be done manually or with an Agent without budget limit. We just need to describe the issue, goal and how-to-solve it, as well as the definition of done.
Generally: We should go through individuals that have no episode links and verify if they truly appear in no episode. We already know that Marie-Agnes Strack-Zimmermann (Q15391841) appears in several episodes, so we already know that there are things wrong here.

Persons with no episode link: 215
  With wikidata_id:    215
  Without wikidata_id: 0

match_strategy breakdown:
match_strategy
wikidata_person_only_baseline    215

Random sample of 20 (verify these are genuinely unmatched — not missed guests):
wikidata_id               canonical_label                match_strategy match_tier
  Q21523850               Tomas Avenarius wikidata_person_only_baseline unresolved
 Q118142894         Wojciech Poczachowski wikidata_person_only_baseline unresolved
  Q15391841 Marie-Agnes Strack-Zimmermann wikidata_person_only_baseline unresolved
   Q2163782            Rolf Schmidt-Holtz wikidata_person_only_baseline unresolved
    Q562958                  Anna Planken wikidata_person_only_baseline unresolved
  Q50077398                 Joachim Frank wikidata_person_only_baseline unresolved
  Q18412110                Patrick Bernau wikidata_person_only_baseline unresolved
     Q76265            Franziska Brantner wikidata_person_only_baseline unresolved
  Q15852627                  Verena Kerth wikidata_person_only_baseline unresolved
   Q1897106     Marie-Christine Ostermann wikidata_person_only_baseline unresolved
  Q17353006             Moritz Schularick wikidata_person_only_baseline unresolved
   Q1039460                  Carl Linfert wikidata_person_only_baseline unresolved
  Q18341391              Sophie Sumburane wikidata_person_only_baseline unresolved
 Q134700129                   André Nemat wikidata_person_only_baseline unresolved
 Q132931403                  Eugen Brysch wikidata_person_only_baseline unresolved
   Q1251526                   Randi Crott wikidata_person_only_baseline unresolved
    Q106721                Peter von Zahn wikidata_person_only_baseline unresolved
 Q124387759          Arne Friedrich Mörig wikidata_person_only_baseline unresolved
  Q93278208                 Michael Sauga wikidata_person_only_baseline unresolved
   Q1357121     Ernst-Ludwig Freisewinkel wikidata_person_only_baseline unresolved

These persons will appear in `person_catalogue_unclassified.csv` after Step A.
Review this list after Step A to confirm no systematically misclassified entries.
