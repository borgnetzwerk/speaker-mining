# Phase 3 Step 1: Entity Disambiguation 

The main goal is to have aligned core class instance tables. Especially the aligned person instances are our main goal - yet, this faces a contextual issue:
* Aligning person data requires upstream alignment of Broadcasting Program and Episode instances, as well as downstream property alignment of Roles and related Organizations.

We need to align all core class instances, working our way down from Broadcasting Programs to Episodes to align Person entities, and then try to disambiguate the related Roles and Organizations further.

## Files
### Documentation
* 00_immutable_input.md
* 01_approach.md
* 02_implementation.md
* 10_refinement.md

### Notebook
* speakermining\src\process\notebooks\31_entity_disambiguation.ipynb