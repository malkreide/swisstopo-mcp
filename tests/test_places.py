# tests/test_places.py
"""Tests for the zoning / municipality / layer-info convenience tools.

These were ported from swiss-geodata-mcp (see
docs/merge-plan-swiss-geodata-mcp.md). Fixtures mirror the live payloads
verified for Seilergraben 76, Zürich (LV95 2683531 / 1247914).
"""
from __future__ import annotations

import httpx
import pytest
import respx
from pydantic import ValidationError

from swisstopo_mcp.api_client import GEO_ADMIN_BASE
from swisstopo_mcp.models import ARE_ZONING_CAVEAT
from swisstopo_mcp.rest_api import (
    LayerInfoInput,
    MunicipalityAtInput,
    ZoningAtInput,
    _as_bfs_number,
    format_layer_info,
    format_municipality,
    format_zoning,
    html_to_text,
    layer_info,
    municipality_at,
    zoning_at,
)

EAST, NORTH = 2683531.0, 1247914.0
IDENTIFY_URL = f"{GEO_ADMIN_BASE}/rest/services/ech/MapServer/identify"

ZONING_PAYLOAD = {
    "results": [
        {
            "attributes": {
                "name": "Zürich",
                "ch_code_hn": "13",
                "kt_kz": "ZH",
                "bfs_no": "261",  # string upstream
                "ch_bez_d": "Mischzonen",
                "ch_bez_f": "Zones mixtes",
            }
        }
    ]
}

MUNICIPALITY_PAYLOAD = {
    "results": [
        {"attributes": {"gemname": "Zürich", "gde_nr": 261, "kanton": "ZH", "jahr": 1950,
                        "is_current_jahr": False}},
        {"attributes": {"gemname": "Zürich", "gde_nr": 261, "kanton": "ZH", "jahr": 2025,
                        "is_current_jahr": True}},
    ]
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class TestAsBfsNumber:
    def test_coerces_string(self):
        """bauzonen serves bfs_no as a string; the join key must still be int."""
        assert _as_bfs_number("261") == 261

    def test_passes_through_int(self):
        assert _as_bfs_number(261) == 261

    def test_none_stays_none(self):
        assert _as_bfs_number(None) is None

    def test_garbage_becomes_none(self):
        assert _as_bfs_number("k.A.") is None


class TestHtmlToText:
    def test_strips_tags_and_collapses_whitespace(self):
        assert html_to_text("<div>Wohn\n  <b>zone</b></div>") == "Wohn zone"

    def test_unescapes_entities(self):
        assert html_to_text("<p>Zone&nbsp;A &amp; B</p>").replace("\xa0", " ") == "Zone A & B"

    def test_empty_string(self):
        assert html_to_text("") == ""


# ---------------------------------------------------------------------------
# Zoning
# ---------------------------------------------------------------------------


class TestZoningAt:
    @respx.mock
    async def test_maps_attributes(self):
        respx.get(IDENTIFY_URL).mock(return_value=httpx.Response(200, json=ZONING_PAYLOAD))
        out = await zoning_at(ZoningAtInput(easting=EAST, northing=NORTH))
        assert out.is_error is False
        z = out.results[0]
        assert z["zone_type_de"] == "Mischzonen"
        assert z["zone_type_fr"] == "Zones mixtes"
        assert z["code"] == "13"
        assert z["municipality"] == "Zürich"
        assert z["canton"] == "ZH"
        assert z["bfs_commune_number"] == 261  # normalised to int

    @respx.mock
    async def test_legal_caveat_on_every_record(self):
        """A client reading `results` must not lose the non-binding warning."""
        respx.get(IDENTIFY_URL).mock(return_value=httpx.Response(200, json=ZONING_PAYLOAD))
        out = await zoning_at(ZoningAtInput(easting=EAST, northing=NORTH))
        assert out.results[0]["legal_note"] == ARE_ZONING_CAVEAT
        assert "Nutzungsplanung" in out.summary

    @respx.mock
    async def test_sends_lv95_upstream(self):
        route = respx.get(IDENTIFY_URL).mock(
            return_value=httpx.Response(200, json=ZONING_PAYLOAD)
        )
        await zoning_at(ZoningAtInput(easting=EAST, northing=NORTH))
        params = route.calls[0].request.url.params
        assert params["sr"] == "2056"
        assert params["geometry"] == f"{EAST},{NORTH}"
        assert params["layers"] == "all:ch.are.bauzonen"

    @respx.mock
    async def test_accepts_wgs84_input(self):
        respx.get(IDENTIFY_URL).mock(return_value=httpx.Response(200, json=ZONING_PAYLOAD))
        out = await zoning_at(ZoningAtInput(lat=47.3769, lon=8.5417))
        assert out.is_error is False

    @respx.mock
    async def test_empty_result_is_soft_miss(self):
        respx.get(IDENTIFY_URL).mock(return_value=httpx.Response(200, json={"results": []}))
        out = await zoning_at(ZoningAtInput(easting=EAST, northing=NORTH))
        assert out.is_error is False
        assert out.match_type == "none"
        assert out.count == 0

    @respx.mock
    async def test_upstream_500_is_handled(self):
        respx.get(IDENTIFY_URL).mock(return_value=httpx.Response(500, text="boom"))
        out = await zoning_at(ZoningAtInput(easting=EAST, northing=NORTH))
        assert out.is_error is True
        assert "boom" not in out.summary

    def test_requires_coordinates(self):
        with pytest.raises(ValidationError):
            ZoningAtInput()


# ---------------------------------------------------------------------------
# Municipality
# ---------------------------------------------------------------------------


class TestMunicipalityAt:
    @respx.mock
    async def test_picks_current_year_record(self):
        """The layer carries one polygon per historical year."""
        respx.get(IDENTIFY_URL).mock(
            return_value=httpx.Response(200, json=MUNICIPALITY_PAYLOAD)
        )
        out = await municipality_at(MunicipalityAtInput(easting=EAST, northing=NORTH))
        assert out.count == 1
        assert out.results[0]["municipality"] == "Zürich"
        assert out.results[0]["bfs_commune_number"] == 261
        assert out.results[0]["canton"] == "ZH"

    @respx.mock
    async def test_no_current_record_is_soft_miss(self):
        historical_only = {
            "results": [
                {"attributes": {"gemname": "X", "gde_nr": 1, "kanton": "ZH",
                                "is_current_jahr": False}}
            ]
        }
        respx.get(IDENTIFY_URL).mock(return_value=httpx.Response(200, json=historical_only))
        out = await municipality_at(MunicipalityAtInput(easting=EAST, northing=NORTH))
        assert out.count == 0
        assert out.match_type == "none"
        assert "Grenze" in out.summary

    @respx.mock
    async def test_requests_enough_results_for_history(self):
        route = respx.get(IDENTIFY_URL).mock(
            return_value=httpx.Response(200, json=MUNICIPALITY_PAYLOAD)
        )
        await municipality_at(MunicipalityAtInput(easting=EAST, northing=NORTH))
        assert route.calls[0].request.url.params["sr"] == "2056"


# ---------------------------------------------------------------------------
# Layer info
# ---------------------------------------------------------------------------


class TestLayerInfo:
    @respx.mock
    async def test_returns_fields_and_legend(self):
        respx.get(f"{GEO_ADMIN_BASE}/rest/services/api/MapServer/ch.are.bauzonen").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "ch.are.bauzonen",
                    "name": "Bauzonen Schweiz",
                    "fields": [{"name": "ch_bez_d", "type": "text", "values": ["Wohnzonen"]}],
                },
            )
        )
        respx.get(
            f"{GEO_ADMIN_BASE}/rest/services/all/MapServer/ch.are.bauzonen/legend"
        ).mock(return_value=httpx.Response(200, text="<div>Wohnzonen</div>"))

        out = await layer_info(LayerInfoInput(layer="ch.are.bauzonen"))
        assert out.is_error is False
        meta = out.results[0]
        assert meta["layer_id"] == "ch.are.bauzonen"
        assert meta["fields"][0]["name"] == "ch_bez_d"
        assert meta["legend"] == "Wohnzonen"

    @respx.mock
    async def test_missing_legend_is_not_fatal(self):
        """A layer without a legend must still return its fields."""
        respx.get(f"{GEO_ADMIN_BASE}/rest/services/api/MapServer/ch.are.bauzonen").mock(
            return_value=httpx.Response(
                200, json={"id": "ch.are.bauzonen", "name": "Bauzonen", "fields": []}
            )
        )
        respx.get(
            f"{GEO_ADMIN_BASE}/rest/services/all/MapServer/ch.are.bauzonen/legend"
        ).mock(return_value=httpx.Response(404, text="not found"))

        out = await layer_info(LayerInfoInput(layer="ch.are.bauzonen"))
        assert out.is_error is False
        assert out.results[0]["legend"] is None

    @respx.mock
    async def test_upstream_error_is_handled(self):
        respx.get(f"{GEO_ADMIN_BASE}/rest/services/api/MapServer/ch.foo").mock(
            return_value=httpx.Response(500, text="boom")
        )
        out = await layer_info(LayerInfoInput(layer="ch.foo"))
        assert out.is_error is True


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------


