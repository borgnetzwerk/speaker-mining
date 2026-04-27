from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]


_DEFAULT_CONFIG = """\
run:
  # Maximum number of live Wikidata API calls per run.
  # 0 = cache-only mode. -1 = unlimited. Any positive integer = hard cap.
  max_queries_per_run: 500

  # What to do with unlikely_relevant nodes at deferred basic_fetch time.
  # "never":      skip entirely unless rules change and promote them.
  # "end_of_run": process after all immediate work is complete.
  deferred_basic_fetch_mode: "never"

  # Maximum BFS traversal depth from any seed (0 = seeds only; 1 = seed neighbors).
  # VERY expensive to increase. Depth 3 = full neighborhood of neighborhoods.
  depth_limit: 2

  # Maximum P279 walk depth in class_hierarchy_resolution.
  # Cheap to set high — only NEW class QIDs trigger a walk; results are cached permanently.
  class_hierarchy_depth_limit: 8

wikidata:
  # Starting delay between consecutive outbound API calls (seconds).
  # The adaptive backoff system adjusts this at runtime; this is the initial value.
  query_delay_seconds: 0.25

  # Timeout per HTTP request (seconds).
  query_timeout_seconds: 30

  # Base delay for exponential HTTP retry backoff (seconds).
  http_backoff_base_seconds: 1.0

  # Maximum retry attempts per HTTP request before giving up.
  http_max_retries: 4

  # Emit a progress line after every N network calls (0 = off).
  progress_every_calls: 50

  # Emit a progress line at least once per interval during long runs (seconds; 0 = off).
  progress_every_seconds: 60.0

adaptive_backoff:
  # Runtime delay adaptation based on observed server-pressure patterns.
  # Delay increases when backoff events cluster; decreases on sustained quiet windows.
  enabled: true

  # Heartbeat windows with sustained backoff required before delay increases.
  pattern_heartbeats: 3

  # Fractional increase to delay on sustained backoff pattern (+5%).
  increase_factor: 0.05

  # Fractional decrease to delay on sustained no-backoff window (-1%).
  decrease_factor: 0.01

  # Hard floor for adaptive delay (seconds). Do not set below 0.05.
  min_delay_seconds: 0.05

  # Hard ceiling for adaptive delay (seconds).
  max_delay_seconds: 30.0

languages:
  # Labels/descriptions/aliases languages. Wikidata default language always included.
  labels: ["de", "en"]
"""


class Config:
    def __init__(self, data: dict):
        self._data = data

    def _get(self, *keys, default=None):
        node: Any = self._data
        for key in keys:
            if not isinstance(node, dict):
                return default
            node = node.get(key, default)
        return node

    @property
    def max_queries_per_run(self) -> int:
        return int(self._get("run", "max_queries_per_run", default=500))

    @property
    def deferred_basic_fetch_mode(self) -> str:
        return str(self._get("run", "deferred_basic_fetch_mode", default="never"))

    @property
    def depth_limit(self) -> int:
        return int(self._get("run", "depth_limit", default=2))

    @property
    def class_hierarchy_depth_limit(self) -> int:
        return int(self._get("run", "class_hierarchy_depth_limit", default=8))

    @property
    def query_delay_seconds(self) -> float:
        return float(self._get("wikidata", "query_delay_seconds", default=0.25))

    @property
    def query_timeout_seconds(self) -> int:
        return int(self._get("wikidata", "query_timeout_seconds", default=30))

    @property
    def http_backoff_base_seconds(self) -> float:
        return float(self._get("wikidata", "http_backoff_base_seconds", default=1.0))

    @property
    def http_max_retries(self) -> int:
        return int(self._get("wikidata", "http_max_retries", default=4))

    @property
    def progress_every_calls(self) -> int:
        return int(self._get("wikidata", "progress_every_calls", default=50))

    @property
    def progress_every_seconds(self) -> float:
        return float(self._get("wikidata", "progress_every_seconds", default=60.0))

    @property
    def adaptive_backoff_enabled(self) -> bool:
        return bool(self._get("adaptive_backoff", "enabled", default=True))

    @property
    def adaptive_backoff_pattern_heartbeats(self) -> int:
        return int(self._get("adaptive_backoff", "pattern_heartbeats", default=3))

    @property
    def adaptive_backoff_increase_factor(self) -> float:
        return float(self._get("adaptive_backoff", "increase_factor", default=0.05))

    @property
    def adaptive_backoff_decrease_factor(self) -> float:
        return float(self._get("adaptive_backoff", "decrease_factor", default=0.01))

    @property
    def adaptive_backoff_min_delay_seconds(self) -> float:
        return float(self._get("adaptive_backoff", "min_delay_seconds", default=0.05))

    @property
    def adaptive_backoff_max_delay_seconds(self) -> float:
        return float(self._get("adaptive_backoff", "max_delay_seconds", default=30.0))

    @property
    def label_languages(self) -> list[str]:
        langs = self._get("languages", "labels", default=["de", "en"])
        if isinstance(langs, list):
            return [str(l) for l in langs]
        return ["de", "en"]


def load_config(repo_root: Path) -> Config:
    """Load wikidata_config.yaml. Auto-creates defaults if absent (then raises to prompt review)."""
    repo_root = Path(repo_root)
    config_path = repo_root / "data" / "00_setup" / "wikidata_config.yaml"

    if not config_path.exists():
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(_DEFAULT_CONFIG, encoding="utf-8")
        raise FileNotFoundError(
            f"Config file did not exist — created at {config_path}\n"
            "Review the defaults and re-run."
        )

    if yaml is None:
        raise ImportError("PyYAML is required. Install with: pip install pyyaml")

    with config_path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}

    return Config(data if isinstance(data, dict) else {})
