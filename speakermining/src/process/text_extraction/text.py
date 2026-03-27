from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, List


def _episode_marker_pattern() -> re.Pattern[str]:
    return re.compile(r"^--- EPISODE\s+\d+", flags=re.IGNORECASE)


def _pdf_page_counter_pattern() -> re.Pattern[str]:
    return re.compile(r"Seite\s+(\d+)\s+von\s+(\d+)", flags=re.IGNORECASE)


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


def assemble_episode_blocks_from_pdf(pdf_path: str | Path) -> List[str]:
    """Assemble full episode blocks from one PDF using page counters.

    This is an optional fallback for repositories that only have raw PDFs.
    The primary workflow still prefers pre-exported ``.pdf_episodes.txt`` files.
    """
    page_counter_pattern = _pdf_page_counter_pattern()
    pages = extract_text_from_pdf(pdf_path)

    episodes: list[str] = []
    current_episode_parts: list[str] = []

    for page_text in pages:
        matches = page_counter_pattern.findall(page_text)
        if not matches:
            # Keep unmatched pages only if we are already inside an episode.
            if current_episode_parts:
                current_episode_parts.append(page_text)
            continue

        current_page_num, total_pages = map(int, matches[-1])

        if current_page_num == 1:
            if current_episode_parts:
                episodes.append("\n".join(current_episode_parts).strip())
            current_episode_parts = [page_text]
        else:
            if not current_episode_parts:
                current_episode_parts = [page_text]
            else:
                current_episode_parts.append(page_text)

        if current_page_num == total_pages and current_episode_parts:
            episodes.append("\n".join(current_episode_parts).strip())
            current_episode_parts = []

    if current_episode_parts:
        episodes.append("\n".join(current_episode_parts).strip())

    return [episode for episode in episodes if episode]


def write_episode_text_dump(episode_blocks: Iterable[str], path: str | Path) -> Path:
    """Persist episode blocks in the repository's canonical text-dump format."""
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with out_path.open("w", encoding="utf-8") as handle:
        for idx, episode in enumerate(episode_blocks, start=1):
            handle.write(f"--- EPISODE {idx} ---\n\n")
            handle.write(str(episode).strip())
            handle.write("\n\n" + "=" * 50 + "\n\n")

    return out_path


def convert_pdf_to_episode_text_dump(
    pdf_path: str | Path,
    output_path: str | Path | None = None,
) -> Path:
    """Convert one archive PDF to a ``.pdf_episodes.txt`` dump file."""
    source = Path(pdf_path)
    target = Path(output_path) if output_path else source.with_name(f"{source.name}_episodes.txt")
    episode_blocks = assemble_episode_blocks_from_pdf(source)
    return write_episode_text_dump(episode_blocks, target)