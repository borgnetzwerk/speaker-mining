# Notebook 21 Redesign — Clarifications
> Aggregated: 2026-04-26  
> Source: User annotations in `01_cell_analysis.md`, `02_data_flow.md`, `04_redesign_goals.md`

This document collects every user clarification made during the investigation and groups them by theme. Its purpose is to establish shared understanding before any redesign work begins. Nothing here is implemented — this is the agreed conceptual baseline.

---

## 0 — Governing Principles

All redesign decisions must be grounded in the existing principle documents:

- [documentation/coding-principles.md](../../coding-principles.md)
- [documentation/Wikidata/Wikidata.md](../Wikidata.md)

These are not background reading — they are constraints. Before any design decision, the question is: "does this comply with the coding principles and the Wikidata interaction guidelines?" If a proposed design conflicts with them, the design must change, not the principles.

---

## 1 — Event Sourcing Is Not Optional, It Is the Architecture

The event store is the single source of truth. This is not a performance optimization or a nice-to-have — it is a fundamental architectural commitment.

**C1.1 — Events are immutable and permanent.**  
No code may ever delete, truncate, or overwrite an event. Events may only be appended. If a past event is "wrong", the correct response is to write a new event handler that reinterprets the old events in a new way, or to emit a correction event. The original events remain.

**C1.2 — Everything else is a projection.**  
All CSV files, JSON files, parquet files, and in-memory data structures derived from the event store are projections. They are rebuildable. They are not the truth. If they are lost, they can be reconstructed from events.

**C1.3 — Projections are only written by EventHandlers.**  
No function outside an EventHandler may write a projection file. This is a hard boundary. An EventHandler reads events, reacts to them, and writes its projection. It does not respond to direct calls to "rebuild" outside the event lifecycle.

**C1.4 — EventHandlers cache their progress.**  
Every EventHandler tracks the last event sequence number it processed. On the next run, it reads only events it has not yet seen. It does not scan the full event store from the beginning on every call. This is the mechanism that makes the system efficient at scale: the cost of an update is O(new events), not O(all events).

**C1.5 — Querying handler state means asking the handler, not reading a file.**  
If we need `existing_relevant_qids`, we ask the RelevancyHandler. The handler will process any events it has not yet seen, update its projection, and respond. We do not read `relevancy.csv` directly as a side-channel. The handler is the interface.

**C1.6 — The "materializer" concept is deprecated.**  
In a correct EventHandler-based system, a separate `_materialize` function that rebuilds all projections from scratch is fully irrelevant. If we need a projection, we add an EventHandler. If we need it updated, we ask the EventHandler. There is no scenario in this design where a monolithic rebuild function is needed. The `materializer.py` module and its `_materialize` function are not carried forward into the redesign.

**C1.7 — Every event type requires a catalogue entry.**  
Each event type must be documented with: who emits it, who reads it, what state change it represents, required fields, and backward-compatibility notes. The catalogue should also include rough statistics (e.g., "56,000+ `query_response` events in the store — this type is stable and must not be renamed"). Event type names should be reviewed against the glossary — if the name of a type is on the "to rename" list, that affects the catalogue entry.

**C1.8 — All existing events must remain interpretable forever.**  
The event store already contains ~56,000 events written by v3 code. The redesign cannot assume a clean event store. Every EventHandler in v4 must be able to correctly read and interpret every event that was written by v3, even if v4 introduces new event types or restructures how state is modelled. Backward compatibility with the existing event log is a hard constraint.

**C1.9 — Two classes of event emitter exist.**  
(a) The **traversal engine** emits primary discovery events: it fetches data from Wikidata (or cache) and records what it finds — entity_discovered, triple_discovered, entity_expanded, query_response. These are factual records of observations.  
(b) **Derivation handlers** may also emit events representing computed conclusions: relevance_assigned, class_membership_resolved. These are not observations but inferences, and they are emitted by an EventHandler as a way to persist a computed conclusion in the event log so other handlers can react to it. An EventHandler that emits events is a derivation handler; an EventHandler that only reads events and writes a projection file is a pure projection handler. Both are valid.

---

## 2 — The Checkpoint System Must Be Replaced

The current checkpoint system is architecturally at odds with event sourcing.

