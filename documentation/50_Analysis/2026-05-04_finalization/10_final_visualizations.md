# Final visualizations
We currently have over 300 visualizations. This breadth of analysis tools was primarily used to identify the most interesting information and experiment with ways to visualize it. Now, we need to focus on the final visualizations, the small set of high-quality visualizations that will represent the results of all our work.

For this, we have selected the following visualizations:
0. table of the show statistics
1. show comparison age violin plot
2. show comparison gender lines over time
3. party over gender stacked bar charts
4. page ranked node graph
5. Table of the property distribution
6. Gender appereances Area graph over age on X axis: What age are individuals when they appear, visualized by gender.

And maybe a sunburst of the occupation hierarchies.


## The context files

### Visualizations_Critique
file: `documentation/50_Analysis/2026-05-04_finalization/reference/Visualizations_Critique.html`

A small set of the 300 existing visualizations was analyzed by Claude Design, reviewed and critiqued.
While some aspects are false interpretations, this file generally contains vast amount of great tips and suggestions. A few highlights:

* Examples for false:
  * "Four copies of every coverage chart". 
    * False, we only have four coverage charts in total.
  * "Per-guest beats per-appearance. Where the two correlate at r > 0.9 (which they do for all 11 properties), publish only per-guest. Footnote the per-appearance variant if you must."
  or
  "Don't ship sparse charts."
    * Generally a good hint, but we sought to first produce every possible visualization and later decide which are most meaningful. The hint on adding a footnote on correlation however is a good suggestion.

* Some Examples of the many great suggestions
  * Almost everything in this file. 
    * "Overlapping data labels", "Labels cut off the canvas", "Shows in arbitrary order", ...
      * All above are issues we have identified and need to fix
    * All redesigned visualizations on the right side
      * All are much more visually pleasing, much better designed, much more skillfully compressing and highlighting information
        * But: One exception, "Female share within each occupation" assumes a binary gender. What we can do instead is always annotate the "male" aspect, still primarily compare it to female, but keep a the others in mind as well: A segment with 70 % male may have 29% female and 0.9% non-binary and 0.1% Agender, but the main thing is that it is 70 % male.

### Priority_Visualizations
file: `documentation/50_Analysis/2026-05-04_finalization/reference/Priority_Visualizations.html`

## The final visualizations

### 0. Show statistics table

See segment starting with
```
*<div class="ftitle">Talk shows · sample &amp; demographics</div>
    <div class="fsub">Sorted by total appearances · 9 German shows + StarTalk reference · 2003 → 2025</div>
```

On the columns existing there:

* Show
  * Should be named "Broadcasting Program"
* Episodes
* Appearances
* Unique guests
* Reuse rate
  * Can be dropped, almost meaningless
* Female % (of known)
  * Change to "Male %" or similar - is not binary, so just counting female is not enough to highlight the issue.
* Median age
* Span
* Appearances over time
  * Graph seems releatively meaningless. Maybe wasted space? Maybe add "Male % over time" or similar

Some columns that may be missing:
* After "Unique Guests": "Guests with Wikidata entry" or similar, so we can show on how many we have what data
* Similarly interesting column: Show where we got the episodes from: On how many episodes do we have an entry from
  * ZDF Archive
  * Wikidata
  * Fernsehserien.de

For any bar / color in the table: Always keep the same color to visualize the same show.

### 1. Age at appearance
Suggestion looks good. Good start, let's improve it once it's implemented.
Regarding color coding, stick to the show specific colors. Also a suggestion for the bars in the table above: Always keep the same color to visualize the same show.

### 2. Female share over time — line chart
Good start, but: Gender once again assumed binary.
Can be redeemed with a "one-line-per-gender" approach. Slight issue: the labels are unreadable since they all stack in the end - keep a dedicated legend. As always: maintain the color by show.


### 3. Party × gender — stacked bar

### 3a
Here is where we diverge:
* `documentation/50_Analysis/2026-05-04_finalization/reference/ Visualizations_Critique.html` had a very nice visualization: "Party affiliation share, by show". We should implement this.

#### 3b
If we want to identify something like gender per party, we should do the following:
* Build a compact implementation of "Female share within each occupation" (now "Male share by property, according to broadcast program appearance" or similar), and make it modular:
  * Have multiple properties side by side, especially:
    * age (derived)
      * Grouped in segments of 10 years
    * occupation
    * position held
    * member of political party

### 4. Guest co-appearance network — PageRank
Good first implementation. 

We should implement a single pipeline that outputs multiple layouts (configurable from file), with multiple different color schemes (once by party affiliation, once by gender, once by occupation), with multiple different edge logic and total node number.


### 5. 11 properties · coverage, cardinality, top values
Currently:
* Distinct values
* Top-3 share
* Top values
  * Generally good, but Maybe there is a more meaningful column to be had here. Good for Item-Values, but for strings or quantities, this is wasted space.

Thus, overall:
* Orient at "Property coverage by show" from `documentation/50_Analysis/2026-05-04_finalization/reference/ Visualizations_Critique.html`.


### 6. Occupation hierarchy — sunburst
Important: Use the Wikidata class hierarchy.