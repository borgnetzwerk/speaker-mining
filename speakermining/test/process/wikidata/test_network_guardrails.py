from __future__ import annotations

# pyright: reportMissingImports=false

import pytest

from process.candidate_generation.wikidata.cache import (
    _http_get_json,
    begin_request_context,
    end_request_context,
)


class _FakeResponse:
    def __init__(self, payload: str) -> None:
        self._payload = payload.encode("utf-8")

    def read(self) -> bytes:
        return self._payload

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        _ = (exc_type, exc, tb)
        return None


def test_http_requires_explicit_request_context(monkeypatch) -> None:
    def _fake_urlopen(*args, **kwargs):
        _ = (args, kwargs)
        return _FakeResponse('{"ok": true}')

    monkeypatch.setattr("process.candidate_generation.wikidata.cache.urlopen", _fake_urlopen)

    with pytest.raises(RuntimeError, match="guard rails not initialized"):
        _http_get_json("https://example.invalid/json")


def test_http_respects_budget_limit(monkeypatch) -> None:
    def _fake_urlopen(*args, **kwargs):
        _ = (args, kwargs)
        return _FakeResponse('{"ok": true}')

    monkeypatch.setattr("process.candidate_generation.wikidata.cache.urlopen", _fake_urlopen)

    begin_request_context(
        budget_remaining=1,
        query_delay_seconds=0.0,
        progress_every_calls=0,
        context_label="test",
    )
    try:
        first = _http_get_json("https://example.invalid/json")
        assert first.get("ok") is True

        with pytest.raises(RuntimeError, match="Network query budget hit"):
            _http_get_json("https://example.invalid/json")
    finally:
        assert end_request_context() == 1


def test_http_prints_progress_every_n_calls(monkeypatch, capsys) -> None:
    def _fake_urlopen(*args, **kwargs):
        _ = (args, kwargs)
        return _FakeResponse('{"ok": true}')

    monkeypatch.setattr("process.candidate_generation.wikidata.cache.urlopen", _fake_urlopen)

    begin_request_context(
        budget_remaining=3,
        query_delay_seconds=0.0,
        progress_every_calls=2,
        context_label="progress_test",
    )
    try:
        _http_get_json("https://example.invalid/json")
        _http_get_json("https://example.invalid/json")
        _http_get_json("https://example.invalid/json")
    finally:
        used = end_request_context()

    out = capsys.readouterr().out
    assert used == 3
    assert "[progress_test] Network calls used: 2 / 3" in out


def test_http_retries_timeout_then_succeeds(monkeypatch) -> None:
    attempts = {"count": 0}

    def _fake_urlopen(*args, **kwargs):
        _ = (args, kwargs)
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise TimeoutError("The read operation timed out")
        return _FakeResponse('{"ok": true}')

    monkeypatch.setattr("process.candidate_generation.wikidata.cache.urlopen", _fake_urlopen)

    begin_request_context(
        budget_remaining=5,
        query_delay_seconds=0.0,
        progress_every_calls=0,
        context_label="timeout_retry_test",
    )
    try:
        payload = _http_get_json(
            "https://example.invalid/json",
            max_retries=1,
            backoff_base_seconds=0.0,
        )
        assert payload.get("ok") is True
    finally:
        used = end_request_context()

    assert attempts["count"] == 2
    assert used == 2


def test_http_raises_timeout_after_retry_budget(monkeypatch) -> None:
    def _fake_urlopen(*args, **kwargs):
        _ = (args, kwargs)
        raise TimeoutError("The read operation timed out")

    monkeypatch.setattr("process.candidate_generation.wikidata.cache.urlopen", _fake_urlopen)

    begin_request_context(
        budget_remaining=5,
        query_delay_seconds=0.0,
        progress_every_calls=0,
        context_label="timeout_budget_test",
    )
    try:
        with pytest.raises(TimeoutError, match="timed out"):
            _http_get_json(
                "https://example.invalid/json",
                max_retries=1,
                backoff_base_seconds=0.0,
            )
    finally:
        used = end_request_context()

    assert used == 2


def test_http_uses_request_context_retry_defaults(monkeypatch) -> None:
    attempts = {"count": 0}

    def _fake_urlopen(*args, **kwargs):
        _ = (args, kwargs)
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise TimeoutError("The read operation timed out")
        return _FakeResponse('{"ok": true}')

    monkeypatch.setattr("process.candidate_generation.wikidata.cache.urlopen", _fake_urlopen)

    begin_request_context(
        budget_remaining=5,
        query_delay_seconds=0.0,
        http_max_retries=1,
        http_backoff_base_seconds=0.0,
        progress_every_calls=0,
        context_label="timeout_context_defaults",
    )
    try:
        payload = _http_get_json("https://example.invalid/json")
    finally:
        used = end_request_context()

    assert payload.get("ok") is True
    assert attempts["count"] == 2
    assert used == 2
