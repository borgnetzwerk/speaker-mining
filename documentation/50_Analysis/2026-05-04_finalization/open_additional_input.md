# Open Additional Input rules:
This is used as an unstructured document to provide additional input for current or future ToDos.
This Document is filled by human users.

Content here can be used to create or modify `documentation/50_Analysis/2026-05-04_finalization/open-tasks.md`. If this is done, the respective content should be moved to `documentation/50_Analysis/2026-05-04_finalization/archive/additional_input.md` so that this current file (`open_additional_input.md`) remains a clean notepad for additional human input.

**ARCHIVAL PRESERVATION RULE — MUST NOT BE VIOLATED:**
When moving content from this file to `documentation/50_Analysis/2026-05-04_finalization/archive/additional_input.md`, the text **must be copied verbatim**. No summarizing, compressing, paraphrasing, or reformatting is permitted. Every word the human wrote must survive in the archive exactly as written. Loss of nuance is loss of information.

If something here is not clear yet and requires further clarification, raise "**QUESTION: ...**" here to request clarification before additional input from here can be further processed into `documentation/50_Analysis/2026-05-04_finalization/open-tasks.md` and `documentation/50_Analysis/2026-05-04_finalization/archive/additional_input.md`.

---

## Current state and lessons learned
* When creating stacked bar charts with labels, try to create horizontal stacked bar charts, where possible. The current Pareto visualization is barely readable as a vertical stacked bar chart with labels. Current issues: Text is rotated to the other labels, so you need to rotate your view to read whats inside. If the bars were horizontal, we would not have this issue.
  * Exceptions would be something like timelines, which we'd expect to be left to right.

* On Displaying "no data": On top, we currently display "n=... unique persons  - ... appereances - ... no data". This would be the perfect place to structure it something like this:
    ... guest appereances of ... unique persons
    no property data on ... guest appereances of ... unique persons (Tier 1 and Tier 2 entries that happen to not have claims for this particular property)
    no Wikidata entry on ... guest appereances of ... unique persons (Tier 3 and Tier 4 entries)
  * potentially, there is a more clever way to format this, but the general idea is: display what data we have

* On README generation: We also need one README per property.
  * Basic principle: Every folder in `data/50_analysis` needs its own README.

* Basic principle: 
  * Every analysis, visualization and README that is created for "ALL" should also be created per show.
  * Every analysis, visualization and README that is created per show should also be created for "ALL.
    * For example: All property analysis is currently done only for ALL, but must also be done for each show individually.

Generally: The current visualizations like Pareto or simple bar charts in general are very basic, and we should not spend much more time on this. Stacked bar charts, timelines, Sunburst, Treemap etc. are all much more interesting and still not implemented. Particularly the property x property and the property x person stacked bar charts will be very interesting. We should focus on those.

## Issue resurfaced
The wrong-episode-mapping critical issue seems to have resurfaced. We once again have a `data/50_analysis/couchwissen/occurrence_matrix.csv` filled with occurrences of guests that were never there. 
Same names, same issues as originally documented in `documentation/31_entitiy_disambiguation/2026-04-05_critical_issue/issue.md`.