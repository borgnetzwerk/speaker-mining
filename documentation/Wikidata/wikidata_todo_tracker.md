# Wikidata TODO Tracker

Date created: 2026-03-31
Scope: Wikidata candidate-generation and graph-quality tasks only

## Status Legend

- [ ] not started
- [~] in progress
- [x] completed

### Learn from backoff patterns
If we run into backoff patterns, congestion control should kick in. We need to identify if we can slightly change our delay to not run into backoff patterns. By linking to our heartbeat, we can check once every minute if we hit a backoff pattern (e.g. at least one backoff in the last minute in the last three heartbeats.).
If we detect such a pattern, we react and slightly increase our query delay (e.g. by 5%). During the next heartbeat, we will know if that helped - otherwise, the rules above apply and we increase again.

Eventually, we should arrive at a delay that triggers no backoff. If that happens, we print it, memorize it, and try to fine-tune (e.g. reduce it by 1% again), until we hit backoffs again. This will eventually tell us a range within which we don't encounter backoffs. This should be printed then and once again at the every end of the cell's runtime, so that the user can configure it later. Likely, we should also have a persisting list (e.g. a csv) where we can track these tests from run to run. This way, when a user specifies a delay which we know to be backoff prone from previous runs, we can throw them a warning right away when they run the configuration cell.