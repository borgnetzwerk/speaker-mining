from __future__ import annotations

import pytest

from process.candidate_generation.wikidata.mention_type_config import (
    assert_mention_type_snapshot_unchanged,
    resolve_enabled_mention_types,
    snapshot_enabled_mention_types,
)


def test_resolve_enabled_mention_types_from_dict() -> None:
    resolved = resolve_enabled_mention_types({"person": True, "topic": False, "organization": 1})
    assert resolved == ["organization", "person"]


def test_resolve_enabled_mention_types_rejects_unknown_values() -> None:
    with pytest.raises(ValueError):
        resolve_enabled_mention_types({"person": True, "unknown_type": True})


def test_assert_mention_type_snapshot_unchanged_accepts_matching_snapshot() -> None:
    raw_config = {"person": True, "topic": False}
    snapshot = snapshot_enabled_mention_types(raw_config)
    assert_mention_type_snapshot_unchanged(raw_config, snapshot, context="fallback matching")


def test_assert_mention_type_snapshot_unchanged_rejects_drift() -> None:
    initial = {"person": False, "topic": False}
    snapshot = snapshot_enabled_mention_types(initial)
    drifted = {"person": True, "topic": False}

    with pytest.raises(RuntimeError):
        assert_mention_type_snapshot_unchanged(
            drifted,
            snapshot,
            context="fallback matching",
        )
