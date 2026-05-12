#!/usr/bin/env python3

from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent / "speakermining" / "src"))

from process.analysis.universal_stats import (
    UNKNOWN_LABEL,
    build_value_episode_matrix,
    compute_carrier_stats,
    compute_episode_appearance_stats,
    expand_property_values_to_appearances,
)
from process.analysis.occurrence_matrix import build_occurrence_matrix, build_person_catalogue


def _build_synthetic_base() -> tuple[pd.DataFrame, pd.DataFrame]:
    episode_ids = [f"E{i:02d}" for i in range(40)]
    gender_values = ["männlich", "weiblich", "divers", "nicht-binär", "unbekannt"]
    never_occurring = {90, 91, 92, 93, 94}

    appearance_rows = []
    property_rows = []

    for person_index in range(100):
        canonical_entity_id = f"ce_{person_index:03d}"
        guest_qid = f"Q{person_index:05d}" if person_index < 99 else ""
        guest_label = f"Person {person_index:03d}"

        if person_index < 99:
            property_rows.append(
                {
                    "canonical_entity_id": canonical_entity_id,
                    "guest_qid": guest_qid,
                    "guest_label": guest_label,
                    "value": gender_values[person_index % len(gender_values)],
                }
            )

        if person_index in never_occurring:
            continue

        for episode_index, episode_id in enumerate(episode_ids):
            if (person_index + episode_index) % 5 < 2:
                appearance_rows.append(
                    {
                        "canonical_entity_id": canonical_entity_id,
                        "guest_qid": guest_qid,
                        "guest_label": guest_label,
                        "episode_id": episode_id,
                    }
                )

    return pd.DataFrame(appearance_rows), pd.DataFrame(property_rows)


def test_expand_property_values_uses_episode_level_rows() -> None:
    base_appearances, property_values = _build_synthetic_base()

    expanded = expand_property_values_to_appearances(
        base_appearances,
        property_values,
        carrier_column="guest_qid",
        carrier_id_column="canonical_entity_id",
        episode_column="episode_id",
        label_column="guest_label",
        value_column="value",
    )

    assert not expanded.empty
    assert expanded["appearance_count"].eq(1).all()
    assert len(expanded) == len(base_appearances)

    stats = compute_carrier_stats(
        expanded,
        value_column="value",
        carrier_column="canonical_entity_id",
        appearance_column="appearance_count",
    )

    total_appearances = int(base_appearances.shape[0])
    assert int(stats["appearance_count"].sum()) == total_appearances

    unknown_row = stats.loc[stats["value"] == UNKNOWN_LABEL].iloc[0]
    expected_unknown_appearances = int(
        base_appearances.loc[base_appearances["guest_qid"] == "", "episode_id"].size
    )
    assert int(unknown_row["person_count"]) == 1
    assert int(unknown_row["appearance_count"]) == expected_unknown_appearances

    known = expanded[expanded["value"] != ""].copy()
    episode_matrix = known.pivot_table(
        index="value",
        columns="episode_id",
        values="appearance_count",
        aggfunc="sum",
        fill_value=0,
    )

    assert episode_matrix.shape == (5, 40)
    assert int(episode_matrix.to_numpy().sum()) == int(known.shape[0])


def test_episode_appearance_stats_match_known_value_matrix() -> None:
    base_appearances, property_values = _build_synthetic_base()

    expanded = expand_property_values_to_appearances(base_appearances, property_values)
    known = expanded[expanded["value"] != ""].copy()

    episode_stats = compute_episode_appearance_stats(
        known,
        value_column="value",
        carrier_column="canonical_entity_id",
        episode_column="episode_id",
    )

    matrix = build_value_episode_matrix(
        known,
        value_column="value",
        carrier_column="canonical_entity_id",
        episode_column="episode_id",
    )

    assert matrix.shape[0] == 5
    assert matrix.shape[1] == 41  # value + 40 episodes
    matrix_sum = int(matrix.drop(columns=["value"]).to_numpy().sum())

    assert set(episode_stats["value"]) == {"männlich", "weiblich", "divers", "nicht-binär", "unbekannt"}
    assert int(episode_stats["total_appearances"].sum()) == int(known.shape[0])
    assert int(episode_stats["total_appearances"].sum()) == matrix_sum
    assert episode_stats["min_per_episode"].ge(0).all()
    assert episode_stats["pct_without_value"].between(0, 100).all()


def test_build_person_catalogue_keeps_guest_qid_from_catalogue() -> None:
    dedup_persons = pd.DataFrame(
        [
            {
                "canonical_entity_id": "ce_001",
                "wikidata_id": "Q1",
                "canonical_label": "Person One",
                "cluster_size": "1",
                "cluster_strategy": "exact",
                "cluster_confidence": "1.0",
            }
        ]
    )

    cluster_members = pd.DataFrame(
        [
            {
                "canonical_entity_id": "ce_001",
                "alignment_unit_id": "a1",
                "canonical_label": "Person One",
                "wikidata_id": "",  # intentionally missing in cluster row
                "mention_id": "m1",
                "match_tier": "resolved",
                "fernsehserien_de_id_fernsehserien_de": "show-1",
                "guest_role_fernsehserien_de": "Gast",
                "episode_url_fernsehserien_de": "ep-1",
            }
        ]
    )

    episode_meta = pd.DataFrame(
        [
            {
                "episode_url": "ep-1",
                "premiere_date": "2024-01-01",
                "fernsehserien_de_id": "show-1",
            }
        ]
    )

    catalogue, _, _, _, episode_appearances = build_person_catalogue(
        dedup_persons=dedup_persons,
        cluster_members=cluster_members,
        episode_meta=episode_meta,
        in_scope_show_ids={"show-1"},
        core_persons={},
        qid_label={},
        moderator_qids=set(),
        repo_root=Path("."),
    )

    assert len(catalogue) == 1
    assert len(episode_appearances) == 1
    assert episode_appearances.iloc[0]["wikidata_id"] == "Q1"
    assert episode_appearances.iloc[0]["guest_qid"] == "Q1"


def test_build_occurrence_matrix_keeps_zero_guest_episodes() -> None:
    catalogue = pd.DataFrame(
        [
            {
                "canonical_entity_id": "ce_001",
                "canonical_label": "Person One",
                "role": "guest",
                "appearance_count": 1,
            }
        ]
    )

    episode_meta = pd.DataFrame(
        [
            {
                "episode_url": "ep-1",
                "premiere_date": "2024-01-01",
                "fernsehserien_de_id": "show-1",
                "program_name": "Show One",
            },
            {
                "episode_url": "ep-2",
                "premiere_date": "2024-01-02",
                "fernsehserien_de_id": "show-1",
                "program_name": "Show One",
            },
        ]
    )

    ri_with_role = pd.DataFrame(
        [
            {
                "canonical_entity_id": "ce_001",
                "fernsehserien_de_id": "show-1",
                "role": "guest",
            }
        ]
    )

    matrix_out, matrix_num = build_occurrence_matrix(
        catalogue=catalogue,
        episode_meta=episode_meta,
        in_scope_episode_urls={"ep-1", "ep-2"},
        ri_with_role=ri_with_role,
    )

    assert list(matrix_num.columns) == ["ep-1", "ep-2"]
    assert list(matrix_out.columns[-2:]) == ["ep-1", "ep-2"]
    assert int(matrix_num.loc["ce_001", "ep-2"]) == 0
    assert matrix_out.loc[matrix_out["canonical_entity_id"] == "ce_001", "ep-2"].iloc[0] == ""