**C2.1 — Checkpoints are not needed for resume.**  
If the event log is correct and all EventHandlers track their progress, then "resume where we left off" is the natural default behavior of every run. Every event is already a checkpoint. There is no need for an artificial outer checkpoint wrapper.

**C2.2 — The checkpoint system should be deprecated.**  
Everything in a checkpoint snapshot other than the event store itself is a derived projection. It can be reconstructed. Storing 7.3 GB of checkpoint snapshots that duplicate projection data is unnecessary. If something cannot be reconstructed from the event store, that is a code defect — we must fix the code to emit the right events, not preserve the derived file in a snapshot.

**C2.3 — Backing up the event store is critical and separate from checkpointing.**  
"Checkpoint" and "backup" are not the same thing. Losing the event store is the worst thing that can happen to the system — it is unrecoverable. The event store must be backed up. That backup is a copy of the JSONL chunk files and nothing else. It has nothing to do with projection snapshots.

**C2.4 — The revert/rollback concept is dangerous and must go.**  
The current Step 3 (decide resume mode) includes a "revert" mode that can roll back event state. This is incompatible with the immutability principle in C1.1. No code should be able to delete or roll back events. This mechanism must be removed. If projections are stale or incorrect, we reset the handler's progress cache (not the events) and let it re-derive.

---

## 3 — Relevancy Propagation Must Be Generic and Rule-Driven

**C3.1 — The current P106/role example is only one case of a general pattern.**  
The goal is not just "propagate via P106 from person to role". The goal is a general engine: given a set of rules, propagate relevancy through triples. The full pattern is:

> Subject A (satisfying some subject requirement, e.g. is-relevant AND is-instance-of human) → via Property P (satisfying some property requirement, e.g. allowed predicate) → Object B (satisfying some object requirement, e.g. must be instance/subclass of "episode")

Any combination of subject requirements, property requirements, and object requirements must be expressible as a rule. Adding a new propagation rule must require only a change to the rules configuration — no code change.

**C3.2 — Propagation can also be reverse-directional.**  
Relevancy can travel from object to subject. Example: a season that "has part" (P527) a relevant episode should itself become relevant. The engine must support both forward propagation (subject → object) and backward propagation (object → subject), as defined by the rules.

**C3.3 — Rules are owned by config, not code.**  
`relevancy_relation_contexts.csv` is the owner of propagation rules. Code reads and applies the rules. Code never encodes a specific subject/property/object combination as a hardcoded check.

**C3.4 — "Core-class instance" is an unstable concept; class expansion requires extra care.**  
The distinction between "instance of a core class" and "subclass of a core class" is not a clean binary. What we want varies per class: for roles, we want subclasses; for persons, we want instances that satisfy additional conditions (e.g. appeared as a guest). The concept of "core-class instance" is not a sufficient predicate for inclusion.

Furthermore, class node expansion must be treated with extreme caution. A class node like "journalist" has potentially thousands of P31 instances across all of Wikidata. Fully fetching a class node as if it were an instance would be catastrophically expensive. Rules that govern when a class node is traversed must be designed conservatively and explicitly — not as a default fallthrough.

**C3.5 — "Core Class Instance" and "Core Class Subclass" are distinct, and both are always needed.**  
An entity that is an instance of a core class is a **Core Class Instance**. An entity that is a subclass of a core class (via P279 chain) is a **Core Class Subclass**. These are two different things and must always be tracked separately. Which one is relevant for a given use case depends on context: person analysis cares about instances; role analysis cares about subclasses; episode analysis cares about instances but may use subclasses for categorization. The system must maintain both and expose both with full context. Conflating them into a single "core class entity" concept is what produced the roles bug.

**C3.6 — Sub-projections within a core class are valid.**  
Within a core class, further distinctions may be needed. For persons, we may need a "guest" sub-projection (persons who appeared as guests), a "host" sub-projection, or others. These are not new core classes — they are filtered views within an existing core class. The output handler for persons may produce multiple sub-projections if the rules and context support it. These sub-projections are output-only artifacts.

**C3.7 — Relevancy rules require active monitoring and amendment capability.**  
As the graph grows, approved rules can produce unexpected matches. For example, a "part of series" rule might correctly propagate to relevant seasons but also incorrectly mark "Top 1000 Streamed Episodes in Canada" as relevant because it coincidentally uses the same property. The rule system must provide visibility into which rules caused which relevancy assignments, and must support adding exclusion conditions or priority overrides without breaking correct existing propagations.

