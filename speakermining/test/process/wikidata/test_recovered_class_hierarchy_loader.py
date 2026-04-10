from __future__ import annotations

from pathlib import Path

from process.candidate_generation.wikidata.class_resolver import load_recovered_class_hierarchy


def test_load_recovered_class_hierarchy_normalizes_qids_and_paths(tmp_path: Path) -> None:
    source = tmp_path / "class_hierarchy.csv"
    source.write_text(
        "class_id,path_to_core_class,subclass_of_core_class,parent_qids\n"
        "q5,q5| q215627 |bad,true,q215627|q35120\n"
        "Q123,,false,Q456|bad\n",
        encoding="utf-8",
    )

    evidence = load_recovered_class_hierarchy(source)

    assert evidence.class_to_path["Q5"] == "Q5|Q215627"
    assert evidence.class_to_subclass_of_core["Q5"] is True
    assert evidence.class_to_parent_qids["Q5"] == ("Q215627", "Q35120")

    assert evidence.class_to_path["Q123"] == ""
    assert evidence.class_to_subclass_of_core["Q123"] is False
    assert evidence.class_to_parent_qids["Q123"] == ("Q456",)

    assert evidence.diagnostics["total_rows"] == 2
    assert evidence.diagnostics["loaded_rows"] == 2


def test_load_recovered_class_hierarchy_tracks_skips_and_malformed_rows(tmp_path: Path) -> None:
    source = tmp_path / "class_hierarchy.csv"
    source.write_text(
        "class_id,path_to_core_class,subclass_of_core_class,parent_qids\n"
        ",Q5|Q215627,true,Q5\n"
        "Q999,bad,false,bad\n"
        "Q100,,,\n",
        encoding="utf-8",
    )

    evidence = load_recovered_class_hierarchy(source)

    assert "Q999" not in evidence.class_to_path
    assert "Q100" not in evidence.class_to_path
    assert evidence.diagnostics["skipped_missing_class_id"] == 1
    assert evidence.diagnostics["malformed_path_rows"] == 1
    assert evidence.diagnostics["malformed_parent_rows"] == 1
    assert evidence.diagnostics["skipped_no_lineage_signal"] == 2
    assert evidence.diagnostics["loaded_rows"] == 0


def test_load_recovered_class_hierarchy_is_deterministic(tmp_path: Path) -> None:
    source = tmp_path / "class_hierarchy.csv"
    source.write_text(
        "class_id,path_to_core_class,subclass_of_core_class,parent_qids\n"
        "Q5,Q5|Q215627,true,Q215627\n",
        encoding="utf-8",
    )

    a = load_recovered_class_hierarchy(source)
    b = load_recovered_class_hierarchy(source)

    assert a == b
