from __future__ import annotations

from pathlib import Path

from . import V4Handler


class SeedHandler(V4Handler):
    """Maintains the set of registered seeds.

    Reacts to: seed_registered
    Writes: seeds.csv (qid, label)
    """

    def name(self) -> str:
        return "SeedHandler"

    def __init__(self, repo_root: Path, event_store=None):
        super().__init__(repo_root, event_store)
        self._seeds: dict[str, str] = {}  # qid → label

    def _on_event(self, event: dict) -> None:
        if event.get("event_type") != "seed_registered":
            return
        payload = event.get("payload", {}) or {}
        qid = str(payload.get("qid", "") or "").strip()
        label = str(payload.get("label", "") or "").strip()
        if qid:
            self._seeds.setdefault(qid, label)

    def _write(self, proj_dir: Path) -> None:
        rows = [[qid, label] for qid, label in sorted(self._seeds.items())]
        self._atomic_write_csv_rows(proj_dir / "seeds.csv", ["qid", "label"], rows)

    def seeds(self) -> dict[str, str]:
        return dict(self._seeds)
