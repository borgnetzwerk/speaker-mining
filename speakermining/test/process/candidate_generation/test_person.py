from __future__ import annotations

# pyright: reportMissingImports=false

import pytest
from process.candidate_generation.person import clean_mixed_uppercase_name, normalize_name_for_matching


class TestCleanMixedUppercaseName:
    def test_all_caps_surname(self) -> None:
        assert clean_mixed_uppercase_name("Elmar ALEXANDER") == "Elmar Alexander"

    def test_eszett_surname_preserved(self) -> None:
        # ß stays; only the uppercase tail is lowercased
        assert clean_mixed_uppercase_name("Elmar THEVEßEN") == "Elmar Theveßen"

    def test_nan_returns_empty(self) -> None:
        import pandas as pd
        assert clean_mixed_uppercase_name(pd.NA) == ""

    def test_empty_string(self) -> None:
        assert clean_mixed_uppercase_name("") == ""


class TestNormalizeNameForMatching:
    def test_eszett_matches_ss(self) -> None:
        assert normalize_name_for_matching("THEVEßEN") == normalize_name_for_matching("THEVESSEN")

    def test_eszett_mixed_case(self) -> None:
        assert normalize_name_for_matching("Elmar THEVEßEN") == normalize_name_for_matching("Elmar Thevessen")

    def test_umlaut_o(self) -> None:
        result = normalize_name_for_matching("GRÖßER")
        assert "oe" in result
        assert "ss" in result
        assert result == result.lower()

    def test_grosser_no_umlauts(self) -> None:
        assert normalize_name_for_matching("GROSSER") == "grosser"

    def test_all_umlauts(self) -> None:
        assert normalize_name_for_matching("Müller") == "mueller"
        assert normalize_name_for_matching("Köhler") == "koehler"
        assert normalize_name_for_matching("Bäcker") == "baecker"

    def test_result_is_lowercase(self) -> None:
        result = normalize_name_for_matching("Hans MÜLLER")
        assert result == result.lower()

    def test_nan_returns_empty(self) -> None:
        import pandas as pd
        assert normalize_name_for_matching(pd.NA) == ""

    def test_empty_string(self) -> None:
        assert normalize_name_for_matching("") == ""
