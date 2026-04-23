# Important aspects

## Fundamentals
### We must scale well
* JSONS do not scale to the amount of data we will likely have. We need deterministic ways to split them up. An example would be: 
  * Once CSV with only two columns: QID,file
    * This means that we can close any file whenever it becomes too big and begin a new file. The lookup time remains constant, since we check the ID once, 
* We can Chunk our output projections different from our projections used during runtime.
  * Later will expect to interact with structured representations of the core class instances. At the same time, wikidata
* Keep in mind that concepts such as "indent" or similar to make (JSON) files more human-readable are irrelevant in this step. Wikidata Outputs are intermediate. Only outputs from Phase 3 and onwards are consumed by humans, so we do not need to consider human readability. 

### Wikidate is the central knowledge node
* Wikidata is the most important knowledge node. Everything we know must be easily accessible to later stages, and likely, we may even be called again to fetch additional items again. This means we need projections and additional interfaces that can be utilized by later layers.
* Properties and classes are best described by wikidata. Other sources will just have a concept of "guest" or "person" or "episode", but only wikidata has the context and IDs describing what these nodes and properties mean.
 
### Core Class Instances are the main output
* We should have one dedicated file per core class (see `data\00_setup\core_classes.csv`) as output. This may look something like this:
1. broadcasting_programs.json
2. series.json
3. episodes.json
4. persons.json
5. topics.json
6. roles.json
7. organizations.json
* Remember that we only add those instances there that are either:
    * a direct neighbor to a listed broadcasting program (see `data\00_setup\broadcasting_programs.csv`),
    * or are a direct neighbor of a direct neighbor to a listed broadcasting program