# class-hierarchy-walk

* priority: medium
* scope: pipeline
* legacy-id: TODO-058

## Summary

The P279 hierarchy walk is incomplete: mid-level class mapping is missing, loop detection uses no configuration, and occupation rollup breakages (visible in top-10 lists as duplicate "Schauspieler", "Teacher" variants) remain unfixed.

## Evidence

`documentation/archive/50_Analysis/2026-05-04_finalization/open-tasks.md` TASK-F03; `documentation/archive/50_Analysis/2026-04-29_Initialization/open-tasks.md` TASK-A02 known issues.

## Definition of done

1. P279 hierarchy walk completes for all first-level classes including Q488205 (Singer-Songwriter) and other QIDs currently missing resolution.
2. Loop detection consults `data/00_setup/loop_resolution.csv`; unlisted cycles use lowest-QID fallback; loop diagnostics (`number_of_loops`, `classes_in_loops`) are published.
3. Mid-level class mapping is defined and applied: sunburst/hierarchy charts show meaningful mid-level groups rather than direct top-level or first-level only.
4. "Two kinds of Schauspieler" symptom is gone from top-10 occupation lists.

## Notes

Depends on `roles-projection-fix` for architectural design. Blocked on V4 Wikidata entity access until basic_fetch is reliable (see `wikidata-v4-rework`).
