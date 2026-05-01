# Existing Context
Weeks ago we already presented an output of the then-V3 Wikidata pipeline, generating the data in `data/31_entity_disambiguation/aligned` and then were manually reconciled to produce what can now be found in `data/31_entity_disambiguation/manual/reconciled_data_summary.csv`.

Generally, the approach will now be:
1. Treat the reconciled_data_summary.csv as the authoritative source of truth.
2. Aggregate Data from every source (ZDF Archiv PDFs, Fernsehserien.de, Wikidata) - likely mostly from `data/31_entity_disambiguation/raw_import` - and to complement this data
3. Whenever data is mssing: Use the Wikidata interface we described in F25 to retrieve the respective QID Info from cache or Wikidata.

Keep in mind that the data under `data/31_entity_disambiguation/raw_import` has the advantage that it is not affected by all the current issues of v4, but still has the downsides of v3 (e.g. core roles is empty because roles are classes and v3 was not yet able to handle that.)

**Note on entity access (F25):** `entity_access.py` implements `get_cached_entity_doc`, `ensure_basic_fetch`, `all_outlink_fetch`, and `load_core_entities`. For Phase 5 property retrieval (P21, P106, P102, P108, P569, P19), `all_outlink_fetch` is the required tier — it is cache-first and fetches full entity claims on a cache miss without triggering inlinks expansion. `ensure_basic_fetch` retrieves only labels + P31/P279 and must not be used as a property source. `all_outlink_fetch` was specified in `00_immutable_input.md` and is implemented as of 2026-04-30. Only access Wikidata through Phase 2 `entity_access.py` functions — never call `full_fetch.full_fetch()` directly from Phase 5 code.

See also open Tasks:

## documentation/ToDo/open-tasks.md
There are plenty of open tasks on analysis / visualization already specified in `documentation/ToDo/open-tasks.md`. Keep in mind: THEY need to be invested into HERE, since everything here is newer than they are. Since they were first written, we have a much more fleshed out analysis design - they should enhance existing tasks, add new once, and be overall ingested into this workflow - but they should not be taken authoritatively if they conflict with e.g. `00_immutable_input.md`
An example is "TODO-020: Extended gender distribution analysis", but generally any TODO with `Area: analysis` or similar.
Fundamentally, it is worth to go through `documentation/ToDo/open-tasks.md` and similar documents to enforce the same rules we just did for wikidata:

> Current status of the operation: We must focus on Phase 5 now. Any task that is related to any other phase must only be implemented if it is immediately useful for Phase 5: Analysis. For now, we should assume that no other Notebook prior to Phase 5 will be run again - at least until the next deadline.
> That means: 
> * Resolve all open tasks that are immedeately affecting how Phase 5 can access the output of prior Phases.
> * Explicitly defer any other known task, issue, problem, fix, finding or otherwise to post-deadline (03.05.). All of this is "Future Work", and currently assumed 100 % unsolvable - at least by us and before the deadline. 
> 
> Basic Principle right now: If doesn`t benefit the analysis right now, we won't do it.
