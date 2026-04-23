# Approach

## Data Schema
Since we do not know what properties are used in any particular wikidata entry, we primarily use JSON for the entire Wikidata step.

### Core class file
The main class file structures everything as follows:
```
wikibase_id,filename,label,description,alias,label_de,description_de,alias_de,wikidata_id,fernsehserien_de_id
,persons,person,,,,,,Q215627,
,organizations,organization,,,,,,Q43229,
,roles,role,,,,,,Q214339,
,episodes,episode,,,,,,Q1983062,
,series,series of creative works,,,,,,Q7725310,
,broadcasting_programs,broadcasting program,,,,,,Q11578774,
,topics,topic,,,,,,Q26256810,
,entities,entity,,,,,,Q35120,
,privacy_properties,property that may violate privacy,,,,,,Q44601380,
```

By default, everything is an entity. The purpose of these classes is to provide a better hierarchical chunking of these entities. As such, each of the top-level classes has its own files where all instances and subclasses are maintained. For example:
* **series**,
 the class representing seasons and similar series of a broadcasting program, has the following files:
  * `data/20_candidate_generation/wikidata/new/classes/series.csv`
  where all english and german labels, descriptions and aliases of the series subclasses are stored
  * `data/20_candidate_generation/wikidata/new/classes/series.json`
  where all other properties of the series subclasses are stored
  * `data/20_candidate_generation/wikidata/new/instances/series.csv`
  where all english and german labels, descriptions and aliases of the series instances are stored
  * `data/20_candidate_generation/wikidata/new/instances/series.json`
  where all other properties of the series instances are stored

In our example, subclasses of series would be *television series season (Q3464665)* and *podcast series season (Q69154911)*, where an instance would be *Markus Lanz, season 11 (Q56418119)*.

#### Query Cache
The results of this query are stored first and foremost in a single json file. As such, the number of files in the query folder will always be identifcal to the amount of query replies recieved. This cache is so that no request is sent twice, every fetched item is loaded from cache, unless it is too old. If that's the case, it is queried again and recieves a new reply file.

#### Principles
* CSV information is always redundant to json info. Any info stored in a csv is also stored in a json, it's just usually easier to access from a csv. The csvs serve as overview

### Raw Query Results
for now, we store all query results as raw json files. Long term, those should be handled by some kind of event-sourced database with the following qualities:
* resistant against corruption, a new write should never endanger the integrity of old entries
* lightweight
* flexible, the query results will look very different all the time, the database must not be too static.
* reconstructable, every event should be timestamped and any point in time should be reconstructable by just aggregating the then current state over all previous entries, ignoring all future entries past that point.

## Approach

### Step 1: Graph Setup
Load the classes and properties from `data/00_setup`.


**Note: As always, "query" means "check in cache first, only query if entry does not exist or is too old."**
#### Classes
The core class file is loaded.
Then, every entry is checked:
1. Is the required folder structure in place? If not, create it.
2. Are all required files in place? If not, create the missing files.
3. Are all core classes represented in entities.json and entities.csv? If not, query each missing core class against wikidata and populate entities.json and entities.csv.
4. Are all fields in the core class file filled? If not, load them from entities.csv.


### Step 2: Broadcasting Program Loading
1. Load the broadcasting programs from `data/00_setup/broadcasting_programs.csv`.
2. Load the first broadcasting programs into the expansion queue.
3. Expand every item in the queue.
   1. When the expansion finds a valid target (see below), the valid target is added to the expansion queue.
   2. When a new ID (property or item) is detected, add it to the cache (see below) 
4. When the queue is empty, add the next broadcasting program to the queue and repeat step 3: Expand every item in the queue.
5. When all broadcasting programs are expanded upon, the task is completed.


#### Graph Expansion Rules
The algorithm can only ever expand information that has a direct link to one of:
* instance of a listed *broadcasting program*, meaning one listed in `data/00_setup/broadcasting_programs.csv`
* instance of a class listed in `data/00_setup/classes.csv` with a link to a listed *broadcasting program*

An example:
1. Markus Lanz (Q1499182), https://www.wikidata.org/wiki/Q1499182
   * is an instance of a listed broadcasting program
   * -> can be expanded
2. Markus Lanz, season 11 (Q56418119), https://www.wikidata.org/wiki/Q56418119
   * is an instance of a listed class: series of creative works (Q7725310)
   * has a direct link to an instance of a listed broadcasting program: Markus Lanz (Q1499182)
   * -> can be expanded
3. Markus Lanz (August 14th, 2018) (Q56418136), https://www.wikidata.org/wiki/Q56418136
   * is an instance of a listed class: episode (Q1983062)
   * has a direct link to an instance of a listed broadcasting program: Markus Lanz (Q1499182)
   * -> can be expanded
4. Harald Lesch (Q45321), https://www.wikidata.org/wiki/Q45321
   * is an instance of a listed class: episode (Q1983062)
   * **has no direct link to an instance of a listed broadcasting program**
   * **X can not be expanded**

This ensures no excessive loops over all somehow linked humans, for example.

General rules:
* In-Links to classes can never be expanded. Classes and abstract concepts in general have so many items pointing to them, the stress on the wikidata services would not be acceptable.
  * Example: talk show (Q622812), https://www.wikidata.org/wiki/Q622812
    * is a class, cannot be expanded


### New Item discovery
Item discovery triggers a basic context fetching. This is not equal to expansion: We don't want to know all relationships and properties of this item, we only want to know the most basic context

Whenever a new entity (QID) is discovered, we only fetch the following basic properties:
* label (`en` and `de`)
* description (`en` and `de`)
* alias (`en` and `de`)
* instance of (P31),
* subclass of (P279),

If we find a new property (PID), we fetch the following basic properties:
* label (`en` and `de`)
* description (`en` and `de`)
* alias (`en` and `de`)
* instance of (P31),
* subproperty (P1647)


#### Class Discovery
Every entity (QID) that has a property:value pair "P279:X" is a subclass of X and thus a class.
* We say "A is subclass of X"
* This also means "X is superclass of A"
Every class has *entity (Q35120)* as its superclass. There may be other superclasses in between them. An Example:
*  A is subclass of X.
*  X is subclass of Y.
*  Y is subclass of entity (Q35120)
When discovering new classes, we are looking for subclasses of our core classes listed in `data/00_setup/classes.csv`.
This means that whenever a new class is discovered, a basic Breadth-First Search (BFS) searches for the shortest path to a known class.
* As always, all discovered classes are stored so they are not queried for again. This search, like all searches, checks before every query if the result is already found locally.
Then, that path is stored alongside the other class properties in the csv. This also applies for every other property on that path.
* For all other discovered properties without a known path to a core class, the path is left blank.
* Identified loops should be printed to console and to a separate analysis file, but are not further critical, because of the next rule:
* During the Breadth-First Search, if a class is part of a currently explored path, it is added to a "seen" list for the duration of the Breadth-First Search. Whenever that class is found in any other branch of the Breadth-First Search, do not explore that particular class further. This will prevent both loops as well as multiple threads of the same search following the same path.

#### Instance Discovery
Every entity (QID) that have no property:value pair "P279:X" is not a class, but only an instance.
Instances will have the instance of property linking them to their classes: "P31:X".
Every instance will thus trigger the Class discovery, resulting in their class receiving a path.
This path is also stored for the instance, marking it as an instance of one of the core classes.
Unless a path to one of the other core classes is discovered, every instance is stored as one of the other entities.