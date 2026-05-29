# tests/test_input_validation.py
"""Regression tests for SEC-018: strict input validation + whitelist patterns."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from swisstopo_mcp.geocoding import GeocodeInput
from swisstopo_mcp.oereb import GetOerebExtractInput
from swisstopo_mcp.rest_api import FindFeaturesInput, GetFeatureInput


class TestWhitelistPatterns:
    @pytest.mark.parametrize(
        "bad",
        [
            "test\x00null",   # control char
            "<script>alert</script>",  # angle brackets
            'a"b',            # double quote
            "a`b",            # backtick
        ],
    )
    def test_search_text_rejects_dangerous(self, bad):
        with pytest.raises(ValidationError):
            GeocodeInput(search_text=bad)

    def test_search_text_accepts_real_address(self):
        m = GeocodeInput(search_text="Bahnhofstrasse 1, Zürich")
        assert m.search_text == "Bahnhofstrasse 1, Zürich"

    def test_feature_id_rejects_path_traversal(self):
        with pytest.raises(ValidationError):
            GetFeatureInput(layer="ch.test", feature_id="../../etc/passwd")

    def test_egrid_rejects_non_alphanumeric(self):
        with pytest.raises(ValidationError):
            GetOerebExtractInput(egrid="CH-7679/824", canton="ZH")

    def test_topics_rejects_spaces_and_specials(self):
        with pytest.raises(ValidationError):
            GetOerebExtractInput(egrid="CH767982496078", canton="ZH", topics="a b;c")


class TestStrictMode:
    def test_int_coords_still_accepted(self):
        # strict mode still accepts int for a float field (47 -> 47.0)
        m = GeocodeInput(search_text="Bern")
        assert m.limit == 10
        from swisstopo_mcp.height import HeightInput

        h = HeightInput(lat=47, lon=8)  # ints
        assert h.lat == 47.0 and h.lon == 8.0

    def test_string_not_coerced_to_int(self):
        # strict mode rejects "10" where an int is expected
        with pytest.raises(ValidationError):
            GeocodeInput(search_text="Bern", limit="10")

    def test_extra_fields_still_forbidden(self):
        with pytest.raises(ValidationError):
            FindFeaturesInput(layer="ch.test", search_text="x", search_field="id", foo="bar")
