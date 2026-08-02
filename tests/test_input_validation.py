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


# ---------------------------------------------------------------------------
# Aggregate / delegate constraint agreement
#
# Two tools collapse a multi-step chain and re-validate the caller's values by
# constructing the underlying tool's input model: `swisstopo_oereb_at` builds a
# `GetOerebExtractInput`, and `swisstopo_map_query` builds one of five REST
# inputs. That means every passed-through field is validated twice, against two
# separately written Field() definitions.
#
# When they disagree the failure is silent in one direction and ugly in the
# other. Stricter aggregate: input the underlying tool accepts is rejected at
# the door, which is what happened to `topics` — the charset was fixed on
# `GetOerebExtractInput` and left broken on `OerebAtInput`, so the one-call
# tool could not name a theme while the two-call chain could. Looser aggregate:
# the value passes the outer model and blows up as an unexpected
# ValidationError inside the handler, surfacing as an internal error.
#
# Descriptions are deliberately *not* compared — an aggregate annotates which
# operation a field belongs to ("nur features_at_point"), and that divergence
# is the point of it.
# ---------------------------------------------------------------------------


def _delegation_pairs():
    from swisstopo_mcp.oereb import GetEgridInput, GetOerebExtractInput, OerebAtInput
    from swisstopo_mcp.rest_api import (
        FindFeaturesInput,
        GetFeatureInput,
        IdentifyInput,
        LayerInfoInput,
        MapQueryInput,
        SearchLayersInput,
    )

    return [
        # oereb.py: oereb_at() -> get_oereb_extract(), and the EGRID lookup it
        # resolves the coordinate with first.
        (OerebAtInput, GetOerebExtractInput),
        (OerebAtInput, GetEgridInput),
        # rest_api.py: map_query() dispatches to one of five.
        (MapQueryInput, SearchLayersInput),
        (MapQueryInput, LayerInfoInput),
        (MapQueryInput, IdentifyInput),
        (MapQueryInput, FindFeaturesInput),
        (MapQueryInput, GetFeatureInput),
    ]


def _shared_fields():
    for aggregate, delegate in _delegation_pairs():
        for field in sorted(set(aggregate.model_fields) & set(delegate.model_fields)):
            yield pytest.param(
                aggregate,
                delegate,
                field,
                id=f"{aggregate.__name__}->{delegate.__name__}.{field}",
            )


class TestAggregatesValidateLikeTheirDelegates:
    @pytest.mark.parametrize("aggregate,delegate,field", list(_shared_fields()))
    def test_constraints_agree(self, aggregate, delegate, field):
        def constraints(model):
            return sorted(str(m) for m in model.model_fields[field].metadata)

        assert constraints(aggregate) == constraints(delegate), (
            f"{aggregate.__name__}.{field} and {delegate.__name__}.{field} "
            "validate differently, but the first is handed straight to the "
            "second. Whichever is right, both must say it."
        )

    def test_the_pairs_cover_every_field_that_is_passed_through(self):
        """Guards the guard: a new field on an aggregate that its delegate also
        has must land in the parametrisation above, not sit outside it."""
        covered = {p.values[2] for p in _shared_fields()}
        assert {"canton", "lang", "topics"} <= covered, (
            "the ÖREB pass-through fields dropped out of the check"
        )
        assert {"layer", "lat", "lon", "limit"} <= covered, (
            "the map_query pass-through fields dropped out of the check"
        )


# ---------------------------------------------------------------------------
# Patterns vs. real values
#
# The `topics` charset rejected every valid ÖREB theme code because it was
# written from imagination rather than from an example. These pin the three
# other places the same audit found, each with a value taken from a live
# response rather than invented — an invented value is what let the bug in.
#
# The audit that produced them checked every patterned field against real data:
# 2115 commune names, 1325 street names, 993 localities and 134 district names
# against TEXT_PATTERN; 896 layer IDs, 100 STAC collection IDs and 109 attribute
# names against ID_PATTERN; 970 BFS keys and 176 postal codes against their
# numeric patterns. Those all passed. What follows is what did not.
# ---------------------------------------------------------------------------


class TestIdentifiersTheServerItselfEmits:
    """`ch.bav.haltestellen-oev` answers with SLOIDs. 201 of the 761 real
    feature IDs sampled across six layers carry colons, and the identifier
    charset had none — so `feature_by_id` rejected IDs `features_at_point` had
    just produced, before any request went out."""

    # Verbatim from a live features_at_point response.
    SLOID = "ch:1:sloid:91220::83"

    def test_get_feature_accepts_a_sloid(self):
        from swisstopo_mcp.rest_api import GetFeatureInput

        m = GetFeatureInput(layer="ch.bav.haltestellen-oev", feature_id=self.SLOID)
        assert m.feature_id == self.SLOID

    def test_map_query_accepts_a_sloid(self):
        from swisstopo_mcp.rest_api import MapQueryInput

        m = MapQueryInput(
            operation="feature_by_id",
            layer="ch.bav.haltestellen-oev",
            feature_id=self.SLOID,
        )
        assert m.feature_id == self.SLOID

    def test_plain_numeric_ids_still_work(self):
        """The other real shape — most layers use integers."""
        from swisstopo_mcp.rest_api import GetFeatureInput

        assert GetFeatureInput(layer="ch.are.bauzonen", feature_id="10003995")


class TestSeparatorSpacingIsAccepted:
    """A space after a comma is how anyone writes a list or a coordinate pair,
    and the code behind each of these fields already coped with it — `float()`
    strips, `bbox` strips each part explicitly. Only the patterns did not."""

    def test_point_accepts_a_space_after_the_comma(self):
        from swisstopo_mcp.geodata import QueryGeodataInput

        assert QueryGeodataInput(layer="strassenverzeichnis", point="47.360966, 8.525343")

    def test_point_still_rejects_a_non_pair(self):
        from swisstopo_mcp.geodata import QueryGeodataInput

        with pytest.raises(ValidationError):
            QueryGeodataInput(layer="strassenverzeichnis", point="47.360966")

    def test_origins_accepts_and_normalises_spacing(self):
        m = GeocodeInput(search_text="Bern", origins="address, gazetteer")
        # Normalised on the way in, so the value handed upstream is the one
        # SearchServer expects rather than one with a stray space in it.
        assert m.origins == "address,gazetteer"

    def test_origins_still_rejects_an_unknown_member(self):
        """Loosening the charset must not loosen the enum behind it."""
        with pytest.raises(ValidationError, match="nonsense"):
            GeocodeInput(search_text="Bern", origins="address, nonsense")
