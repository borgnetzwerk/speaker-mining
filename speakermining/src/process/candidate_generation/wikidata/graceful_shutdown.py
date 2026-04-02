"""Graceful shutdown primitives for v3 pipeline operations."""

from __future__ import annotations

import signal
from pathlib import Path


terminate_requested = False


def request_termination() -> None:
    """Set the global termination flag."""
    global terminate_requested
    terminate_requested = True


def reset_termination_flag() -> None:
    """Reset termination flag (useful for tests)."""
    global terminate_requested
    terminate_requested = False


def check_shutdown_file(shutdown_path: Path) -> bool:
    """Return True when a non-empty shutdown file exists."""
    path = Path(shutdown_path)
    if not path.exists():
        return False
    try:
        return bool(path.read_text(encoding="utf-8").strip())
    except Exception:
        return False


def should_terminate(shutdown_path: Path | None = None) -> bool:
    """Return whether processing should stop."""
    if terminate_requested:
        return True
    if shutdown_path is not None and check_shutdown_file(Path(shutdown_path)):
        return True
    return False


def install_shutdown_handlers() -> None:
    """Install SIGINT/SIGTERM handlers that set the terminate flag."""

    def _handler(signum, frame):
        _ = (signum, frame)
        request_termination()

    signal.signal(signal.SIGINT, _handler)
    signal.signal(signal.SIGTERM, _handler)
