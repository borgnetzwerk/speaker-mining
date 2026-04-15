1. Build all relevant non-wikidata properties manually.
2. Build wikidata properties from csv first lines
	(around 2000 from wikidata alone)


pre 3.: experiment with instance import
pre 4.: experiment with value import

-- wait for reconsilation to be done --

OPEN REFINE
3. import instances via openrefine (just focus on the first five rows with the ids)
3.1 write csv with "BIG 6" columns:
* alignment_unit_id
* wikibase_id
* wikidata_id
* fernsehserien_de_id
* mention_id
* canonical_label

-- once open refine instance import is done

4. for each of those instances:
	for each relevant property beyond the first five: 
		for each value: if it does not exist yet: create it.
		
		(if possible) for each value: add a reference to it's source 
			* (ZDF Archiv with archiv number and filename maybe?)
			* fernsehserien.de with URL
			* Wikidata with QID
				* and: if available: actually use wikidata reference as well


Rule: Whenever possible, use cache first.

Must have outputs:
29.04. a list of all first 6 columns:
* alignment_unit_id
* wikibase_id
* wikidata_id
* fernsehserien_de_id
* mention_id
* canonical_label

03.05. Step 4 done: all instances and all values on wikibase.

after that: fix what we must, improve if we want


Don't forget: we still have to do deduplication.