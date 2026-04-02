# tests/test_rest_api.py
from __future__ import annotations

import pytest
from pydantic import ValidationError

from swisstopo_mcp.rest_api import (
    SearchLayersInput,
    IdentifyInput,
    FindFeaturesInput,
    GetFeatureInput,
    search_layers,
    identify_features,
    find_features,
    get_feature,
    format_layer_results,
    format_identify_results,
    format_find_results,
    format_feature_detail,
)


# ---------------------------------------------------------------------------
# Input Model Validation
# ---------------------------------------------------------------------------


class TestSearchLayersInput:
    def test_defaults(self):
        m = SearchLayersInput(query="gebaeude")
        assert m.query == "gebaeude"
        assert m.lang == "de"
        assert m.limit == 10

    def test_custom_values(self):
        m = SearchLayersInput(query="wald", lang="fr", limit=5)
        assert m.lang == "fr"
        assert m.limit == 5

    def test_strip_whitespace(self):
        m = SearchLayersInput(query="  gebaeude  ")
        assert m.query == "gebaeude"

    def test_empty_query_rejected(self):
        with pytest.raises(ValidationError):
            SearchLayersInput(query="")

    def test_query_too_long(self):
        with pytest.raises(ValidationError):
            SearchLayersInput(query="x" * 201)

    def test_limit_bounds(self):
        with pytest.raises(ValidationError):
            SearchLayersInput(query="test", limit=0)
        with pytest.raises(ValidationError):
            SearchLayersInput(query="test", limit=31)

    def test_extra_fields_forbidden(self):
        with pytest.raises(ValidationError):
            SearchLayersInput(query="test", foo="bar")


class TestIdentifyInput:
    def test_defaults(self):
        m = IdentifyInput(layers="ch.bfs.gebaeude_wohnungs_register", lat=47.0, lon=8.0)
        assert m.tolerance == 0
        assert m.sr == 4326

    def test_lat_out_of_range(self):
        with pytest.raises(ValidationError):
            IdentifyInput(layers="ch.test", lat=48.0, lon=8.0)
        with pytest.raises(ValidationError):
            IdentifyInput(layers="ch.test", lat=45.0, lon=8.0)

    def test_lon_out_of_range(self):
        with pytest.raises(ValidationError):
            IdentifyInput(layers="ch.test", lat=47.0, lon=5.0)
        with pytest.raises(ValidationError):
            IdentifyInput(layers="ch.test", lat=47.0, lon=11.0)

    def test_tolerance_bounds(self):
        with pytest.raises(ValidationError):
            IdentifyInput(layers="ch.test", lat=47.0, lon=8.0, tolerance=-1)
        with pytest.raises(ValidationError):
            IdentifyInput(layers="ch.test", lat=47.0, lon=8.0, tolerance=201)

    def test_layers_min_length(self):
        with pytest.raises(ValidationError):
            IdentifyInput(layers="x", lat=47.0, lon=8.0)

    def test_extra_fields_forbidden(self):
        with pytest.raises(ValidationError):
            IdentifyInput(layers="ch.test", lat=47.0, lon=8.0, extra="no")


class TestFindFeaturesInput:
    def test_defaults(self):
        m = FindFeaturesInput(layer="ch.test", search_text="100", search_field="id")
        assert m.contains is True

    def test_contains_false(self):
        m = FindFeaturesInput(layer="ch.test", search_text="100", search_field="id", contains=False)
        assert m.contains is False

    def test_empty_search_text_rejected(self):
        with pytest.raises(ValidationError):
            FindFeaturesInput(layer="ch.test", search_text="", search_field="id")

    def test_extra_fields_forbidden(self):
        with pytest.raises(ValidationError):
            FindFeaturesInput(layer="ch.test", search_text="x", search_field="id", extra="no")


