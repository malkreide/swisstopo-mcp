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


# ---------------------------------------------------------------------------
# Every string field is length-bounded (audit SEC-018)
#
# Three fields shipped without a `max_length` — `collection_id`, `origins` and
# `layers` — and the remediation note claimed length bounds had been added
# across the board. A pattern constrains the charset, not the size, so a
# multi-kilobyte value of legal characters passed validation and was forwarded
# upstream; `collection_id` lands in a URL *path*.
#
# Rather than assert the three, this walks every field of every registered input
# model. A new unbounded string field fails the build.
# ---------------------------------------------------------------------------


def _input_models():
    """Every Pydantic model reachable as a tool parameter."""
    import inspect

    from pydantic import BaseModel

    from swisstopo_mcp import (
        coords,
        geocoding,
        geodata,
        height,
        oereb,
        openplz,
        overpass,
        rest_api,
        stac,
        wmts,
    )

    seen: dict[str, type[BaseModel]] = {}
    for module in (
        coords, geocoding, geodata, height, oereb, openplz, overpass,
        rest_api, stac, wmts,
    ):
        for name, obj in inspect.getmembers(module, inspect.isclass):
            if (
                issubclass(obj, BaseModel)
                and obj is not BaseModel
                and obj.__module__.startswith("swisstopo_mcp")
                and name.endswith("Input")
            ):
                seen[f"{obj.__module__}.{name}"] = obj
    return seen


def _string_fields():
    import typing

    for qualname, model in sorted(_input_models().items()):
        for field_name, field in model.model_fields.items():
            annotation = field.annotation
            args = typing.get_args(annotation) or (annotation,)
            if str in args:
                yield qualname, field_name, field


class TestEveryStringFieldIsBounded:
    # Fields bounded by an anchored fixed-width pattern rather than by
    # max_length. Each entry names the pattern, so the exemption is a stated
    # reason rather than a way to silence the check.
    EXEMPT = {
        "lang",          # ^[a-z]{2}$
        "canton",        # ^[A-Za-z]{2}$ / ^([A-Za-z]{2}|\d{1,2})$
        "source",        # ^(swisstopo|geodienste|oereb)$
        "postal_code",   # ^\d{4}$
        "district",      # ^\d{1,4}$
    }

    def test_the_sweep_finds_the_models(self):
        """A sweep that matches nothing passes vacuously."""
        models = _input_models()
        assert len(models) >= 20, f"only found {len(models)} input models"
        assert len(list(_string_fields())) >= 15

    def test_no_unbounded_string_field(self):
        unbounded = []
        for qualname, field_name, field in _string_fields():
            if field_name in self.EXEMPT:
                continue
            has_max = any(
                getattr(meta, "max_length", None) is not None for meta in field.metadata
            )
            if not has_max:
                unbounded.append(f"{qualname}.{field_name}")

        assert not unbounded, (
            "string fields with no max_length: "
            + ", ".join(unbounded)
            + ". A pattern constrains the charset, not the size — add a bound or "
            "list the field in EXEMPT with a reason."
        )

    def test_exemptions_are_actually_bounded(self):
        """An exemption is only valid if the pattern really caps the length.
        Without this the EXEMPT set becomes a way to silence the check."""
        import re

        for qualname, field_name, field in _string_fields():
            if field_name not in self.EXEMPT:
                continue
            patterns = [
                getattr(meta, "pattern", None)
                for meta in field.metadata
                if getattr(meta, "pattern", None)
            ]
            assert patterns, f"{qualname}.{field_name} is exempt but has no pattern"
            pattern = patterns[0]
            assert pattern.startswith("^") and pattern.endswith("$"), (
                f"{qualname}.{field_name} pattern is not anchored, so it does "
                "not bound the length"
            )
            # An unbounded quantifier defeats the whole exemption.
            assert not re.search(r"[+*]", pattern), (
                f"{qualname}.{field_name} pattern {pattern!r} has an unbounded "
                "quantifier — add max_length instead"
            )


class TestOriginsIsAnActualEnum:
    """The description promised seven values; the pattern accepted any
    lowercase-alphanumeric-comma string (SEC-018)."""

    def test_known_values_accepted(self):
        assert GeocodeInput(search_text="Bern", origins="address").origins == "address"
        assert GeocodeInput(search_text="Bern", origins="address,zipcode").origins

    def test_unknown_value_rejected(self):
        with pytest.raises(ValidationError, match="Unbekannte origins"):
            GeocodeInput(search_text="Bern", origins="notathing")

    def test_unknown_value_in_a_list_rejected(self):
        with pytest.raises(ValidationError, match="notathing"):
            GeocodeInput(search_text="Bern", origins="address,notathing")

    def test_error_names_the_allowed_set(self):
        with pytest.raises(ValidationError, match="gazetteer"):
            GeocodeInput(search_text="Bern", origins="zzz")


class TestOversizedValuesRejected:
    def test_collection_id_length_capped(self):
        from swisstopo_mcp.stac import GetCollectionInput

        with pytest.raises(ValidationError):
            GetCollectionInput(collection_id="ch." + "a" * 200)

    def test_layers_length_capped(self):
        from swisstopo_mcp.wmts import MapUrlInput

        with pytest.raises(ValidationError):
            MapUrlInput(lat=47.0, lon=8.0, layers="ch.a," * 200)

    def test_origins_length_capped(self):
        with pytest.raises(ValidationError):
            GeocodeInput(search_text="Bern", origins="address," * 100)
