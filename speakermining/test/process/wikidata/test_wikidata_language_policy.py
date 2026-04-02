from __future__ import annotations

import pytest

from process.candidate_generation.wikidata.common import (
    active_wikidata_languages_with_default,
    get_active_wikidata_languages,
    set_active_wikidata_languages,
)


def test_set_active_wikidata_languages_requires_at_least_one_language() -> None:
    with pytest.raises(ValueError, match="Please define at least one language"):
        set_active_wikidata_languages({"de": False, "en": False})


def test_active_wikidata_languages_includes_default_mul_bucket() -> None:
    previous = get_active_wikidata_languages()
    try:
        resolved = set_active_wikidata_languages({"en": True, "de": False})
        assert resolved == ("en",)
        assert active_wikidata_languages_with_default() == ("en", "mul")
    finally:
        set_active_wikidata_languages(previous)