class TestFormatters:
    def test_zoning_empty(self):
        assert "Keine Bauzone" in format_zoning([])

    def test_zoning_includes_caveat(self):
        out = format_zoning([{"zone_type_de": "Wohnzonen", "code": "1",
                              "municipality": "Zürich", "canton": "ZH"}])
        assert "Wohnzonen" in out and "Nutzungsplanung" in out

    def test_municipality_none(self):
        assert "Keine aktuelle Gemeinde" in format_municipality(None)

    def test_municipality_shows_bfs(self):
        out = format_municipality(
            {"municipality": "Zürich", "bfs_commune_number": 261, "canton": "ZH"}
        )
        assert "Zürich" in out and "261" in out

    def test_layer_info_without_fields(self):
        out = format_layer_info({"layer_id": "ch.x", "name": "X", "fields": []})
        assert "Keine abfragbaren Felder" in out


# ---------------------------------------------------------------------------
# Live (skipped in CI)
# ---------------------------------------------------------------------------


@pytest.mark.live
class TestPlacesLive:
    async def test_zoning_at_zurich(self):
        out = await zoning_at(ZoningAtInput(easting=EAST, northing=NORTH))
        assert out.is_error is False
        assert out.results[0]["canton"] == "ZH"
        assert out.results[0]["bfs_commune_number"] == 261

    async def test_municipality_at_zurich(self):
        out = await municipality_at(MunicipalityAtInput(easting=EAST, northing=NORTH))
        assert out.is_error is False
        assert out.results[0]["municipality"] == "Zürich"
        assert out.results[0]["bfs_commune_number"] == 261

    async def test_layer_info_bauzonen(self):
        out = await layer_info(LayerInfoInput(layer="ch.are.bauzonen"))
        assert out.is_error is False
        assert out.results[0]["fields"]
