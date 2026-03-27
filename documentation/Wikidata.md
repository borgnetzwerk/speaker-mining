# Wikidata Service Interaction Guidelines

This document defines how this repository should interact with Wikidata and related Wikimedia services.

## Purpose

The goals are:

1. preserve data quality and reproducibility,
2. reduce service burden,
3. avoid repeated and unnecessary queries,
4. keep requests identifiable and policy-compliant.

## Scope

These rules apply to:

1. Wikidata Query Service (SPARQL),
2. Wikidata/MediaWiki API endpoints,
3. reconciliation-related endpoints used for candidate generation.

## Authoritative Scope Note

This is the authoritative guidance for Wikidata service interaction behavior.

For workflow ownership and execution order, see [workflow.md](workflow.md).
For output contracts, see [contracts.md](contracts.md).

## Required Request Identification

All outbound requests should clearly identify the calling program.

1. Send a descriptive User-Agent that includes project/program identity.
2. Include a contact channel (for example repository URL or maintainer contact).
3. Where supported by the endpoint, include a tool/application identifier parameter.
4. Log request metadata with each cache artifact:
	- endpoint,
	- normalized query,
	- query hash,
	- timestamp (UTC),
	- notebook or process step origin.

## Caching Conventions

Caching is mandatory by default.

1. Any successful query should be cached and not repeated unless the last execution is older than 365 days.
2. Cache keys should include:
	- endpoint,
	- normalized query text,
	- key parameters,
	- response format.
3. Cached results should be stored with metadata sidecars or equivalent structured fields.
4. If the same query is requested again within 365 days, use cache unless there is an explicit override reason.
5. Override reasons should be documented (for example endpoint migration, parser bug fix, schema requirement change).

Recommended cache location pattern:

1. `data/20_candidate_generation/wikidata/raw_queries/` for raw query artifacts,
2. index/summary files in `data/20_candidate_generation/wikidata/`.

## Request Pacing And Load Shedding

1. Keep at least 1 second delay between consecutive outbound queries to the same service.
2. Do not run large query bursts without pacing.
3. On 429/503 or similar load signals, back off exponentially with jitter.
4. Prefer single-threaded request flows for heavy SPARQL workloads unless a stronger case is documented.

## Query Reuse Policy

1. Query once, reuse many times from cache.
2. If a query has already been executed successfully and is newer than 365 days, do not rerun.
3. Prefer enriching local index tables over repeatedly calling remote services.

## Chunkable Query Design (Refinement Track)

Queries should be designed so large result sets can be fetched in stable chunks.

### Why

If a target set is very large (for example 10,000 inlinks), naive pagination can repeatedly return the same subset.

### Current Design Direction

1. Use deterministic ordering (for example stable item identifier ordering).
2. Prefer cursor/range-based chunking over unstable repeated pulls.
3. Persist chunk checkpoints so resumed runs continue from the last confirmed boundary.
4. Use controlled overlap only where needed, then deduplicate locally.

### Example Pattern

1. Plan chunks of 200 items.
2. Persist progress markers per chunk.
3. Execute approximately 50 chunks for 10,000 items, with optional overlap chunks for integrity checks.
4. Validate final cardinality and duplicate rate before downstream use.

### Still To Be Refined

1. Canonical chunking strategy per query family.
2. Standard overlap size and merge policy.
3. Completeness verification thresholds.

## Best Practices References

Follow and periodically review official guidance:

1. Wikidata Query Service page: https://www.wikidata.org/wiki/Wikidata:SPARQL_query_service
2. MediaWiki API etiquette: https://www.mediawiki.org/wiki/API:Etiquette
3. Wikimedia User-Agent policy: https://foundation.wikimedia.org/wiki/Policy:Wikimedia_Foundation_User-Agent_Policy

## Community Suggestions And Quotes

Store operational suggestions here before formal adoption.
Treat quoted suggestions as proposals until verified and integrated into the policy sections above.

* "We should try the alternative endpoints for faster reconciliation. There is one specifically made for reconciling people, and at least one support CirrusSearch filters."