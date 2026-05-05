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


### Third finding of the same issue: "Resolving 6822 missing value QIDs via full fetch"
Once again, we use the wrong wording and outputs: During Analyis, we are not doing any `full_fetch`, we are doing `outlink_fetch`. This is correct behaviour, but print output and documentation may wrong. We must be careful with terminology to avoid concept drift.

```
 Wikidata property coverage: archive=672  cache=4,592  missing=0
Catalogued canonical persons: 8,448
  guest role rows: 31,569
  episode appearances: 31,569
  unmatched: 3,184
  unclassified: 93
Missing cached entity docs for 4580 guests - attempting full fetches
Fetched 4580 missing guest entity docs
Network requests consumed: 0
Extracting occupation (P106, type=Item)...
  → 12125 values extracted
Extracting country of citizenship (P27, type=Item)...
  → 4649 values extracted
Extracting sex or gender (P21, type=Item)...
  → 5046 values extracted
Extracting place of birth (P19, type=Item)...
  → 4385 values extracted
Extracting position held (P39, type=Item)...
  → 3649 values extracted
Extracting academic degree (P512, type=Item)...
  → 561 values extracted
Extracting member of political party (P102, type=Item)...
  → 1102 values extracted
Extracting religion or worldview (P140, type=Item)...
  → 395 values extracted
Extracting award received (P166, type=Item)...
  → 6549 values extracted
Extracting employer (P108, type=Item)...
  → 2708 values extracted
Extracting date of birth (P569, type=Point_in_time)...
  → 4844 values extracted
Extracting number of viewers/listeners (P5436, type=Quantity)...
  → 52 values extracted
Extracting social media followers (P8687, type=Quantity)...
  → 878 values extracted
Extracting Commons category (P373, type=String)...
  → 3039 values extracted
Extracting political ideology (P1142, type=Item)...
  → 26 values extracted
Resolving 6822 missing value QIDs via full fetch
[wikidata] Network calls used: 50 / unlimited elapsed=44.0s rate=68.13/min
[wikidata] Network calls used: 100 / unlimited elapsed=58.4s rate=102.76/min
[wikidata] Network calls used: 150 / unlimited elapsed=74.5s rate=120.82/min
[wikidata] Network calls used: 200 / unlimited elapsed=94.1s rate=127.53/min
Network requests consumed: 233
```

second still says 6822 full fetches
```
  Wikidata property coverage: archive=672  cache=4,592  missing=0
Catalogued canonical persons: 8,448
  guest role rows: 31,569
  episode appearances: 31,569
  unmatched: 3,184
  unclassified: 93
Missing cached entity docs for 4580 guests - attempting full fetches
Fetched 4580 missing guest entity docs
Network requests consumed: 0
Extracting occupation (P106, type=Item)...
  → 12125 values extracted
Extracting country of citizenship (P27, type=Item)...
  → 4649 values extracted
Extracting sex or gender (P21, type=Item)...
  → 5046 values extracted
Extracting place of birth (P19, type=Item)...
  → 4385 values extracted
Extracting position held (P39, type=Item)...
  → 3649 values extracted
Extracting academic degree (P512, type=Item)...
  → 561 values extracted
Extracting member of political party (P102, type=Item)...
  → 1102 values extracted
Extracting religion or worldview (P140, type=Item)...
  → 395 values extracted
Extracting award received (P166, type=Item)...
  → 6549 values extracted
Extracting employer (P108, type=Item)...
  → 2708 values extracted
Extracting date of birth (P569, type=Point_in_time)...
  → 4844 values extracted
Extracting number of viewers/listeners (P5436, type=Quantity)...
  → 52 values extracted
Extracting social media followers (P8687, type=Quantity)...
  → 878 values extracted
Extracting Commons category (P373, type=String)...
  → 3039 values extracted
Extracting political ideology (P1142, type=Item)...
  → 26 values extracted
Resolving 6822 missing value QIDs via full fetch
[wikidata] Network calls used: 50 / unlimited elapsed=44.7s rate=67.17/min
[wikidata] Network calls used: 100 / unlimited elapsed=59.6s rate=100.69/min
[wikidata] Network calls used: 150 / unlimited elapsed=80.0s rate=112.50/min
[wikidata] Network calls used: 200 / unlimited elapsed=97.2s rate=123.40/min
[wikidata] Network calls used: 250 / unlimited elapsed=114.0s rate=131.52/min
[wikidata] Network calls used: 300 / unlimited elapsed=132.5s rate=135.86/min
[wikidata] Network calls used: 350 / unlimited elapsed=156.3s rate=134.36/min
[wikidata] Network calls used: 400 / unlimited elapsed=174.8s rate=137.31/min
[wikidata] Network calls used: 450 / unlimited elapsed=196.1s rate=137.66/min
[wikidata] Network calls used: 500 / unlimited elapsed=216.7s rate=138.41/min
[wikidata] Network calls used: 550 / unlimited elapsed=233.2s rate=141.50/min
Fetched 6822 value entity docs
Network requests consumed: 568
Enriching 15 property frames with fetched labels...
Expanding property frames from guest level to guest-episode level...
✓ Property frames expanded to episode level
```

To correct behaviour, we must also differentiate what data we get from cache and for which we need to do outlink fetches. Then we can say "retrieved X from cache, now retrieving Y via outlink fetches..." as a clear output. in our example, actually 233 + 568 Network requests were needed, but the output reads as if 6822 are needed.