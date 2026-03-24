from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, List


def _episode_marker_pattern() -> re.Pattern[str]:
    return re.compile(r"^--- EPISODE\s+\d+", flags=re.IGNORECASE)


def split_episode_text_dump(raw_text: str) -> List[str]:
    """Split a pre-exported text dump into raw episode blocks."""
    lines = raw_text.splitlines()
    marker = _episode_marker_pattern()

    episodes: list[str] = []
    current: list[str] = []
    inside = False

    for line in lines:
        if marker.match(line.strip()):
            if current:
                episodes.append("\n".join(current).strip())
            current = []
            inside = True
            continue

        if not inside:
            continue

        if line.strip() == "=" * 50:
            if current:
                episodes.append("\n".join(current).strip())
                current = []
            inside = False
            continue

        current.append(line)

    if current:
        episodes.append("\n".join(current).strip())

    return [e for e in episodes if e]


def load_episode_blocks_from_txt(path: str | Path) -> List[str]:
    """Load and split archived episode text from one .txt file."""
    p = Path(path)
    raw = p.read_text(encoding="utf-8")
    return split_episode_text_dump(raw)


def load_episode_blocks_from_many(paths: Iterable[str | Path]) -> List[str]:
    """Load episodes from many archives while preserving file order."""
    out: list[str] = []
    for path in paths:
        out.extend(load_episode_blocks_from_txt(path))
    return out


def extract_text_from_pdf(pdf_path: str | Path) -> List[str]:
    """Extract per-page text blocks from a PDF.

    Notebook use: this helper is optional in current workflow because the project
    primarily consumes pre-exported .pdf_episodes.txt files.
    """
    try:
        import pdfplumber  # type: ignore
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise ImportError(
            "pdfplumber is required for direct PDF extraction. "
            "Install it in the notebook kernel before calling this function."
        ) from exc

    pages: list[str] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            text = text.strip()
            if text:
                pages.append(text)
    return pages