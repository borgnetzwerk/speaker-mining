# Entity_disambiguation
We have instances of the following core classes:
* person (Q215627)
* organization (Q43229)
* role (Q214339)
* episode (Q1983062)
* series of creative works (Q7725310)
* broadcasting program (Q11578774)
* topic (Q26256810)

We need to disambiguate the representations of all these instances from the various sources:
* PDF (ZDF Archiv): `data/10_mention_detection`
* Wikibase: (not yet implemented)
* Wikidata: `data/20_candidate_generation/wikidata`
* Fernsehserien.de: `data/20_candidate_generation/fernsehserien_de`

## Layer One: Broadcasting Programs
One layer does not need disambiguation:
* broadcasting program (Q11578774)
They are already structured in `data/00_setup/broadcasting_programs.csv`.
This is our single source of union, connecting all sources. From here, we can work down to layer two.

## Layer Two: Broadcasting Program Entity Children
Two entities will almost always point directly to broadcasting programs:
* series of creative works (Q7725310)
* episode (Q1983062)
Almost certainly, every source will have exactly one clearly identifiable entry. The main information used to disambiguate here is time: Publication date, duration, start time, end time, all these metrics can be used to match a wikidata season to a PDF season, a fernsehserien.de episode to a wikidata episode.
This also allows us to have one very important sorting axis: Time. Using time, we can sort every item ascending, from the very first episode to the most recent one.

Starting from here, we will have orphans: Very likely, many sources will have entities that cannot be matched to any other. Examples include:
* An episode registered in the ZDF Archive that was never released and thus has no entry in wikidata or fernsehserien.de
* An episode on fernsehserien.de that was just missing in the ZDF Archive and also has no Wikidata equivalent
As such, it is expected that Layer two items and onwards won't be perfectly matched. Never forcefully match any item - if the likelyhood is below a certain threshold, just keep the entity as an orphan.

## Layer Three: Episode Entity Children
The next layers are in direct relationship to the episodes:
* topic (Q26256810)
* person (Q215627)

Topics are extremely complicated and can be ignored for now.

Persons, on the other hand, are our main focus:
* Every person is originally assigned to one episode. They are on our radar exactly because of this. Some sources, such as Wikidata, will already have the guests disambiguated over different episodes - a "Barack Obama (Q76)" item mentioned in Episode 1 may be the same as the "Barack Obama (Q76)" item linked to in Episode 37. For our Step `31_entity_disambiguation`, this fact is not relevant yet: We ensure that the following are matched:
* "Barack Obama (Q76)" mentioned in Episode 1 of show X on Wikidata
* "Barack Obama (https://www.fernsehserien.de/barack-obama)" mentioned in Episode 1 of show X on Fernsehserien.de
* "Barack Obama" (mention_id) mentioned in Episode 1 of show X on the PDFs of ZDF Archive

All we need to do is matching those to eachother.
First, we have three different sources reporting the same: In some specific Episode instance, some specific guest instance was present. We just align this exact statement between different sources.

The end result that we should aggregate all information we have on this person into one entry:
Episode 1 of show X mentions "Barack Obama" (ZDF Archiv ID: mention_id) (Wikidata ID: Q76) (Fernsehserien.de ID: https://www.fernsehserien.de/barack-obama)

The unifier is the Episode disambiguated in layer two. As a result, we can have a person representation that aggregates all information from every source into one entry.


## Layer Four: Episode Guest Entity Children
Spread over all prior layers, there will be references to the following instances:
* role (Q214339)
* organization (Q43229)

Fernsehserien.de and the PDF archive have dedicated fields, sometimes multiple to describe the role of persons.
Organizations may be refered in those descriptions (e.g. "President of the CDU", referencing both their role (president) as well as the organization (CDU)). in general, these two can not easily be disambiguated. Once again, the relationship to their origin is important:
If an a person is said to have Role "President of the CDU" in the episode 1 description of the ZDF archive, and we match that person to a wikidata entry that has a claims like "President of: CDU" or similar, we can use this to map the role to president to the wikidata property, as well as the organization to the wikidata organization.

## General notes:
Higher layers are always most important. However, lower layers can further inform higher layers:
* Role and organization information retrieved from layer four can further inform the mapping of layer three. A human that could previously not be matched with sufficient certainty may now have more clarity, since lower level links were established. For example, if an occupation of a person was disambiguated, it will be much easier to now identify which of the candidates was ment - if we later learn that some person X has occcupation: engineer, and we had exactly one of many candidates that fits this description, this may increase our certainty over the required threshold.
* However, lower level information are generally more ambiguous and should rarely, if ever, be used to overwrite higher level decisions. Maybe a wrong match was made prematurely person in fernsehserien.de and in Wikidata, which was later uncovered due to a layer four discovery. This could be a reason to unlink the two again and put off the decision for now, with respective reasoning documented. However, especially Layer One and Two links are so strong and deterministic (linked via time, which is immutable and explicit), that there is likely nothing on Layer Three or below that could unlink them.