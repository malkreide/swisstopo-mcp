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


# ---------------------------------------------------------------------------
# Strict-mode contract on the shared base (audit SEC-018)
# ---------------------------------------------------------------------------


class TestSharedBaseIsStrict:
    """The base model used to carry an empty config; only the subclasses were
    strict. This asserts the contract at the level that would have caught it."""

    def test_base_config_forbids_extra(self):
        from swisstopo_mcp.coords import SwissPointInput

        assert SwissPointInput.model_config.get("extra") == "forbid"

    def test_base_config_is_strict(self):
        from swisstopo_mcp.coords import SwissPointInput

        assert SwissPointInput.model_config.get("strict") is True


class TestSrIsConstrained:
    """`sr` was an unbounded int forwarded straight upstream, while the
    purpose-built validate_sr() sat unused (SEC-018)."""

    @pytest.mark.parametrize("bad_sr", [9999, 0, -1, 4327])
    def test_geocode_rejects_unsupported_sr(self, bad_sr):
        from swisstopo_mcp.geocoding import GeocodeInput

        with pytest.raises(ValidationError):
            GeocodeInput(search_text="Bern", sr=bad_sr)

    @pytest.mark.parametrize("good_sr", [4326, 2056, 21781, 3857])
    def test_geocode_accepts_supported_sr(self, good_sr):
        from swisstopo_mcp.geocoding import GeocodeInput

        assert GeocodeInput(search_text="Bern", sr=good_sr).sr == good_sr

    def test_get_feature_rejects_unsupported_sr(self):
        from swisstopo_mcp.rest_api import GetFeatureInput

        with pytest.raises(ValidationError):
            GetFeatureInput(layer="ch.x", feature_id="1", sr=9999)


class TestIdentifierLengthBounds:
    def test_layers_field_is_bounded(self):
        from swisstopo_mcp.rest_api import IdentifyInput

        with pytest.raises(ValidationError):
            IdentifyInput(layers="a" * 600, lat=47.0, lon=8.0)

    def test_search_field_is_bounded(self):
        from swisstopo_mcp.rest_api import FindFeaturesInput

        with pytest.raises(ValidationError):
            FindFeaturesInput(layer="ch.x", search_text="y", search_field="f" * 200)