---

## 4 — Configuration Must Live in an External File

**C4.1 — The notebook config cell is the wrong pattern.**  
When configuration lives in a notebook cell, every config change marks the notebook as modified in git, creating noise in commit history. The correct pattern is: a dedicated config file that the notebook reads. The notebook cell becomes a reader, not the config itself.

**C4.2 — The config file must be self-documenting.**  
The config file must be human-readable and contain enough inline documentation that a user can understand every parameter by opening the file — without reading the notebook code. Each parameter needs a comment explaining what it does and what its options are.

**C4.3 — The config file must be auto-created with defaults on first run.**  
If the config file does not exist, the notebook should create it with all defaults and immediately raise an error asking the user to review and configure it before continuing. This prevents silent use of wrong defaults.

---

## 5 — Graceful Stop and Heartbeat Are Universal Requirements

**C5.1 — Graceful stop is not special to Step 6.**  
Every cell in every notebook that performs writes must handle user interruption gracefully. The stop handler must be universal. Any cell that runs for more than a few seconds and touches the event store or projections must not be interruptible in a way that leaves partial state.

**C5.2 — Heartbeat is not special to Step 6 either.**  
Any cell that can run for more than one minute must emit a heartbeat visible in the cell output. The heartbeat must update at least every minute and every 50 network calls. This is not optional for a pipeline that can run for hours. Users need to be able to see what the system has been doing without waiting for it to finish.

---

## 6 — The Integrity Pass Must Not Be Necessary

**C6.1 — A correct design needs no post-hoc repair step.**  
The current Step 6.5 (node integrity pass) exists because the expansion logic can produce a state that is internally inconsistent — entities referenced in triples but not fully discovered. In a correct redesign, this situation should never arise: if a triple references a QID, that QID should be discovered as part of the same transactional expansion that produced the triple.

**C6.2 — A final validation check is acceptable; a repair step is not.**  
It is fine to have a concluding cell that checks all invariants and reports any violations. It is not fine for that check to be a load-bearing step that must run to produce correct output. Correctness must be ensured during expansion, not patched after it.

---

## 7 — Seed Completion Logic Needs Careful Reconsideration

**C7.1 — "Seed already complete" is not a safe skip condition.**  
The current expansion engine marks a seed as complete and skips it in subsequent runs. But what does "complete" mean if the expansion logic has changed? If new predicates were added to the traversal config, or if new entities became reachable that weren't before, a previously "complete" seed may be incomplete under the new rules.

**C7.2 — Event sourcing should handle this naturally.**  
In a correct event-sourced design, the `fetch_engine` emits events for every discovery. On re-run, the engine checks whether a seed has a `seed_fully_fetched` event (or equivalent) and whether the config that was current at that time matches the current config. If they differ, re-fetching is needed.

**C7.3 — Fetch rules govern which nodes are full_fetched; the full_fetch itself is always a complete link retrieval.**  
"Fetch rules" control the decision of *whether* to `full_fetch` a node. Once that decision is made (`fetch_decision`), the `full_fetch` always retrieves all incoming and outgoing claims for the node. Selectivity belongs in the `fetch_decision` layer, not in the fetch itself.

**C7.4 — The boundary between fetch rules and relevancy rules must be explicitly designed.**  
There is potential overlap: if `fetch_decision` is governed by fetch rules, and relevancy propagation is also governed by relevancy rules, we must be explicit about whether these are the same rule set or separate ones. A preliminary separation: fetch rules say "full_fetch this QID"; relevancy rules say "this entity is relevant". These are different concerns that may reference each other but must remain separate configurations.

**C7.5 — The ClassHierarchyHandler answers Q5 (class resolution trigger).**  
A dedicated derivation handler — the ClassHierarchyHandler — reads `entity_discovered` and `triple_discovered` events. Whenever it sees a new class QID referenced in a P31 or P279 claim, it triggers the P279 upward walk for that class if not already resolved. It owns `class_resolution_map.csv` and the full class hierarchy projection. It tracks which classes are referenced by the current graph ("active") vs known but not yet used. Class resolution is thereby continuous and incremental — O(new class QIDs per run), not O(all active classes at startup). Most of the required BFS algorithm already exists in `class_resolver.py`; the change is making it reactive rather than upfront-exhaustive.

