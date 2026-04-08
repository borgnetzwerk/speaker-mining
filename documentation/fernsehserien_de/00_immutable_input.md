# Fernsehserien.de Specification
https://fernsehserien.de/ is an IMDB-like website that stores information on many broadcasting programs we are interested in.

## Wikidata
Wikidata even has a dedicated property for Fernsehserien.de:
* fernsehserien.de ID (P5327)
And a wikidata item:
* fernsehserien.de (Q54871129)
We have this item in our speaker-mining storage:
    id,class_id,class_filename,label_de,label_en,description_de,description_en,alias_de,alias_en,path_to_core_class,subclass_of_core_class,discovered_at_utc,expanded_at_utc
    Q54871129,Q35127,,Fernsehserien.de,fernsehserien.de,Website über Fernsehserien,German website,,,,False,2026-04-07T09:07:47Z,

## Approach
1. **Load broadcasting programs:** Load `data/00_setup/broadcasting_programs.csv` and process all eligible rows with a valid `fernsehserien_de_id`.
2. **Get fernsehserien.de root page:** Use this `fernsehserien_de_id` to get the respective main page of the broadcasting program.
3. **Get fernsehserien.de episode pages:** Discover episode URLs primarily via episodenguide traversal (with on-gap leaf-neighbor fallback), fetch leaf pages cache-first, and store information from each episode page (most importantly: name, description, publication, Cast & Crew, Sendetermine).

Repeat Step 3 until all episodes of that broadcasting program are retrieved.
Then repeat from step 1 onwards until all episodes of all broadcasting programs are retrieved.

### Example:
#### Step 1: Load broadcasting program
wikibase_id,filename,label,description,alias,label_de,description_de,alias_de,wikidata_id,fernsehserien_de_id
,markus_lanz,Markus Lanz,,,,,,Q1499182,markus-lanz

#### Step 2:
Navigate to
* https://www.fernsehserien.de/markus-lanz/
Sample data of how this data looks like can be found here:
* `data/01_input/fernsehserien_de/testing/root/Markus Lanz – fernsehserien.de.html`


We can also navigate to
* https://www.fernsehserien.de/markus-lanz/episodenguide
Of which a local snapshot is stored here:
* `data/01_input/fernsehserien_de/testing/episodenguide/Markus Lanz Episodenguide – fernsehserien.de.html`
Note: This page has plenty of "mehr..." buttons:
    <div><ul class="fs-buttons"><li><span class="fs-button"><button type="button" data-event-category="button-mehr-episoden" data-abschnitt="1" data-sendung-id="12129" data-episodenliste-entkuerzen="" data-event-applied="1">mehr…</button></span></li></ul></div>
Those buttons reveal other episodes hidden in the original view. A local snapshot of the expanded version is stored here:
* `data/01_input/fernsehserien_de/testing/episodenguide_expanded`

The episodenguide is also paginated
* https://www.fernsehserien.de/markus-lanz/episodenguide/1/21920
* https://www.fernsehserien.de/markus-lanz/episodenguide/1/21920/2
* https://www.fernsehserien.de/markus-lanz/episodenguide/1/21920/3
* ...
  * **Note:** It is right now not clear where the ID "21920" is coming from, but it seems to be required for the page to resolve. Yet, the full URL can be retrieved from the root page. For example:
  * https://www.fernsehserien.de/markus-lanz/
    <a data-event-category="liste-ausstrahlungsformen" href="https://www.fernsehserien.de/markus-lanz/episodenguide/1/21920" data-event-applied="1">
Local saves for inspection are stored here:
* Page 1: `data/01_input/fernsehserien_de/01/Markus Lanz 2008 Episodenguide – fernsehserien.de.html`
* Page 2: `data/01_input/fernsehserien_de/testing/02/Markus Lanz 2008 Episodenguide (Seite 2) – fernsehserien.de.html`


#### Step 3:
The canonical traversal strategy is:
1. use episodenguide traversal (including pagination) as the primary discovery path,
2. use episode "next/previous" neighbor traversal only as on-gap fallback when new unseen neighbors are detected.