class TestGetFeatureInput:
    def test_defaults(self):
        m = GetFeatureInput(layer="ch.test", feature_id="123")
        assert m.sr == 4326

    def test_custom_sr(self):
        m = GetFeatureInput(layer="ch.test", feature_id="123", sr=2056)
        assert m.sr == 2056

    def test_short_layer_rejected(self):
        with pytest.raises(ValidationError):
            GetFeatureInput(layer="x", feature_id="123")

    def test_empty_feature_id_rejected(self):
        with pytest.raises(ValidationError):
            GetFeatureInput(layer="ch.test", feature_id="")

    def test_extra_fields_forbidden(self):
        with pytest.raises(ValidationError):
            GetFeatureInput(layer="ch.test", feature_id="1", extra="no")


# ---------------------------------------------------------------------------
# Format Helpers
# ---------------------------------------------------------------------------


class TestFormatLayerResults:
    def test_empty(self):
        result = format_layer_results([], "test")
        assert "Keine Layer gefunden" in result
        assert "test" in result

    def test_typical(self):
        results = [
            {
                "id": "ch.bfs.gebaeude_wohnungs_register",
                "attrs": {
                    "label": "<b>Gebäude</b>- und Wohnungsregister",
                    "detail": "Eidgenössisches GWR",
                },
            },
            {
                "id": "ch.swisstopo.vec25-gebaeude",
                "attrs": {
                    "label": "Gebäude swissTLM3D",
                    "detail": "TLM Gebäude",
                },
            },
        ]
        md = format_layer_results(results, "gebaeude")
        assert "Layer-ID" in md
        assert "ch.bfs.gebaeude_wohnungs_register" in md
        assert "ch.swisstopo.vec25-gebaeude" in md
        # HTML tags should be stripped
        assert "<b>" not in md

    def test_missing_attrs_graceful(self):
        results = [{"id": "ch.test", "attrs": {}}]
        md = format_layer_results(results, "test")
        assert "ch.test" in md


class TestFormatIdentifyResults:
    def test_empty(self):
        result = format_identify_results([])
        assert "Keine Features gefunden" in result

    def test_typical(self):
        results = [
            {
                "layerBodId": "ch.bfs.gebaeude_wohnungs_register",
                "layerName": "GWR",
                "featureId": "123",
                "attributes": {"egid": "1234", "strname": "Bahnhofstrasse"},
            }
        ]
        md = format_identify_results(results)
        assert "GWR" in md or "ch.bfs.gebaeude_wohnungs_register" in md
        assert "egid" in md
        assert "1234" in md


class TestFormatFindResults:
    def test_empty(self):
        result = format_find_results([])
        assert "Keine Features gefunden" in result

    def test_typical(self):
        results = [
            {
                "layerBodId": "ch.test",
                "layerName": "Test Layer",
                "featureId": "42",
                "attributes": {"name": "Zürich"},
            }
        ]
        md = format_find_results(results)
        assert "42" in md
        assert "Zürich" in md


class TestFormatFeatureDetail:
    def test_typical(self):
        data = {
            "feature": {
                "featureId": "99",
                "layerBodId": "ch.test",
                "layerName": "Test",
                "attributes": {"name": "Bern", "population": 130000},
            }
        }
        md = format_feature_detail(data)
        assert "99" in md
        assert "Bern" in md
        assert "130000" in md

    def test_with_geometry(self):
        data = {
            "feature": {
                "featureId": "1",
                "layerBodId": "ch.test",
                "layerName": "Test",
                "attributes": {"x": "y"},
                "geometry": {"type": "Point", "coordinates": [8.0, 47.0]},
            }
        }
        md = format_feature_detail(data)
        assert "Geometrie" in md or "geometry" in md.lower()


# ---------------------------------------------------------------------------
# Async Handler Tests (mocked)
# ---------------------------------------------------------------------------