---

## 8 — Output-Only Projections May Be Written at the End

**C8.1 — Intermediate state belongs in the event store, not in CSV files.**  
CSV projections that are only used as output (consumed by downstream notebooks but never read back by Notebook 21 itself) do not need to be written at intermediate steps. They can be written once, at the end of the run, as the final export step.

**C8.2 — Internal state must flow through the event log.**  
Any state that needs to survive across cells or runs — entity documents, class hierarchies, relevancy assignments — must be represented as events or as EventHandler projections. It must not be written to CSV and then read back from that CSV as if the CSV were the source of truth.

**C8.3 — Triple events must preserve qualifier and reference context.**  
When a triple is stored as an event, the event must include qualifier context alongside the core `(subject, predicate, object)`. At minimum, qualifier property PIDs should be stored (pipe-separated) so that a consumer can determine whether a qualifier exists and what kind it is without needing to re-read the full entity document. This preserves the ability to implement time-sensitive claim filtering (TODO-041) without requiring a full entity re-fetch per triple.

---

## 9 — Fallback String Matching Belongs in Phase 3, Not Phase 2

**C9.1 — Phase 2 is Wikidata graph expansion only.**  
Notebook 21 and the entire Phase 2 candidate generation phase is scoped to Wikidata-rooted graph traversal. String matching against arbitrary text sources, reconciliation against external databases, and any logic that requires non-Wikidata data sources are out of scope for Phase 2.

**C9.2 — Fallback string matching must move to Phase 3.**  
If fallback string matching is ever re-implemented, it belongs in its own notebook under Phase 3. The current Steps 8 and 9 (string matching + re-entry) must be removed from Notebook 21. Their presence in Phase 2 is architecturally incorrect and adds dead code to the normal run path.

---

## 10 — Diagnostic and Analysis Cells Belong in Analysis Notebooks

**C10.1 — Step 2.4.1 (conflict analysis) can move.**  
`inspect_class_resolution_conflicts` is a diagnostic output — it produces no pipeline artifacts. Diagnostic cells that are useful for investigation but not required for correct pipeline execution should be in a separate analysis notebook, not in the production pipeline notebook.

**C10.2 — Production notebooks should be runnable top-to-bottom without manual intervention.**  
Every cell that is NOT pure diagnostic work should produce correct results when the notebook is run unattended. If a cell is only useful for interactive investigation, it belongs elsewhere.

---

## 11 — A Glossary Is Required Before Implementation

Before any module or data structure is designed, the core vocabulary must be established. The current codebase uses terms ("materializer", "hydration", "expansion", "relevancy", "core-class instance") that are either ambiguous, misleading, or overloaded. Designing new code on top of unclear terms will reproduce the same confusion that made the current architecture hard to reason about.

**C11.1 — Define every key term before using it in design.**  
The glossary must cover at minimum: what is a "core class", what is a "core class entity", what is "relevant", what does "expansion" mean, what does "hydration" mean, what is an "event", what is a "handler", what is a "projection". Each term needs a precise, agreed-upon definition.

**C11.2 — Evaluate whether current terms should be renamed, split, or deprecated.**  
Some current terms may be fundamentally imprecise. For example, "expansion" currently conflates fetching a node's Wikidata data and adding it to the graph with traversing its links outward — these may be two distinct operations that deserve distinct names. The glossary exercise is also a naming exercise.

**C11.3 — The glossary is a prerequisite to implementation, not optional.**  
Concepts that cannot be clearly defined cannot be correctly implemented. If a term's definition cannot be agreed upon in one sentence, that is a signal that the concept needs to be broken apart before code is written.

---

## 12 — Rules Must Be Designed to Expand, Not to Fit Known Cases

This is perhaps the most important principle for the redesign. The current architecture broke down repeatedly not because the implementation was buggy, but because the design was overfitted to the small set of known cases at the time of writing. Every time a new case was found (role subclasses, bidirectional propagation, class-node targets), a patch was added. The redesign must break this cycle.

**C12.1 — Do not design for the cases we know. Design for a rule space that can accommodate cases we do not know yet.**  
The moment we write code that says "if it's a role, use subclass mode; otherwise, use instance mode", we have made an assumption that will be wrong the first time a new core class behaves differently. Instead, we should express: "for each entity, evaluate it against a set of rules; the rules determine what is collected." Adding a new case then means adding a rule, not changing code.