Neighbor traversal examples:
    <a class="episode-ueberschrift-zurueck" data-event-category="button-zurück-oben" href="/markus-lanz/folgen/2206-sendung-vom-07-04-2026-1869430" title="zurück" data-event-applied="1"></a>
    <a class="episode-ueberschrift-weiter" data-event-category="button-weiter-oben" href="/markus-lanz/folgen/2208-sendung-vom-09-04-2026-1869432" title="weiter" data-event-applied="1"></a>

To get all information we require, we likely need to navigate to each episode's own page. An example:
* https://www.fernsehserien.de/markus-lanz/folgen/1-folge-1-514614
Exemplary data retrieved from such a page is stored here:
* `C:/workspace/git/borgnetzwerk/speaker-mining/data/01_input/fernsehserien_de/testing/01_01/Markus Lanz 1_ Folge 1 – fernsehserien.de.html` 


## Implementation
The two mainly important paths are:
* Orchestrating Notebook: `speakermining/src/process/notebooks/22_candidate_generation_fernsehserien_de.ipynb`
* logic modules: `speakermining/src/process/candidate_generation/fernsehserien_de`

Current notebook runtime configuration is intentionally minimal and production-oriented:
* `MAX_NETWORK_CALLS` controls cache-only (`0`), bounded (`>0`), or unlimited (`<0`) execution.
* `QUERY_DELAY_SECONDS` controls pacing.
* `USER_AGENT` controls request identification.

### Policy
This workflow is built from scratch and does not carry backward compatibility obligations for legacy code, legacy projections, or legacy users.

The exceptions are deliberate and narrow:
* Cached source files are authoritative inputs and must always be reused and built around.
* Legacy append-only events are authoritative history and must always remain part of replay and projection logic.

### Basic principles
Fundamentally, `documentation/coding-principles.md` and all related coding principles apply.

This means, among others:
* Precision over recall for automated extraction unless explicitly discussed and documented.
* Traceability over convenience
* Notebooks orchestrate; core logic lives in `speakermining/src/process` modules.
* Event-Sourcing Principles; every persisting action produces an event, and projections are constructed from events.

### Event-Sourcing
Particularly important is the Event-Sourcing:
* By design, every action that impacts the persistent state is stored as an event. These events ensure that no action is ever done twice, which is especially important for queries.
* every projection, such as "list of episodes" or "list of guests" or any other data beyond events 

The potential for Event-Sourcing was already discussed in two previous migrations:
* `documentation/Wikidata/2026-04-02_jsonl_eventsourcing`
* `documentation/Wikidata/2026-04-03_eventsourcing_potential_unlock`
Since the code for fernsehserien.de is written from scratch, we can ensure we follow the eventsourcing principles perfectly. We need to utilize this freedom and unlock the potential of eventsourcing.

### Wait time
Principles very similar to Wikidata apply: Be very slow with the requests we sent. We need to maintain good graces with the service, so take it slow. Back off if need be, and implement a generous wait time of 1 second between requests by default.

### Finding the right approach
It will likely take a few tries to find the best approach to retrieve episode data. We must ensure we are using the best approach for the service to retrieve the data we need. As such, while we try to find the right solution:
* Once we have recieved a response for a network request, never request this again. If we need to measure any metrics, do it during ever network request. Plan ahead, don't spam requests and burden the service.
* Whenever there a two paths available, explore both.
* Explore local files. We already have some files in `data/01_input/fernsehserien_de/testing`, and you can store additional files there - retrieved data, measurements, metrics, anything. Make use of a local cache to explore different routes to find the one that puts the lowest burden on the service.
* **Ignore noise.** Every page contains a few information we need (most importantly: name, description, publication, Cast & Crew, Sendetermine), and a whole set of noise we don't need (advertisments, page footers, forwarding links, app recommendations, etc.). We always need all important information - but if possible, we should try not to retrieve the noise. This may not always be possible, but here is a consideration:
  * If everytime we download a page, we download a constant amount of noise - then reducing the number of downloaded pages is instantly a reduction in amount of noise downloaded. page download count is then a good proxy for this noise.
  * If we, however, find a format where we only retrieve relevant information with barely any noise, then downloading this format barely affects the amount of noise downloaded. We can use this format more freely then.