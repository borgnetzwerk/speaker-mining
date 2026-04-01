# Documentation Hub

This folder is the contributor handbook for the repository.

Use this as the single place to understand how the repository works, what standards to follow, and what needs work next.

## Read In This Order

1. [repository-overview.md](repository-overview.md)
2. [workflow.md](workflow.md)
3. [contracts.md](contracts.md)
4. [notebook-observability.md](notebook-observability.md)
5. [mention-detection.md](mention-detection.md)
6. [coding-principles.md](coding-principles.md)
7. [open-tasks.md](open-tasks.md)
8. [findings.md](findings.md)
9. [context/README.md](context/README.md)

## Scope Of This Documentation

- Explain the end-to-end architecture and phase boundaries.
- Document executable workflow and phase ownership.
- Keep output contracts aligned with actual generated CSVs.
- Provide clear contributor rules for notebooks and process modules.
- Track all open and solved work in one maintained location.
- Preserve technical findings in one aggregated findings document.

## Authoritative Sources By Topic

- Workflow execution order and phase ownership: [workflow.md](workflow.md)
- Architecture and module map: [repository-overview.md](repository-overview.md)
- Output file contracts and schema headers: [contracts.md](contracts.md)
- Notebook run/network observability and append-only event logs: [notebook-observability.md](notebook-observability.md)
- Mention detection conventions and parsing rules: [mention-detection.md](mention-detection.md)
- Contributor standards and change discipline: [coding-principles.md](coding-principles.md)
- Open and solved work items: [open-tasks.md](open-tasks.md)
- Research and evidence notes: [findings.md](findings.md)

## Tracking Model

- There is one unified work item type in [open-tasks.md](open-tasks.md).
- Items are sorted by priority (`high`, `medium`, `low`) and solved items are listed at the end.

Use the inline template at the top of [open-tasks.md](open-tasks.md) for new entries.

## Maintenance Rules

- If notebook order, output schema, or process modules change, update `repository-overview.md`, `workflow.md`, and `contracts.md` in the same PR.
- If a bug, gap, or improvement is discovered, add one entry to `open-tasks.md`.
- Keep `findings.md` as the aggregated evidence reference.
- When mentioning a governed topic in any other document, link to its authoritative file instead of copying long operational lists.

## Historical Context

- [background.md](background.md)

## Supporting Assets

- [visualizations](visualizations)
- [OpenRefine](OpenRefine)