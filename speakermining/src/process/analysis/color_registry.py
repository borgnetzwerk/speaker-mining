"""Deterministic QID-to-color assignment for analysis visualizations."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from .config import load_party_colors


UNKNOWN_COLOR = "#999999"
OTHER_COLOR = "#CCCCCC"

PALETTE = [
    "#E69F00",
    "#56B4E9",
    "#009E73",
    "#F0E442",
    "#0072B2",
    "#D55E00",
    "#CC79A7",
    "#000000",
    "#44AA99",
    "#88CCEE",
    "#DDCC77",
    "#AA4499",
]


def _normalize_qid(value: str | object) -> str:
    text = "" if value is None else str(value).strip()
    return text


def _normalize_hex(value: str | object) -> str:
    return _normalize_qid(value).upper()


@dataclass
class ColorRegistry:
    """Immutable lookup table for QID colors."""

    _colors: dict[str, str] = field(default_factory=dict)

    def get_color(self, qid: str) -> str:
        """Return the color registered for a QID."""

        normalized = _normalize_qid(qid)
        if normalized not in self._colors:
            raise KeyError(f"QID not registered: {normalized}")
        return self._colors[normalized]

    def get_unknown_color(self) -> str:
        """Color used for missing or unknown values."""

        return UNKNOWN_COLOR

    def get_other_color(self) -> str:
        """Color used for aggregated 'Other' buckets."""

        return OTHER_COLOR

    @classmethod
    def build(cls, guest_facts: pd.DataFrame, party_colors_path: str | Path) -> "ColorRegistry":
        """Build a deterministic registry from guest facts and party seeds."""

        colors: dict[str, str] = {}

        party_colors = load_party_colors()
        if party_colors.empty and Path(party_colors_path).exists():
            party_colors = pd.read_csv(Path(party_colors_path), dtype=str).fillna("")

        if not party_colors.empty:
            for _, row in party_colors.iterrows():
                qid = _normalize_qid(row.get("wikidata_id", ""))
                color = _normalize_hex(row.get("hex_color", ""))
                if qid and color:
                    colors[qid] = color

        if guest_facts is None or guest_facts.empty or "guest_qid" not in guest_facts.columns:
            return cls(colors)

        qids = (
            guest_facts["guest_qid"]
            .astype(str)
            .map(_normalize_qid)
        )
        qids = qids[qids != ""]
        if qids.empty:
            return cls(colors)

        counts = qids.value_counts().to_dict()
        ordered_qids = sorted(counts.items(), key=lambda item: (-item[1], item[0]))

        reserved_hex = {_normalize_hex(value) for value in colors.values()}
        available_palette = [
            color for color in PALETTE
            if _normalize_hex(color) not in reserved_hex
            and _normalize_hex(color) not in {_normalize_hex(UNKNOWN_COLOR), _normalize_hex(OTHER_COLOR)}
        ]
        if not available_palette:
            available_palette = [
                color for color in PALETTE
                if _normalize_hex(color) not in {_normalize_hex(UNKNOWN_COLOR), _normalize_hex(OTHER_COLOR)}
            ]

        palette_index = 0
        for qid, _count in ordered_qids:
            if qid in colors:
                continue
            colors[qid] = available_palette[palette_index % len(available_palette)]
            palette_index += 1

        return cls(colors)
