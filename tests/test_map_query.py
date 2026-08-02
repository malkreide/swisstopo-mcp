# tests/test_map_query.py
"""The merged api3 tool (audit ARCH-006).

Five tools — one per REST endpoint, which is the 1:1 API mapping the check
names — became one `swisstopo_map_query` taking an `operation`. That trade is
only worth making if the merged surface is at least as navigable as the five
separate ones were, so this module tests the two properties that decide it:

1. **A wrong argument is refused, not ignored.** With five tools, sending
   `search_field` to the point query was impossible — the field did not exist on
   that tool. With one tool every operation's fields are visible on every call,
   so the schema alone no longer prevents it. `_OPERATION_FIELDS` is what
   replaces that protection, and if it silently dropped the stray field instead
   of rejecting it the merge would have introduced exactly the defect class
   ARCH-003 is about: a plausible answer to a question nobody asked.

2. **The operation reaches the right handler with the right arguments.** The
   dispatcher is new code between the schema and five handlers that were
   previously reached directly, and a mis-wired branch would return real,
   well-formed data from the wrong endpoint — the hardest kind of bug to notice.

Argument validation *within* an operation (patterns, bounds, the LV95 rules) is
not retested here. `MapQueryInput` delegates the point rules to
`SwissPointInput` and the dispatcher rebuilds the original sub-models, so those
constraints are still the ones `test_rest_api.py` and `test_lv95_input.py`
cover — the delegation itself is what is asserted below.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from swisstopo_mcp import rest_api
from swisstopo_mcp.models import ToolResponse
from swisstopo_mcp.rest_api import (
    _OPERATION_FIELDS,
    MapQueryInput,
    MapQueryOperation,
    map_query,
)

OPERATIONS = tuple(MapQueryOperation.__args__)

# A minimal valid payload per operation, reused across the tests below.
VALID: dict[str, dict] = {
    "search_layers": {"query": "bauzonen"},
    "layer_info": {"layer": "ch.are.bauzonen"},
    "features_at_point": {"layers": "ch.are.bauzonen", "lat": 47.36, "lon": 8.52},
    "features_by_attribute": {
        "layer": "ch.are.bauzonen",
        "search_text": "Zug",
        "search_field": "name",
    },
    "feature_by_id": {"layer": "ch.are.bauzonen", "feature_id": "123"},
}


def _input(operation: str, **overrides) -> MapQueryInput:
    return MapQueryInput(operation=operation, **{**VALID[operation], **overrides})


class TestTheOperationTableCoversTheEnum:
    """The table and the Literal are two lists of the same thing, and a new
    operation added to one but not the other fails obscurely — a KeyError deep
    in validation, or an operation nothing can reach."""

    def test_every_operation_has_a_field_spec(self):
        assert set(_OPERATION_FIELDS) == set(OPERATIONS)

    def test_every_operation_has_a_valid_example_here(self):
        """Keeps this module honest as the surface grows."""
        assert set(VALID) == set(OPERATIONS)

    @pytest.mark.parametrize("operation", OPERATIONS)
    def test_the_minimal_payload_validates(self, operation):
        assert _input(operation).operation == operation

    @pytest.mark.parametrize("operation", OPERATIONS)
    def test_required_and_optional_do_not_overlap(self, operation):
        required, optional = _OPERATION_FIELDS[operation]
        assert not (required & optional), (
            "a field cannot be both required and merely accepted — the stray "
            "check subtracts both, so an overlap hides a missing requirement"
        )

    @pytest.mark.parametrize("operation", OPERATIONS)
    def test_every_named_field_exists_on_the_model(self, operation):
        required, optional = _OPERATION_FIELDS[operation]
        for name in required | optional:
            assert name in MapQueryInput.model_fields, (
                f"{name!r} is in the table for {operation!r} but is not a field; "
                "a renamed field would otherwise become permanently unusable"
            )


class TestARequiredArgumentIsNamed:
    @pytest.mark.parametrize("operation", OPERATIONS)
    def test_omitting_everything_is_rejected(self, operation):
        with pytest.raises(ValidationError) as exc:
            MapQueryInput(operation=operation)
        assert operation in str(exc.value)

    def test_the_message_names_what_is_missing(self):
        with pytest.raises(ValidationError, match="Fehlend: search_field, search_text"):
            MapQueryInput(operation="features_by_attribute", layer="ch.are.bauzonen")

    def test_a_partially_supplied_operation_is_rejected(self):
        with pytest.raises(ValidationError, match="Fehlend: feature_id"):
            MapQueryInput(operation="feature_by_id", layer="ch.are.bauzonen")


class TestAnArgumentFromAnotherOperationIsRefused:
    """The property that replaces what five separate schemas used to guarantee."""

    def test_a_stray_field_is_rejected(self):
        with pytest.raises(ValidationError, match="search_field"):
            _input("features_at_point", search_field="name")

    def test_the_message_names_the_accepted_fields(self):
        with pytest.raises(ValidationError, match="Diese operation akzeptiert"):
            _input("search_layers", layer="ch.are.bauzonen")

    @pytest.mark.parametrize("operation", OPERATIONS)
    def test_no_operation_silently_accepts_a_foreign_field(self, operation):
        """Swept over the whole matrix rather than spot-checked: the cost of
        getting this wrong is a silently ignored argument, which looks like a
        successful call."""
        required, optional = _OPERATION_FIELDS[operation]
        own = required | optional
        foreign = {
            name
            for spec in _OPERATION_FIELDS.values()
            for name in (spec[0] | spec[1])
        } - own
        for name in sorted(foreign):
            with pytest.raises(ValidationError, match=name):
                _input(operation, **{name: _SAMPLE[name]})

    def test_a_default_valued_field_still_counts_as_supplied(self):
        """`contains` defaults to True, so a None-check could not tell "sent it
        by mistake" from "left it alone". Passing the default value explicitly
        must still be refused."""
        with pytest.raises(ValidationError, match="contains"):
            _input("search_layers", contains=True)

    def test_leaving_a_foreign_default_alone_is_fine(self):
        """The other half of the same property: an unsent field with a non-None
        default must not be mistaken for one the caller supplied."""
        assert _input("search_layers").contains is True


# Type-correct sample values for the sweep above, so a rejection can only be
# the operation check rather than a pattern or bounds failure.
_SAMPLE: dict[str, object] = {
    "query": "bauzonen",
    "layer": "ch.are.bauzonen",
    "layers": "ch.are.bauzonen",
    "lat": 47.36,
    "lon": 8.52,
    "easting": 2683531.0,
    "northing": 1247914.0,
    "tolerance": 10,
    "search_text": "Zug",
    "search_field": "name",
    "contains": False,
    "feature_id": "123",
    "sr": 2056,
    "lang": "fr",
    "limit": 5,
}


class TestThePointRulesAreDelegatedNotRestated:
    """`features_at_point` must give the same errors as every other
    point-taking tool. Re-implementing the rules here would have produced a
    second, worse dialect of them."""

    def test_a_missing_point_is_rejected(self):
        with pytest.raises(ValidationError, match="Koordinaten fehlen"):
            MapQueryInput(operation="features_at_point", layers="ch.are.bauzonen")

    def test_both_coordinate_pairs_are_rejected(self):
        with pytest.raises(ValidationError, match="nicht beides"):
            _input("features_at_point", easting=2683531.0, northing=1247914.0)

    def test_half_a_pair_is_named_as_such(self):
        with pytest.raises(ValidationError, match="Unvollständig"):
            MapQueryInput(
                operation="features_at_point", layers="ch.are.bauzonen", lat=47.36
            )

    def test_degrees_in_the_lv95_fields_are_diagnosed(self):
        """The specific mistake SwissPointInput exists to name."""
        with pytest.raises(ValidationError, match="WGS84-Grad"):
            MapQueryInput(
                operation="features_at_point",
                layers="ch.are.bauzonen",
                easting=8.5,
                northing=47.3,
            )

    def test_lv95_is_accepted(self):
        model = MapQueryInput(
            operation="features_at_point",
            layers="ch.are.bauzonen",
            easting=2683531.0,
            northing=1247914.0,
        )
        assert model.easting == 2683531.0


class TestDispatch:
    """Each operation reaches its own handler, and carries its arguments there.

    A mis-wired branch would return well-formed data from the wrong endpoint,
    so asserting "no error" would not catch it — the handler identity and the
    arguments it received are what these check.
    """

    HANDLERS = {
        "search_layers": "search_layers",
        "layer_info": "layer_info",
        "features_at_point": "identify_features",
        "features_by_attribute": "find_features",
        "feature_by_id": "get_feature",
    }

    @pytest.fixture
    def spy(self, monkeypatch):
        seen: dict[str, object] = {}

        def _install(name):
            async def _handler(params, *args):
                seen["handler"] = name
                seen["params"] = params
                return ToolResponse.ok("stub", [], match_type="exact")

            monkeypatch.setattr(rest_api, name, _handler)

        for name in set(self.HANDLERS.values()):
            _install(name)
        return seen

    @pytest.mark.parametrize("operation", OPERATIONS)
    async def test_the_operation_reaches_its_own_handler(self, spy, operation):
        await map_query(_input(operation))
        assert spy["handler"] == self.HANDLERS[operation]

    @pytest.mark.parametrize("operation", OPERATIONS)
    async def test_every_operation_returns_a_tool_response(self, spy, operation):
        assert isinstance(await map_query(_input(operation)), ToolResponse)

    async def test_search_arguments_survive_the_hop(self, spy):
        await map_query(_input("search_layers", lang="fr", limit=3))
        assert (spy["params"].query, spy["params"].lang, spy["params"].limit) == (
            "bauzonen",
            "fr",
            3,
        )

    async def test_point_arguments_survive_the_hop(self, spy):
        await map_query(_input("features_at_point", tolerance=25))
        params = spy["params"]
        assert (params.layers, params.lat, params.lon, params.tolerance) == (
            "ch.are.bauzonen",
            47.36,
            8.52,
            25,
        )

    async def test_lv95_survives_the_hop_unconverted(self, spy):
        """The sub-model, not the dispatcher, owns the projection — passing
        lat/lon through as LV95 would put degrees on the wire."""
        await map_query(
            MapQueryInput(
                operation="features_at_point",
                layers="ch.are.bauzonen",
                easting=2683531.0,
                northing=1247914.0,
            )
        )
        assert (spy["params"].easting, spy["params"].northing) == (2683531.0, 1247914.0)
        assert spy["params"].lat is None

    async def test_attribute_arguments_survive_the_hop(self, spy):
        await map_query(_input("features_by_attribute", contains=False))
        params = spy["params"]
        assert (params.layer, params.search_text, params.search_field, params.contains) == (
            "ch.are.bauzonen",
            "Zug",
            "name",
            False,
        )

    async def test_feature_arguments_survive_the_hop(self, spy):
        await map_query(_input("feature_by_id", sr=2056))
        params = spy["params"]
        assert (params.layer, params.feature_id, params.sr) == (
            "ch.are.bauzonen",
            "123",
            2056,
        )

    async def test_the_context_reaches_layer_info(self, monkeypatch):
        """`layer_info` is the one operation that reports progress, and the ctx
        is threaded by hand — the exact shape of the SDK-003 defect."""
        seen: dict[str, object] = {}

        async def _handler(params, ctx=None):
            seen["ctx"] = ctx
            return ToolResponse.ok("stub", [], match_type="exact")

        monkeypatch.setattr(rest_api, "layer_info", _handler)
        sentinel = object()
        await map_query(_input("layer_info"), sentinel)
        assert seen["ctx"] is sentinel


class TestAnUnhandledOperationFailsLoudly:
    async def test_an_operation_with_no_branch_raises(self, monkeypatch):
        """Adding an operation to the Literal and the table but forgetting the
        dispatcher branch must not land silently in the last handler."""
        model = _input("search_layers")
        object.__setattr__(model, "operation", "invented_operation")
        with pytest.raises(ValueError, match="Unbehandelte operation"):
            await map_query(model)


# ---------------------------------------------------------------------------
# Live coverage (audit OPS-001)
#
# The five handlers already had live tests, reached directly. Those still run
# and still cover the upstream contract; what they cannot cover is the
# dispatcher, which is the layer a client now actually calls through. These go
# through `map_query` for every operation, so the nightly run exercises the
# real path rather than the one that existed before the merge.
# ---------------------------------------------------------------------------

_COMMUNE_LAYER = "ch.swisstopo.swissboundaries3d-gemeinde-flaeche.fill"

# A layer whose feature IDs are SLOIDs — `ch:1:sloid:91220::83`. The round-trip
# below used to run on `_COMMUNE_LAYER` alone, whose IDs are bare integers, and
# so never touched the charset. `feature_id` rejected every colon, meaning
# `features_at_point` handed out IDs that `feature_by_id` refused to take back.
_COLON_ID_LAYER = "ch.bav.haltestellen-oev"


@pytest.mark.live
class TestSwisstopoMapQueryLive:
    async def test_search_layers(self):
        result = await map_query(
            MapQueryInput(operation="search_layers", query="gebaeude")
        )
        assert result.is_error is False, result.summary

    async def test_layer_info(self):
        result = await map_query(
            MapQueryInput(operation="layer_info", layer=_COMMUNE_LAYER)
        )
        assert result.is_error is False, result.summary
        assert result.results[0]["fields"], "a layer with no queryable fields is drift"

    async def test_features_at_point(self):
        result = await map_query(
            MapQueryInput(
                operation="features_at_point",
                layers=_COMMUNE_LAYER,
                lat=47.3769,
                lon=8.5417,
                tolerance=50,
            )
        )
        assert result.is_error is False, result.summary

    async def test_features_by_attribute(self):
        result = await map_query(
            MapQueryInput(
                operation="features_by_attribute",
                layer=_COMMUNE_LAYER,
                search_text="Zürich",
                search_field="gemname",
            )
        )
        assert result.is_error is False, result.summary
        if result.match_type == "none":
            assert result.note, "an empty attribute search must carry a next step"

    async def test_feature_by_id(self):
        """Chained on the attribute search so the id cannot go stale."""
        found = await map_query(
            MapQueryInput(
                operation="features_by_attribute",
                layer=_COMMUNE_LAYER,
                search_text="Zürich",
                search_field="gemname",
            )
        )
        if not found.results:
            pytest.skip("attribute search returned nothing today")
        feature_id = found.results[0].get("featureId") or found.results[0].get("id")
        if feature_id is None:
            pytest.skip("upstream result carries no usable feature id")
        result = await map_query(
            MapQueryInput(
                operation="feature_by_id",
                layer=_COMMUNE_LAYER,
                feature_id=str(feature_id),
            )
        )
        assert result.is_error is False, result.summary

    async def test_a_feature_id_the_server_emits_is_one_it_accepts_back(self):
        """The pairing `features_at_point` -> `feature_by_id` is the documented
        way to drill into a hit, so an ID the first call hands out must survive
        the second. It did not for any layer using SLOIDs: the identifier
        charset had no colon, and the follow-up died in input validation before
        a request was made.

        Run on a colon-bearing layer specifically. The sibling test above uses
        integer IDs, which is why this class was green while the pairing was
        broken for 201 of the 761 real feature IDs sampled across six layers.
        """
        found = await map_query(
            MapQueryInput(
                operation="features_at_point",
                layers=_COLON_ID_LAYER,
                lat=47.3769,
                lon=8.5417,
                tolerance=100,
            )
        )
        if not found.results:
            pytest.skip("no transit stop near the probe point today")
        feature_id = found.results[0].get("featureId") or found.results[0].get("id")
        if feature_id is None:
            pytest.skip("upstream result carries no usable feature id")

        result = await map_query(
            MapQueryInput(
                operation="feature_by_id",
                layer=_COLON_ID_LAYER,
                feature_id=str(feature_id),
            )
        )
        assert result.is_error is False, result.summary
        assert str(feature_id) in result.summary
