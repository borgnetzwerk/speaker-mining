# T03: Investigate and Add pyproject.toml

**Decision:** D-09 — investigate later as dedicated process.

## Problem

Notebooks currently add `speakermining/src` to `sys.path` manually in each notebook's setup cell. This means:
- No `pip install -e .` workflow is possible
- Import paths depend on where the notebook is launched from
- There is no machine-readable list of the package structure

## Investigation questions

Before implementing, answer these:

1. **What is the package root?** Is it `speakermining/src/` (so `from process.analysis import ...`) or should it be `speakermining/` (so `from src.process.analysis import ...`)? Current notebooks use `process.*` imports.

2. **Is there already an `__init__.py` at `speakermining/src/`?** Check — if not, the current import convention requires `sys.path.insert(0, str(root / "speakermining/src"))`.

3. **Do any notebooks or tests break if the package is installed?** An editable install might conflict with the manual sys.path approach. Need to test.

4. **What Python version is targeted?** Check `.python-version` or the pixi config.

## Implementation options

### Option A: Full pyproject.toml with editable install

```toml
[project]
name = "speakermining"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
    # from requirements.txt
]

[build-system]
requires = ["setuptools>=61"]
build-backend = "setuptools.backends.legacy:build"

[tool.setuptools.packages.find]
where = ["speakermining/src"]
```

Then: `pip install -e .` replaces all `sys.path` manipulation.

### Option B: Minimal setup for notebooks only

Add only enough so notebooks can import without path manipulation, but don't publish the package.

### Option C: Document the manual approach clearly (no structural change)

Add a notebook bootstrap snippet to `coding-principles.md` as the canonical pattern.

## Acceptance criteria

- Developers can run `pip install -e .` (or equivalent) and notebooks import without sys.path hacks
- OR: the manual approach is documented clearly enough that it's not confusing

## Notes

- `requirements.txt` exists at root — the pyproject.toml `[project.dependencies]` should mirror it
- Avoid breaking the existing test runner (`pytest speakermining/test/`)
- Check if pixi already handles this (`pixi.toml` or `pixi.lock` at root?)