class TestSearchLayersHandler:
    async def test_search_layers_mocked(self, monkeypatch):
        async def mock_request(path, params=None):
            return {
                "results": [
                    {
                        "id": "ch.bfs.gebaeude_wohnungs_register",
                        "attrs": {
                            "label": "Gebäude- und Wohnungsregister",
                            "detail": "GWR",
                        },
                    }
                ]
            }

        monkeypatch.setattr("swisstopo_mcp.rest_api.geo_admin_request", mock_request)
        result = await search_layers(SearchLayersInput(query="gebaeude"))
        assert "ch.bfs.gebaeude_wohnungs_register" in result

    async def test_search_layers_empty(self, monkeypatch):
        async def mock_request(path, params=None):
            return {"results": []}

        monkeypatch.setattr("swisstopo_mcp.rest_api.geo_admin_request", mock_request)
        result = await search_layers(SearchLayersInput(query="xyznotfound"))
        assert "Keine Layer gefunden" in result


class TestIdentifyFeaturesHandler:
    async def test_identify_mocked(self, monkeypatch):
        async def mock_request(path, params=None):
            return {
                "results": [
                    {
                        "layerBodId": "ch.bfs.gebaeude_wohnungs_register",
                        "layerName": "GWR",
                        "featureId": "55",
                        "attributes": {"egid": "9999"},
                    }
                ]
            }

        monkeypatch.setattr("swisstopo_mcp.rest_api.geo_admin_request", mock_request)
        result = await identify_features(
            IdentifyInput(layers="ch.bfs.gebaeude_wohnungs_register", lat=47.38, lon=8.54)
        )
        assert "9999" in result

    async def test_identify_empty(self, monkeypatch):
        async def mock_request(path, params=None):
            return {"results": []}

        monkeypatch.setattr("swisstopo_mcp.rest_api.geo_admin_request", mock_request)
        result = await identify_features(
            IdentifyInput(layers="ch.test", lat=47.0, lon=8.0)
        )
        assert "Keine Features gefunden" in result


class TestFindFeaturesHandler:
    async def test_find_mocked(self, monkeypatch):
        async def mock_request(path, params=None):
            return {
                "results": [
                    {
                        "layerBodId": "ch.test",
                        "layerName": "Test",
                        "featureId": "7",
                        "attributes": {"name": "Bern"},
                    }
                ]
            }

        monkeypatch.setattr("swisstopo_mcp.rest_api.geo_admin_request", mock_request)
        result = await find_features(
            FindFeaturesInput(layer="ch.test", search_text="Bern", search_field="name")
        )
        assert "Bern" in result


class TestGetFeatureHandler:
    async def test_get_feature_mocked(self, monkeypatch):
        async def mock_request(path, params=None):
            return {
                "feature": {
                    "featureId": "42",
                    "layerBodId": "ch.test",
                    "layerName": "Test",
                    "attributes": {"key": "value"},
                }
            }

        monkeypatch.setattr("swisstopo_mcp.rest_api.geo_admin_request", mock_request)
        result = await get_feature(GetFeatureInput(layer="ch.test", feature_id="42"))
        assert "value" in result

    async def test_get_feature_error(self, monkeypatch):
        import httpx

        async def mock_request(path, params=None):
            resp = httpx.Response(404, request=httpx.Request("GET", "http://test"))
            raise httpx.HTTPStatusError("Not found", request=resp.request, response=resp)

        monkeypatch.setattr("swisstopo_mcp.rest_api.geo_admin_request", mock_request)
        result = await get_feature(GetFeatureInput(layer="ch.test", feature_id="999"))
        assert "Fehler" in result or "nicht gefunden" in result


# ---------------------------------------------------------------------------
# Live Tests (network required)
# ---------------------------------------------------------------------------

@pytest.mark.live
async def test_live_search_layers():
    result = await search_layers(SearchLayersInput(query="gebaeude"))
    assert "gebaeude" in result.lower() or "Gebäude" in result


@pytest.mark.live
async def test_live_identify():
    result = await identify_features(
        IdentifyInput(
            layers="ch.bfs.gebaeude_wohnungs_register",
            lat=47.3769,
            lon=8.5417,
            tolerance=50,
        )
    )
    # May or may not find features at this exact point, but should not error
    assert isinstance(result, str)
    assert len(result) > 0
