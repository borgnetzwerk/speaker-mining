"""Config-file readers for the 2026-04-30 analysis redesign.

DESIGN NOTE — Claims are temporal, not properties
-------------------------------------------------
It is incorrect to say "property X is temporal" or "property X is not temporal."
Whether a statement carries temporal scope is a per-claim attribute: one person
may hold an occupation their entire life while another's claim carries a start
date (P580) and/or end date (P582).  The correct framing is:

    "Claim (subject=Q123, predicate=P102, object=Q456) is temporal
     from start=1998 to end=2005."

Code that inspects whether a *property* is temporal (rather than each individual
claim) will silently produce wrong results: it may discard valid current claims
or retain stale historical ones.  Always evaluate the P580/P582 qualifiers on
the specific statement row, not on the property as a whole.

The ``temporal_variable`` column in ``analysis_properties.csv`` and any
runtime flag set by ``normalize_analysis_properties`` are therefore
**deprecated** and must not be used to gate analysis logic.
``infer_temporal_properties_from_values`` is retained for informational
diagnostics only (it reveals which properties *have any* temporally-scoped
claims in the dataset, not that *all* claims of that property are temporal).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


SETUP_DIR = Path("data/00_setup")

ANALYSIS_PROPERTIES_PATH = SETUP_DIR / "analysis_properties.csv"
MIDLEVEL_CLASSES_PATH = SETUP_DIR / "midlevel_classes.csv"
LOOP_RESOLUTION_PATH = SETUP_DIR / "loop_resolution.csv"
PARTY_COLORS_PATH = SETUP_DIR / "party_colors.csv"

# P580 = start time, P582 = end time — used to detect temporally-scoped claims.
# Check these on individual statement rows, never on the property as a whole.
TEMPORAL_QUALIFIER_PIDS = {"P580", "P582"}


def read_csv_or_empty(path: str | Path) -> pd.DataFrame:
    """Read a CSV file and return an empty frame when the file is missing."""

    csv_path = Path(path)
    if not csv_path.exists():
        return pd.DataFrame()
    return pd.read_csv(csv_path, dtype=str).fillna("")


def load_analysis_properties(property_values_by_id: dict[str, pd.DataFrame] | None = None) -> pd.DataFrame:
    """Load the analysis property catalog and infer temporal flags at runtime."""

    properties = read_csv_or_empty(ANALYSIS_PROPERTIES_PATH)
    return normalize_analysis_properties(properties, property_values_by_id=property_values_by_id)


def load_midlevel_classes() -> pd.DataFrame:
    """Load the designated mid-level class config."""

    return read_csv_or_empty(MIDLEVEL_CLASSES_PATH)


def load_loop_resolution() -> pd.DataFrame:
    """Load the manual P279 loop resolution config."""

    return read_csv_or_empty(LOOP_RESOLUTION_PATH)


def load_party_colors() -> pd.DataFrame:
    """Load the human-specified party color config."""

    return read_csv_or_empty(PARTY_COLORS_PATH)


def infer_temporal_properties_from_values(
    property_values: pd.DataFrame,
    property_id: str | None = None,
) -> bool:
    """Infer which properties behave temporally from qualifier payloads.

    A property is treated as temporal when any extracted value carries start/end
    time qualifiers such as P580/P582. This keeps the runtime behavior driven by
    actual Wikidata payloads rather than by a pre-seeded config bit.
    """

    if property_values is None or property_values.empty:
        return False

    qualifier_columns = [column for column in ("qualifier_pids", "qualifiers") if column in property_values.columns]
    if not qualifier_columns:
        return False

    normalized_property_id = str(property_id or "").strip()
    for _, row in property_values.iterrows():
        for column in qualifier_columns:
            qualifier_blob = str(row.get(column, "") or "")
            if any(pid in qualifier_blob for pid in TEMPORAL_QUALIFIER_PIDS):
                return True
    return False


def normalize_analysis_properties(
    properties: pd.DataFrame,
    property_values_by_id: dict[str, pd.DataFrame] | None = None,
) -> pd.DataFrame:
    """Return a normalized analysis-property table.

    The ``temporal_variable`` column is preserved for informational display only
    but is NOT used to gate analysis logic.  Temporal scope must be evaluated
    claim-by-claim (via P580/P582 qualifier inspection), not property-by-property.
    See module docstring for the full design rationale.
    """

    if properties is None or properties.empty:
        return pd.DataFrame(columns=["wikidata_id", "label", "type", "enabled", "notes"])

    frame = properties.copy()
    frame["wikidata_id"] = frame.get("wikidata_id", pd.Series(dtype=str)).astype(str).str.strip()

    # Drop the deprecated temporal_variable column if present so downstream code
    # cannot accidentally rely on it.
    frame = frame.drop(columns=["temporal_variable"], errors="ignore")

    return frame


def has_temporal_claims(
    property_values: pd.DataFrame,
    property_id: str | None = None,
) -> bool:
    """Return True if any individual claim in the dataset carries P580/P582 qualifiers.

    This is an informational diagnostic — use it to *report* which properties have
    some temporal claims.  Do NOT use the result to classify the whole property as
    temporal; evaluate each claim row individually instead.
    """
    return infer_temporal_properties_from_values(property_values, property_id=property_id)
