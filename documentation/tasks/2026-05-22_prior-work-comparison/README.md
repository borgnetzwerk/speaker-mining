# prior-work-comparison

* priority: medium
* scope: pipeline
* legacy-id: TODO-022

## Summary

The project has three prior datasets to compare against: Arrrrrmin (`data/01_input/arrrrrmin`), Spiegel (`data/01_input/spiegel`), and Omar (`data/01_input/omar`). Two comparison artifacts are needed: a high-level table for the related-work section and an extensive data comparison going through all prior results.

## Evidence

Prior data directories: `data/01_input/arrrrrmin`, `data/01_input/spiegel`, `data/01_input/omar`. Arrrrrmin visualization: `data/01_input/arrrrrmin/Website/LanzMining.html`. Omar's codebase: `documentation/tasks/2026-05-03_Speaker_Mining_Paper/First Approach Codebase`.

## Definition of done

1. A high-level summary table (methodology, scope, data volume, key findings) comparing this project against all three prior works is written and saved to `documentation/`.
2. An analysis notebook or section ingests each prior dataset and computes comparable statistics (guest count, gender distribution, time range) to enable direct comparison.
3. Key differences and improvements over prior work are documented.

## Scope clarification

Three different works total:
1. **Arrrrrmin** — independent prior work
2. **Spiegel** — independent prior work
3. **This Work** — built in two iterations: (a) Omar's first approach "LanzMining but Fair" (V0), and (b) this second iteration "Speaker Mining" (V1)

Omar's analysis may be omitted from the final comparison but can be presented as a V0 of this approach.

## Constraints

All analysis must exclude the moderator (Markus Lanz, Q43773) — see `moderator-exclusion` task. Age distribution should count every appearance (not just first) so a person appearing over multiple seasons is counted at each appearance age.
