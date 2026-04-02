"""Checksum utilities for eventstore chunks."""

from __future__ import annotations

import hashlib
from pathlib import Path


def _wikidata_dir(repo_root: Path) -> Path:
    return Path(repo_root) / "data" / "20_candidate_generation" / "wikidata"


def checksums_path(repo_root: Path) -> Path:
    return _wikidata_dir(Path(repo_root)) / "eventstore_checksums.txt"


def compute_checksum(chunk_path: Path) -> str:
    """Compute SHA256 checksum for a chunk file."""
    sha = hashlib.sha256()
    with Path(chunk_path).open("rb") as f:
        for block in iter(lambda: f.read(8192), b""):
            sha.update(block)
    return sha.hexdigest()


def _load_checksum_registry(path: Path) -> dict[str, str]:
    registry: dict[str, str] = {}
    if not Path(path).exists():
        return registry
    for raw_line in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or "=" not in line:
            continue
        name, value = line.split("=", 1)
        if name and value:
            registry[name.strip()] = value.strip()
    return registry


def _write_checksum_registry(path: Path, registry: dict[str, str]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"{name}={registry[name]}" for name in sorted(registry)]
    temp = path.with_suffix(".tmp")
    temp.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    temp.replace(path)


def write_chunk_checksum(repo_root: Path, chunk_path: Path) -> str:
    """Compute and persist checksum for a closed chunk.

    Returns computed SHA256.
    """
    chunk = Path(chunk_path)
    digest = compute_checksum(chunk)
    path = checksums_path(repo_root)
    registry = _load_checksum_registry(path)
    registry[chunk.name] = digest
    _write_checksum_registry(path, registry)
    return digest


def validate_chunk_checksum(repo_root: Path, chunk_path: Path) -> bool:
    """Validate a chunk checksum against the registry.

    If chunk has no registry entry yet, returns True.
    """
    chunk = Path(chunk_path)
    registry = _load_checksum_registry(checksums_path(repo_root))
    expected = registry.get(chunk.name)
    if not expected:
        return True
    return compute_checksum(chunk) == expected
