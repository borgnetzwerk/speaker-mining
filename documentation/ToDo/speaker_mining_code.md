# Speaker Mining Code
## Documentation cleanup
First, make a phase by phase pass where all is summarized and analyzed first.

## Disambiguation questions: 
* How is the OpenRefine match stored?
  * Idee: in einer neuen Spalte speichern - dafür einfach die existierende duplizieren und umbenennen in "open_refine_name" o.ä.

## Fix bugs
### Somehow, the third row of the Fernsehserien.de guest description seems to be missing.
It may have gotten lost in these steps:
1) writing the csv in step 2.1
2) converting the csv in step 3.1

## deduplication

## analysis and 
### Property distribution: gender/age/...
* how does this look like per many per occupation
* age: subtract episode release date from birthdate to get age at release
* Party affiliation
* Journalism house affiliation
* University affiliation

"The average page-rank for a person with property x is ..."

Make a list of all guests.
Then make a list of all their properties.
Then analyze all these properties and make a statistic of their values 

## visualization
Visualize everything from analysis

### Page-Rank like visualization
#### Class diagram
only instances
* All classes are grey
* All core classes have their specific colors

#### Instance diagram
no classes.
* Inherit the logic from the class diagramm, but transfer it to the instances.

##### Page Rank Diagram
* Node visualization, page rank increases size
  * Validation: Instances such as "ZDF" or "Markus Lanz" should be very big

##### Instance
Normalized stacked bar chart:
How much percent of the invited guests were male/female

Total | and then by each major occupation branch

Every time there is a bar, make two: One "by individual", one "by occurence". To be read as:
"30% of the invited reasearchers were female. When a researcher was guest, 10 % of them were female"
The first bar is by individual, meaning the same person being invited 1000 times has no impact and still gets counted as 1. The second bar is inverted: It does not matter if 1 female person gets invited 1000 times or 1000 persons 1 time each: it will count as 1000 invited female guests.


## Maybe we can still do this?
### Einschaltquoten
We have some PDFS on Einschaltquoten 


### Geneder inference
Description words with capital first letter and ending on "in" are an indicator of female gender

infering gender from a description is dangerous:
While the accuracy is high, we cannot make decisions on the inverse. So while we can increase our classification rate of female guests, the inverse is not true.
We can identify female gender from "-in" ending, as well as from terms like "Ehefrau" - but the inverse, a word not ending on "-in", is not automatically clear - a femal author may just be called "Autor" just as a male one.

It is adviced not to conduct this kind of mining.

### Description Semantification
Export a mapped entry in one language
Identify columns that may be mapped to another via similarity

Beschreibung: "Gärtner"
Occupation: "Gärtner"

Care that there is plenty of noise in there "ehem. Gartner an der Uni seines Vaters"


## Future Work
* Forbidden Features catalogue / Data Privacy catalogue
  * A catalogue for all reference that maybe should not be in the publically visible database
    * Person of color
    * Age
    * Gender
    * Everything that could be used to target / harass people, but is very important for scientists to analyze 
  * This catalogue should be behind closed doors, only internally accessible, and access is only granted to people who have a university / similar institution backing them and sign a contract that they will do no harm with this data. 
  * See for reference: 
    * living people protection class (P8274)
      * when used with living people this project falls under the category described in Wikidata's Living People policy
    * property that may violate privacy (Q44601380)
      * when this property is used with items of living people it may violate privacy; statements should generally not be supplied unless they can be considered widespread public knowledge or openly supplied by the individual themselves
    * property likely to be challenged (Q44597997)
      * when this property is used with items of living people it's likely to be challenged; as a result those statements should be supported by a reliable public source as suggested in Wikidata:Living people
* Plenty of further interesting properties usable for analysis:
  * assessment (P5021)
    * subject took the test or exam, or was assessed per test or method






## Intermediate Statistics
### 16.04.
otal graph nodes: 6276 | edges: 8581
Selected nodes for global tables: 6276 | edges: 8581
Core classes in selected graph: 7
Activity mode: runtime-or-structural
Per-core pool sizes:
  Q11578774 (broadcasting_programs): 86
  Q1983062 (episodes): 24
  Q214339 (roles): 527
  Q215627 (persons): 4366
  Q26256810 (topics): 63
  Q43229 (organizations): 1987
  Q7725310 (series): 182
