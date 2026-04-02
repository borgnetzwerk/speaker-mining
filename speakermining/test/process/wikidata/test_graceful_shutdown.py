from __future__ import annotations

# pyright: reportMissingImports=false

from pathlib import Path

from process.candidate_generation.wikidata.graceful_shutdown import (
    check_shutdown_file,
    request_termination,
    reset_termination_flag,
    should_terminate,
)


def test_shutdown_file_detection(tmp_path: Path) -> None:
    path = tmp_path / ".shutdown"
    assert check_shutdown_file(path) is False
    path.write_text("stop", encoding="utf-8")
    assert check_shutdown_file(path) is True


def test_global_termination_flag() -> None:
    reset_termination_flag()
    assert should_terminate() is False
    request_termination()
    assert should_terminate() is True
    reset_termination_flag()


def test_should_terminate_when_shutdown_file_present(tmp_path: Path) -> None:
    reset_termination_flag()
    path = tmp_path / ".shutdown"
    path.write_text("1", encoding="utf-8")
    assert should_terminate(path) is True
