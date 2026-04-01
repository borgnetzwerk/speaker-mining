from __future__ import annotations

from process.candidate_generation.wikidata.materializer import _alias_pipe, _pick_lang_text


def test_pick_lang_text_falls_back_to_default_language_bucket() -> None:
    mapping = {
        "mul": {"language": "mul", "value": "Bernd Saur"},
    }

    assert _pick_lang_text(mapping, "de") == "Bernd Saur"
    assert _pick_lang_text(mapping, "en") == "Bernd Saur"


def test_alias_pipe_includes_requested_and_default_aliases() -> None:
    aliases = {
        "en": [{"language": "en", "value": "B. Saur"}],
        "mul": [{"language": "mul", "value": "Bernd Saur"}],
    }

    assert _alias_pipe(aliases, "de") == "B. Saur|Bernd Saur"
    assert _alias_pipe(aliases, "en") == "B. Saur|Bernd Saur"
