## General status
We currently have a very solid baseline of analysis and visualization. The data is correctly deduplicated, persons and properties are loaded and analyzed. What remains are:
1. Some fixes, for exmaple:
   1. Moderators get mixed in with guests - we must ensure that this classification is done once and that only guests are fully analyzed.
   2. Appearances are wrong, with roughly 5000 persons, 5000 episodes and an average of roughly 4 guests per epsiode, we should have something like 20.000 appereances - yet some statistics say that we have e.g. 23000 appearances of a guest being male - there must be something wrong with the current appearances calculation
2. implementation of additional analysis / visualization angles.

We get to learn about those by 
a) inspecting older analysis documentation, search for open tasks, match these against the current implementation and see what could still be added. An example of this is `documentation\50_Analysis\2026-05-04_finalization\01_from_2026-04-30_restructuring.md`.
    Noteworthy: The older documentation may be outdated - an open task may be long solved, or a better solution was found. Generally: nothing is authoritative, raise questions when something is unclear.
b) Process `documentation/50_Analysis/2026-05-04_finalization/open_additional_input.md`. This is generally authoritative, but can also be already implemented.

Once we have all of these aggregated:
* Aggregate into a deduplicated task list, aggregating input from all sources.
* Form a short overview of an implementation plan in `documentation/50_Analysis/2026-05-04_finalization/02_implementation_plan.md` - a simple ordered list of "Task | status" should suffice.

Then - when that list of open-tasks and implementation plan is confirmed - we implement.

Our target implementation: A dynamic pipeline that generates all suitable visualizations for every property we specify in `data/00_setup/analysis_properties.csv`. If we add a new visualization to our catalogue and let the code rerun - it should exist for every property (combination, if applicable). This way: We write a new analysis, we register it somewhere, and the next execution of the unchanged notebook will just produce that one as well.