**C12.2 — Begin with granular, individually-expressible rules; cluster them only after the full rule space is understood.**  
It is not a problem if the initial rule set looks complex or verbose. A complex but correct rule set is infinitely preferable to a clean but wrong abstraction. We have time to simplify later, once we understand which rules share the same shape. We do not have time to undo a wrong fundamental assumption.

**C12.3 — Real-world ontological complexity will always exceed our current model.**  
The class resolution conflict analysis showed 1,381 rows with ontological ambiguity — entities that legitimately resolve to multiple core classes, like "Arabic Speaker" being both a role and a person. We cannot eliminate this complexity by picking one. Our rule system must be able to represent multi-class membership, priority ordering, and override rules. A design that forces entities into exactly one bucket will break on the first real-world edge case.

**C12.4 — The naming convention is not yet decided.**  
We do not yet know whether we will have `guest_persons`, `host_persons`, `role_subclasses`, or something else entirely. We do not know if there are role instances in addition to role subclasses. We should not commit to naming before the rule space is mapped. The naming will emerge from the rules, not the other way around.

**C12.5 — A fundamentally wrong design is worse than a complex correct one.**  
It is acceptable to have a rule catalogue that looks verbose or over-specified. It is not acceptable to have a rule catalogue that encodes false assumptions. When in doubt, be more explicit rather than more concise. Conciseness can be added later; correctness cannot be patched in indefinitely.

---

## 13 — Performance Is a Symptom, Not a Goal

**C13.1 — The goal is correct event-sourced design.**  
Runtime speed is an indicator of design quality, not the primary objective. A correct design where all EventHandlers track their progress and only process new events will naturally produce fast runs — not because we optimized for speed, but because correct incremental processing is inherently efficient.

**C13.2 — The 20-minute runtime is a symptom of full-scan-on-every-run.**  
The root cause is not "the event store is too big" — it is that handlers re-scan from the beginning instead of continuing from where they left off. Fix the design; the runtime fixes itself.

---

## 14 — basic_fetch, full_fetch, and fetch_decision Are Three Distinct Operations

From the glossary clarifications and naming decisions (`11_naming_decisions.md`), "expansion" is decomposed into three named operations:

**C14.1 — `basic_fetch` is the minimalistic, structured, mass-capable fetch.**  
`basic_fetch` retrieves: label, description, aliases (configured languages + Wikidata default) + P31 (instance-of) + P279 (subclass-of) claims only. Enough to know *what a node is* without knowing everything it links to. Because the payload is fixed and predictable, `basic_fetch` can be issued for many nodes in a single batch call, significantly reducing Wikidata API burden. The old term "hydration" is retired and replaced by `basic_fetch`.

**C14.2 — `full_fetch` retrieves all claims for a single node.**  
When a node is `full_fetch`ed, all outgoing and incoming Wikidata claims are retrieved and stored as events. This is unbounded — the number of claims is unknown in advance. `full_fetch` is triggered by the `fetch_engine` for nodes that have been queued by a `fetch_decision`. The pair `basic_fetch` / `full_fetch` is intentional: basic retrieves the fixed identity payload; full retrieves everything.

**C14.3 — `fetch_decision` is the decision layer, distinct from both fetch operations.**  
After a node is `full_fetch`ed, `fetch_decision` inspects the newly stored triples and decides which referenced QIDs should be `full_fetch`ed next. This is governed by fetch rules. The cycle is: `full_fetch` → `fetch_decision` → `full_fetch` → ... The engine that orchestrates this cycle is the `fetch_engine`. "Expand"/"expansion" are retired from v4 vocabulary.

**C14.4 — Minimizing Wikidata API burden is a design constraint, not an optimization.**  
Per `Wikidata.md`, responsible API access is required. `basic_fetch`'s mass-batch capability is architecturally valuable precisely because it reduces API calls while still providing the identity data needed for class resolution and relevancy decisions.

---

## 15 — Relevancy Semantics: What Makes an Entity Relevant

**C15.1 — Seeds are authoritatively relevant by definition.**  
A seed entity (broadcasting program in `broadcasting_programs.csv`) is relevant because we designated it as a target of interest. No propagation rule, no class membership, no graph distance is required. Seed relevancy is axiomatic.

