# 2026-04-28 Evaluation Findings
We have just reset the handler `_progress` and let it run for over an hour. The output is found in `documentation/Wikidata/2026-04-26_investigation/2026-04-28_evaluation/run_output.txt`.

Overall verdict: The current state is critically broken and functionally unusable.

## Inexcusably long runtime
The runtime is extremely far too long - "Network calls used: 17 / 100 elapsed=4216.4s rate=0.24/min" - what are we doing if 17 calls are taking 4216 seconds ?

**Root cause identified (2026-04-29):** Two compounding bugs, not a network issue.

**Bug A — `ClassHierarchyHandler._pending` not cleaned up during replay:** When progress files were reset to 0 for this run, all 67 000+ events were replayed from scratch. Every `triple_discovered(*, P31/P279, class_qid)` event appended `class_qid` to `_pending`. Every `class_resolved(class_qid)` event added it to `_resolved` but — before the fix applied in this session — did NOT remove it from `_pending`. After replay, `_pending` contained thousands of class QIDs that were already in `_resolved`.

**Bug B — Work loop calls `replay_all()` even when `resolve_next()` did nothing:** The work loop is `while True: if class_h.has_pending() → resolve_next() → replay_all() → continue`. `resolve_next()` pops one QID, then immediately returns 0 if `qid in self._resolved` (no network call). But `replay_all()` is still called unconditionally, making 8 passes over the event log. With ~10 000 stale class QIDs in `_pending` and each `replay_all()` pass taking ~100ms (reading 67 000 events), this loop ran for **~1 000 seconds** before `_pending` was drained — matching the observed 1279s before the first network call.

**Fixes already applied in this session:**
- `ClassHierarchyHandler._on_event("class_resolved")` now removes the class from `_pending`.
- Snapshot+delta loading (F28) means progress files no longer need to be reset to 0; the full replay never happens again.

**Fix applied (2026-04-29):** `_work_loop()` in `21_candidate_generation_wikidata.ipynb` now guards every `replay_all()` call: `if handler.do_work(...) > 0: replay_all()`. This prevents the O(N_pending × N_events) spinning on stale pending entries even if they remain after snapshot load.

## Thousands of missing entities
The classified items are far to few - are our capture rules not correct? We should have far more of each core class, like 2000 episodes, around 1000 persons, similar numbers to this, thinking back to v3:

### Core output files
| File | Size | Date | Status |
|------|------|------|--------|
| `core_persons.json` | 48.5 MB | 2026-04-24 | **Not updated in this run** — pre-dates run |
| `core_roles.json` | 2 bytes | 2026-04-11 | **Empty `{}` — roles relevancy propagation did not produce output** |
| `not_relevant_core_roles.json` | 665 KB | 2026-04-26 | Updated — roles discovered but marked not-relevant |
| `core_organizations.json` | 244 MB | 2026-04-26 | Updated — large, organizations expanded |
| `core_episodes.json` | 32.7 MB | 2026-04-24 | Not updated in this run |
| `core_series.json` | 35.8 MB | 2026-04-26 | Updated |
| `core_topics.json` | 417 KB | 2026-04-24 | Not updated |
| `core_broadcasting_programs.json` | 219 KB | 2026-04-13 | Not updated |


## Wrong outputs
The outputs are wrong: The expected output was to put the wikidata json of the entity into the 

Right now, it looks like this:
[
  {
    "qid": "Q29845483",
    "label": "Ellen Ehni",
    "description": "",
    "aliases": [],
    "core_class": "Q215627",
    "conflict": false,
    "triples": []
  }
]

This structure is absolutely not what is needed. What is needed is exactly the structure we had in V3, an example to be seen in documentation/Wikidata/2026-04-26_investigation/2026-04-28_evaluation/example_episode_expected.json

**Root cause — wrong output format (2026-04-29):** `CoreClassOutputHandler` assembled a minimal internal record from individual events. The expected format is the **full raw Wikidata JSON** (the wbgetentities API response), structured as `{"Q..": {"type": "item", "labels": {...}, "claims": {...}, ...}}` — exactly what `full_fetch.py` saves into the Wikidata cache.

**Fix applied (2026-04-29):** `CoreClassOutputHandler._write()` now reads each entity's cached raw JSON via `_latest_cached_record` + `_entity_from_payload` and writes `{QID: entity_doc}` dicts. The `_triples`/`_descriptions`/`_aliases` event-reconstruction fields were removed; only `_labels` (entity registry), `_p31_map`, `_class_to_core`, `_core_classes`, `_core_class_mode`, and `_relevant` are retained for classification.

**Root cause — CSV blank lines (2026-04-29):** `V4Handler._atomic_write_csv_rows` used `csv.writer(io.StringIO())` which defaults to `\r\n` line terminators. `Path.write_text()` in text mode then converts `\n` → `\r\n`, producing `\r\r\n` per row — displayed as a blank line.

**Fix applied (2026-04-29):** Changed to `csv.writer(buf, lineterminator="\n")` in `handlers/__init__.py`.

Even the CSV have some weird newline between every row.

    qid,label
    
    Q11578774,broadcasting_programs
    
    Q1983062,episodes
    
    Q214339,roles
    
    Q215627,persons
    
    Q26256810,topics
    
    Q43229,organizations
    
    Q7725310,series
    

## Later stage access
Later stages must be able to understand and access our data - they must be able to access our cache easily, e.g. via triples or via a QID-lookup (give QID to a function, recieve all we know about that entity, including all JSON data we have retrieved about that entity from wikidata). Currently, since the entity store is gone, I see no easy way for later functions to interact with that data.

### We must confirm we actually need every query
We will always have a large amount of entities already cached. We must ensure that we only fetch data we do not already have in cache. An example of potentially wrong logic:
* We want to do a basic_fetch on Q123, but we never explicitly did a "basic_fetch". However, since we had all the data requested in a prior v3 `hydration` or `expansion`(both deprecated concepts), or even as part of a `full_fetch`, we already have all the data cached that we need. That means that despite us never requesting this data with explcitly a `basic_fetch` request. This could also happen if an entity is batch-fetched with a large group: Potentially, some in this group are already cached.
This is one reason to have a "data by QID" lookup, then we can always confirm what we know about and QID. This was the reason to have the QID lookup table pointing to the JSONL entity chunks: Be able to quickly look up and update data on any QID, without having one monolithic JSON file that takes ages to rewrite over and over again.
* Context: `F25 — v4 has no dedicated entity store; all entity data lives in the event log`

It may be wise to rethink that decision again.

## Unknown issues
The known issues above are all severely wrong, critically wrong - what other drift has happened from the quite well working v3 to the plausible looking v4 design to the current v4 implementation? It seems that the current implementation is so severely broken in many different ways that maybe, there have been some major concepts drifting away from the intended streamlining of a generally well working process. We need to find out where we went wrong.
