from __future__ import annotations

from pathlib import Path
import sys


def find_repo_root(start: Path) -> Path:
    """Resolve repository root from a starting path.

    Expects a repo layout containing both top-level data/ and speakermining/src/.
    """
    cur = start.resolve()
    for _ in range(8):
        if (cur / "data").exists() and (cur / "speakermining" / "src").exists():
            return cur
        if cur.parent == cur:
            break
        cur = cur.parent
    raise RuntimeError("Repository root not found.")


def bootstrap_notebook_paths(start: Path | None = None) -> tuple[Path, Path]:
    """Return (ROOT, SRC) and ensure SRC is importable for notebooks."""
    root = find_repo_root(start or Path.cwd())
    src = root / "speakermining" / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
    return root, src
