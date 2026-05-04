## Pre Analysis redesign

> Status: Completely implemented

Currently, the analysis step `speakermining/src/process/notebooks/50_analysis.ipynb` is a bit overloaded:
* Data is ingested from manual reconciliation
* Then partially deduplicated
* then missing data is fetched from wikidata
* Then missing property value data is also are fetched
* then the actual analysis begins.

What we need to do:
### Phase 3 Step 2
Currently, `speakermining/src/process/notebooks/32_entity_deduplication.ipynb` is also not implemented correctly:

After `data/31_entity_disambiguation` has been resolved, we can get the most authoritative file: `data/31_entity_disambiguation/manual/reconciled_data_summary.csv`

To do so, we must move all relevant .py and .ipynb code from `data/31_entity_disambiguation/manual` to the beginning of 32_entity_deduplication.ipynb.

Executing `32_entity_deduplication` then begins with set up and then generates the `data/31_entity_disambiguation/manual/reconciled_data_summary.csv` that looks like this:
```
alignment_unit_id,wikibase_id,wikidata_id,fernsehserien_de_id,mention_id,canonical_label,entity_class,match_confidence,match_tier,match_strategy,evidence_summary,unresolved_reason_code,unresolved_reason_detail,inference_flag,inference_basis,notes
pm_89f51707074a,,Q1332861,https://www.fernsehserien.de/markus-lanz/folgen/54-folge-54-517595,pm_89f51707074a,Elmar Theveßen,person,0.0,unresolved,episode_context_name_exact,no candidate above threshold,no_candidate,No deterministic same-episode guest or unique Wikidata person candidate,false,,
pm_fbb719b2cd68,,Q1332861,https://www.fernsehserien.de/maischberger-ard/folgen/818-sendung-vom-29-05-2024-1720446,pm_fbb719b2cd68,Elmar Theveßen,person,0.83,high,episode_context_name_exact,unique label-equal wikidata person,,,false,,
```

This data is then our primary mapping structure:
1) First, every entry sharing a QID is deduplicated and aggregated to this unique QID: One unique entry that knows all the IDs it was aggregated from. In our case: The entry for Elmar Theveßen (Q1332861) stores that it is the deduplicated entry for pm_fbb719b2cd68. The QID can be the unique identifier of this aggregation entry. 
   1) Once this is done for the `data/31_entity_disambiguation/manual/reconciled_data_summary.csv`, we can also aggregate all other QIDs from Wikidata: All episodes, organizations, other persons, etc. - should be aggregated so at the end of this first tep, we have a set of ALL unique QIDs we are aware of, and retrieve all data we have cached on them.
2) Then, all entries that do not have a QID yet should be considered, currently, these will be from  ZDF archive data and fernsehserien.de. For these, we do the deduplication clustering and identify if they belong to a cluster that has members which are already mapped to a QID. Then, this can be aggregated there, with a dedicated note. If this clustering groups members which individually belong to different QIDs, print them to a dedicated output file and raise warnings for the user to inspect.
   1) We already have a good clustering algorithm, which we can just keep and use here. Lexemical similarity analysis between remaining unmatched entities should generally suffice, but eventually, we can even disambiguate the roles and descriptions. For now, additional implementations should be liimited to only low hanging high ROI fruits. 


Our final output should be:
Per core class, two files (CSV or JSON, whichever is more suitable) that cointain a) the final deduplicated entries and b) the entries that could not be deduplicated.
Both will then be available to the analysis.

Below are a few examples of different clusters that all describe the same unique individual: Elmar Theveßen (Q1332861).

#### Elmar THEVESSEN
```
ce_f9dbccd723c0,person,69,normalized_name_match,medium,,Elmar THEVESSEN,Elmar THEVESSEN,elmar thevessen,Normalized name key 'elmar thevessen' matches 69 alignment units,pm_89f51707074a
```

#### Elmar THEVEßEN
```
ce_ae1202b97ba3,person,83,wikidata_qid_match,high,Q1332861,Elmar THEVEßEN,Elmar THEVEßEN,elmar thevessen,Shared Wikidata QID Q1332861 across 83 alignment units,pm_fbb719b2cd68
```

#### Mainz Elmar THEVEßEN
```
ce_7dbd7787839c,person,2,normalized_name_match,medium,,Mainz Elmar THEVEßEN,Mainz Elmar THEVEßEN,mainz elmar thevessen,Normalized name key 'mainz elmar thevessen' matches 2 alignment units,pm_19a3f1ecbd2f
```
We will probably not be able to catch this, for now. This is a loss that we will have to live with, for now.

### Analysis:
Analysis then only reads the final output from Phase 3 Step 2:
Per core class, two files (CSV or JSON, whichever is more suitable) that cointain a) the final deduplicated entries and b) the entries that could not be deduplicated.

The main thing we fix in analysis that the input preparation is outsourced to Phase 3 Step 2, and we only read it from there.
Thus:

1. Reads all the relevant data from `data/00_setup` (for exmaple `broadcasting_programs.csv` and `analysis_properties.csv`)
2. Reads all episodes from the Phase 3 Step 2 output.
3. Classifies all relevant persons into their respective categories for the upcoming analysis (per epsiode: moderator XOR guest XOR ...), creating the fundamental occurence matrixes (moderator_episode_occurence matrix, guest_episode_occurence matrix, ...)
4. Identifies all the relevant properties and values for these entities (e.g. persons episodes broadcasting_programs) relevant to this particular analysis and outlink_fetches all their data that is not yet available.
5. Proceed with the regular analysis

Note that the separation of person classifications (guest, moderator etc.) is currently not working propertly and should also be carefully fixed with this rework.