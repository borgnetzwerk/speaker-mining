# V2 Restart

## Principles

### Layered Matching Model

The disambiguation strategy is hierarchical. Higher layers constrain lower layers.

1. Layer 1: Broadcasting Program (already unified from setup, no disambiguation needed). This layer is the backbone of our matching.
2. Layer 2: Episode alignment across sources, primarily by time and publication signals. Episodes are our main alignment target - if we can match episodes between sources, this gives us plenty of context for all lower layers.
3. Layer 3: Person alignment, primarily via an already aligned episode. Guests of aligned episodes can be mapped to each other across sources relatively easily. With lower certainty, however, even guests without matched episodes can be aligned: if they share the same name, this is a good indicator; and if their properties are similar, this certainty increases.
4. Layer 4: Role and organization alignment, if possible. Low probability that matches are possible at all, since mainly wikidata has structured notations of these, but maybe these can be aligned with ZDF_archiv guest or episode descriptions or with fernsehserien.de guest descriptions, but also least relevant.

Aligning properties (including roles and associated organizations), which are sometimes hidden in descriptions and metadata, is very tricky, since in any format outside wikidata, all kinds of properties are grouped as "description". We will need to inspect plenty of different columns to find candidates for matching properties.

### Inspectable Examples, Analysis, and Handovers
31_entitiy_disambiguation will iteratively evolve.  

#### Examples
For every artifact we create, we should create an example version. This is intended to be easily digested and learned. Thus, it only contains one single representative entry.

#### Handovers
* `documentation/00_actionably_handover`

## Sequence of Actions
### Phase 1: Planning
1. Ingest 00_immutable_input.md. This is immutable and is authoritative.
2. Analyze 01_approach.md. Improve if needed. 
3. Construct 02_implementation.md. Groundwork is layed, a full implementation specification and plan is required.

### Phase 2: Improving
Only when Phase 1 is completed:
Inspect 10_refinement.md. Analyze if amything can be learned from the legacy artifacts. If so, improve the documentation accordingly.

### Phase 3: Implementation
Execute the implementation plan.