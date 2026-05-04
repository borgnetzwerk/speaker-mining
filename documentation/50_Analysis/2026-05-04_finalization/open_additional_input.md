# Open Additional Input rules:
This is used as an unstructured document to provide additional input for current or future ToDos.
This Document is filled by human users.

Content here can be used to create or modify `documentation/50_Analysis/2026-05-04_finalization/open-tasks.md`. If this is done, the respective content should be moved to `documentation/50_Analysis/2026-05-04_finalization/archive/additional_input.md` so that this current file (`open_additional_input.md`) remains a clean notepad for additional human input.

**ARCHIVAL PRESERVATION RULE — MUST NOT BE VIOLATED:**
When moving content from this file to `documentation/50_Analysis/2026-05-04_finalization/archive/additional_input.md`, the text **must be copied verbatim**. No summarizing, compressing, paraphrasing, or reformatting is permitted. Every word the human wrote must survive in the archive exactly as written. Loss of nuance is loss of information.

If something here is not clear yet and requires further clarification, raise "**QUESTION: ...**" here to request clarification before additional input from here can be further processed into `documentation/50_Analysis/2026-05-04_finalization/open-tasks.md` and `documentation/50_Analysis/2026-05-04_finalization/archive/additional_input.md`.

---

## For Documentation
Generally: The order we established is the universal behaviour we should expect and implement at every step of the analysis:
* List episodes (e.g. 5000)
    * create binary guests x episodes occurrence matrix (e.g. 6000 x 5000)
       * from this occurrence matrix: derive all other value x episode matrix per property. (e.g. 4x5000 for one property, 532 x 5000 for another, 28 x 5000 for a third, ...). Here, each cell reflects the number of guests with that property value were present: 0 if none, 1 if one unique person, 5 if five unique persons, up to the maximum number of guests that were present in that episode, if everyone happens to have that. This way, we can quickly calculate things like "how many episodes were without carrier of this particular value" just by looking at that value's row and count the zeors.