**C15.2 — Relevancy propagates via approved triples following participation semantics.**  
Concrete example: Markus Lanz (talk show) is a seed → seasons "part of" it become relevant → episodes belonging to relevant seasons become relevant → guests appearing in relevant episodes are relevant speakers → hosts of relevant episodes are relevant speakers.

**C15.3 — Topic mention does NOT propagate relevancy.**  
If an episode has "topic: Barack Obama", Obama is not a speaker — he was referenced, not present. This triple must not trigger relevancy propagation. He becomes relevant only if he later appears as a guest. Relevancy rules must be designed to propagate through *participation* relationships only, not through subject/topic references. This is a critical correctness constraint.

**C15.4 — Relevancy is binary and monotonically increasing.**  
An entity is either relevant or not. Once relevant, it cannot become not-relevant. Nothing in the system reduces relevancy. The propagation model is strictly additive. Confidence levels are not needed.

**C15.5 — The output separation "relevant" / "not-relevant" must be preserved.**  
Entities resolved to a core class but not yet reachable via any propagation path are "not relevant" and appear in `not_relevant_core_<class>.json`. This distinction is data, not a design failure — not-relevant entities may become relevant in future runs as more seeds are processed.

---

## 16 — Phase 3 Output Contract

**C16.1 — Phase 2 sets the output contract; Phase 3 adapts.**  
Phase 3 (entity disambiguation) was originally designed to consume Phase 2's old output format. In the redesign, we should not constrain Phase 2's output structure to match Phase 3's current input expectations. The new Phase 2 should produce the richest, most correctly-structured output it can. Phase 3 will be updated separately to consume it.

**C16.2 — Provide maximum context; let downstream consumers select what they need.**  
Rather than producing the minimum required by the current Phase 3, Phase 2 should produce output that includes instances, subclasses, sub-projections, qualifier context, and lookup indices — enough that any reasonable downstream consumer can work with it. Downstream notebooks can select the view they need from a richer structure, but they cannot reconstruct context that was never stored.

---

## Summary: What the Redesign Must Get Right

| Principle | Requirement |
|-----------|-------------|
| Event immutability | No code may delete or overwrite events; only append |
| Handler progress tracking | Every handler persists its last-processed sequence; restarts from there |
| Projection ownership | Only EventHandlers write projections; no materializer |
| Two emitter types | Traversal engine emits primary events; derivation handlers emit computed events |
| Events catalogue | Every event type documented; old events backward-compatible forever |
| Config externalization | Config in a file, not a cell; file is self-documenting |
| Relevancy engine | Generic rule-based, configurable subject/property/object requirements, bidirectional |
| Relevancy semantics | Seeds authoritative; propagates via participation; topic mentions excluded; binary, monotonic |
| Rules monitoring | Rule verdicts must be visible and amendable; exclusion overrides must be possible |
| Class node caution | Fetch rules for class nodes must be explicit and conservative; class nodes are not instances |
| Instance + Subclass both | Both Core Class Instances and Core Class Subclasses tracked; conflating them was the roles bug |
| Triple qualifiers | Triple events preserve qualifier PIDs; enables time-sensitive filtering without re-fetch |
| Three operations | `basic_fetch` (fixed identity payload, mass-batchable), `full_fetch` (all claims), `fetch_decision` (traversal decision layer) are distinct |
| Wikidata API burden | Design for minimum API calls; `basic_fetch`'s mass-batch capability is a first-class design tool |
| No artificial checkpoints | Event store continuity is the resume mechanism |
| Event store backup | Backing up chunk files is critical; projection snapshots are not |
| Phase 2 scope | Wikidata graph traversal only; no string matching |
| Phase 3 contract | Phase 2 sets the output contract; Phase 3 adapts to it, not vice versa |
| Integrity correctness | `full_fetch` + `fetch_decision` must produce consistent state; no post-hoc repair required |
| Fetch rules vs relevancy rules | Distinct rule sets: fetch rules = `fetch_decision` inputs; relevancy rules = classification decisions |
| Output projections | Written once at end; internal state flows through event log |
| Graceful stop + heartbeat | Universal; every production cell, not just Step 6 |
| Glossary first | All key terms defined and agreed before any module is designed |
| Rules before abstractions | Express rules individually and correctly; cluster only once the rule space is understood |
| No false assumptions | A complex correct rule set is better than a clean wrong one |
