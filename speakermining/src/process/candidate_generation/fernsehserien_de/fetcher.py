from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from process.io_guardrails import atomic_write_text

from .config import FernsehserienRunConfig
from .event_store import FernsehserienEventStore
from .paths import FernsehserienPaths


def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha1_text(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()


def normalize_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if not parsed.scheme:
        raise ValueError(f"URL must include scheme: {url}")
    if parsed.scheme.lower() not in {"http", "https"}:
        raise ValueError(f"URL must use http/https scheme: {url}")
    if not parsed.netloc:
        raise ValueError(f"URL must include host: {url}")
    host = str(parsed.hostname or "").strip()
    if not host:
        raise ValueError(f"URL must include host: {url}")
    try:
        host.encode("idna")
    except UnicodeError as exc:
        raise ValueError(f"URL host is invalid: {url}") from exc
    # URL fragments (e.g. #Cast-Crew) are client-side anchors and must not
    # create distinct fetch/cache identities for the same page.
    return parsed._replace(fragment="").geturl()


@dataclass(frozen=True)
class FetchResult:
    url: str
    status: str
    from_cache: bool
    cache_path: Path | None
    content: str
    fetched_at_utc: str
    http_status: int | None


class FernsehserienFetcher:
    """Cache-first fetcher with explicit per-run network budget."""

    def __init__(
        self,
        *,
        config: FernsehserienRunConfig,
        paths: FernsehserienPaths,
        event_store: FernsehserienEventStore,
    ) -> None:
        self.config = config
        self.paths = paths
        self.event_store = event_store
        self._network_calls_used = 0
        self._last_call_monotonic: float | None = None

    @property
    def network_calls_used(self) -> int:
        return self._network_calls_used

    def _cache_path_for_url(self, url: str) -> Path:
        key = hashlib.md5(url.encode("utf-8")).hexdigest()
        return self.paths.cache_pages_dir / f"{key}.html"

    def _sleep_if_needed(self) -> None:
        if self._last_call_monotonic is None:
            return
        elapsed = time.monotonic() - self._last_call_monotonic
        remaining = float(self.config.query_delay_seconds) - elapsed
        if remaining > 0:
            time.sleep(remaining)

    def _is_budget_exhausted(self) -> bool:
        if int(self.config.max_network_calls) < 0:
            return False
        return self._network_calls_used >= int(self.config.max_network_calls)

    def fetch_url(self, *, url: str, phase: str, request_kind: str = "html_page") -> FetchResult:
        try:
            normalized_url = normalize_url(url)
        except Exception as exc:
            reason = f"{type(exc).__name__}: {exc}"
            event = self.event_store.append(
                event_type="network_request_invalid_url",
                payload={
                    "url": str(url),
                    "request_kind": request_kind,
                    "reason": reason,
                    "fetched_at_utc": _iso_now(),
                },
            )
            return FetchResult(
                url=str(url),
                status="invalid_url",
                from_cache=False,
                cache_path=None,
                content="",
                fetched_at_utc=_iso_now(),
                http_status=None,
            )

        cache_path = self._cache_path_for_url(normalized_url)

        if cache_path.exists():
            content = cache_path.read_text(encoding="utf-8", errors="replace")
            event = self.event_store.append(
                event_type="network_request_skipped_cache_hit",
                payload={
                    "url": normalized_url,
                    "cache_path": str(cache_path),
                    "fetched_at_utc": _iso_now(),
                    "request_kind": request_kind,
                },
            )
            return FetchResult(
                url=normalized_url,
                status="cache_hit",
                from_cache=True,
                cache_path=cache_path,
                content=content,
                fetched_at_utc=_iso_now(),
                http_status=200,
            )

        if (not self.config.allow_network) or self._is_budget_exhausted():
            return FetchResult(
                url=normalized_url,
                status="budget_blocked",
                from_cache=False,
                cache_path=None,
                content="",
                fetched_at_utc=_iso_now(),
                http_status=None,
            )

        self._sleep_if_needed()
        started_at = time.monotonic()
        request = Request(
            normalized_url,
            headers={
                "User-Agent": self.config.user_agent,
                "Accept": "text/html,application/xhtml+xml",
            },
        )
        try:
            with urlopen(request, timeout=20) as response:
                body = response.read().decode("utf-8", errors="replace")
                http_status = int(getattr(response, "status", 200))
        except Exception as exc:
            reason = f"{type(exc).__name__}: {exc}"
            event = self.event_store.append(
                event_type="network_request_failed",
                payload={
                    "url": normalized_url,
                    "request_kind": request_kind,
                    "reason": reason,
                    "fetched_at_utc": _iso_now(),
                    "network_call_index": self._network_calls_used + 1,
                },
            )
            return FetchResult(
                url=normalized_url,
                status="error",
                from_cache=False,
                cache_path=None,
                content="",
                fetched_at_utc=_iso_now(),
                http_status=None,
            )

        atomic_write_text(cache_path, body, encoding="utf-8")
        self._last_call_monotonic = time.monotonic()
        self._network_calls_used += 1
        duration_ms = int((time.monotonic() - started_at) * 1000)
        content_sha1 = _sha1_text(body)

        event = self.event_store.append(
            event_type="network_request_performed",
            payload={
                "url": normalized_url,
                "request_kind": request_kind,
                "cache_path": str(cache_path),
                "http_status": http_status,
                "duration_ms": duration_ms,
                "content_sha1": content_sha1,
                "fetched_at_utc": _iso_now(),
                "network_call_index": self._network_calls_used,
            },
        )

        return FetchResult(
            url=normalized_url,
            status="success",
            from_cache=False,
            cache_path=cache_path,
            content=body,
            fetched_at_utc=_iso_now(),
            http_status=http_status,
        )
