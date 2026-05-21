# Contributing

## Setup

1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Notebooks are in `speakermining/src/process/notebooks/` — run in the order defined in [`documentation/workflow.md`](documentation/workflow.md)

## Contributor Standards

All engineering practices are documented in [`documentation/coding-principles.md`](documentation/coding-principles.md):

- Phase ownership and write boundaries: each phase writes only to its own `data/<phase>/` folder
- Notebook conventions: orchestrate in notebooks, logic in `speakermining/src/process/` modules
- Output contracts: if a schema or filename changes, update `documentation/contracts.md` in the same commit

## Reporting Issues

Open an issue on GitHub. For context on known open work, see [`documentation/open-tasks.md`](documentation/open-tasks.md).
