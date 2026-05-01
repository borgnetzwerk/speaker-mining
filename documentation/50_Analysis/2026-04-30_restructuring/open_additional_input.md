# Open Additional Input rules:
This is used as an unstructured document to provide additional input for current or future ToDos.
This Document is filled by human users.

Content here can be used to create or modify `documentation/50_Analysis/2026-04-30_restructuring/open-tasks.md`. If this is done, the respective content should be moved to `documentation/50_Analysis/2026-04-30_restructuring/archive/additional_input.md` so that this current file (`open_additional_input.md`) remains a clean notepad for additional human input.

**ARCHIVAL PRESERVATION RULE — MUST NOT BE VIOLATED:**
When moving content from this file to `documentation/50_Analysis/2026-04-30_restructuring/archive/additional_input.md`, the text **must be copied verbatim**. No summarizing, compressing, paraphrasing, or reformatting is permitted. Every word the human wrote must survive in the archive exactly as written. Loss of nuance is loss of information.

If something here is not clear yet and requires further clarification, raise "**QUESTION: ...**" here to request clarification before additional input from here can be further processed into `documentation/50_Analysis/2026-04-30_restructuring/open-tasks.md` and `documentation/50_Analysis/2026-04-30_restructuring/archive/additional_input.md`.

---

## 3. Run Person Catalogue Build via Pipeline Modules
We may have just re-fetched 4587 guest data from wikidata which we already had stored previously. If this was a one-time error, that is fine and we must live with it now. If this happens again, we have seriously miswired something and must fix it immediately. Retry the pipeline with network calls = 10 and see if cache still says entities are missing.

Also, regarding wording and outputs: During Analyis, we are not doing any `full_fetch`, we are doing `outlink_fetch`. This is correct behaviour, but print output and documentation may wrong. We must be careful with terminology to avoid concept drift.

Output snippet:
```
Missing cached entity docs for 4587 guests — attempting full fetches

[...]

Fetched 4587 missing guest entity docs
Network requests consumed: 4588
Extracting occupation (P106, type=Item)...
→ 14324 values extracted
Extracting country of citizenship (P27, type=Item)...
→ 5506 values extracted
Extracting sex or gender (P21, type=Item)...
→ 5916 values extracted
Extracting place of birth (P19, type=Item)...
→ 5195 values extracted
Extracting position held (P39, type=Item)...
→ 4795 values extracted
Extracting academic degree (P512, type=Item)...
→ 737 values extracted
Extracting member of political party (P102, type=Item)...
→ 1395 values extracted
Extracting religion or worldview (P140, type=Item)...
→ 502 values extracted
Extracting award received (P166, type=Item)...
→ 7896 values extracted
Extracting employer (P108, type=Item)...
→ 3583 values extracted
Extracting date of birth (P569, type=Point_in_time)...
→ 5668 values extracted
Extracting number of viewers/listeners (P5436, type=Quantity)...
→ 66 values extracted
Extracting social media followers (P8687, type=Quantity)...
→ 1114 values extracted
Extracting Commons category (P373, type=String)...
→ 3602 values extracted
Resolving 6909 missing value QIDs via full fetch

[...]

Fetched 6909 value entity docs
Network requests consumed: 6909
```

### Second run
Extracting occupation (P106, type=Item)...
  → 14324 values extracted
Extracting country of citizenship (P27, type=Item)...
  → 5506 values extracted
Extracting sex or gender (P21, type=Item)...
  → 5916 values extracted
Extracting place of birth (P19, type=Item)...
  → 5195 values extracted
Extracting position held (P39, type=Item)...
  → 4795 values extracted
Extracting academic degree (P512, type=Item)...
  → 737 values extracted
Extracting member of political party (P102, type=Item)...
  → 1395 values extracted
Extracting religion or worldview (P140, type=Item)...
  → 502 values extracted
Extracting award received (P166, type=Item)...
  → 7896 values extracted
Extracting employer (P108, type=Item)...
  → 3583 values extracted
Extracting date of birth (P569, type=Point_in_time)...
  → 5668 values extracted
Extracting number of viewers/listeners (P5436, type=Quantity)...
  → 66 values extracted
Extracting social media followers (P8687, type=Quantity)...
  → 1114 values extracted
Extracting Commons category (P373, type=String)...
  → 3602 values extracted
Resolving 26 missing value QIDs via full fetch
Fetched 26 value entity docs
Network requests consumed: 26

### Finding: Seems to be okay.
One-time issue. not good, but nothing to be done about it. Lesson Learned, moving on.