# tests/test_geocoding.py
from __future__ import annotations

import pytest
from pydantic import ValidationError

from swisstopo_mcp.geocoding import (
    GeocodeInput,
    ReverseGeocodeInput,
    format_geocode_results,
    geocode,
    reverse_geocode,
)

# ---------------------------------------------------------------------------
# Input Model Validation
# ---------------------------------------------------------------------------


class TestGeocodeInput:
    def test_defaults(self):
        m = GeocodeInput(search_text="Bern")
        assert m.search_text == "Bern"
        assert m.origins is None
        assert m.sr == 4326
        assert m.limit == 10

    def test_custom_values(self):
        m = GeocodeInput(search_text="Zürich", origins="address", sr=2056, limit=5)
        assert m.origins == "address"
        assert m.sr == 2056
        assert m.limit == 5

    def test_strip_whitespace(self):
        m = GeocodeInput(search_text="  Bern  ")
        assert m.search_text == "Bern"

    def test_too_short_rejected(self):
        with pytest.raises(ValidationError):
            GeocodeInput(search_text="B")

    def test_too_long_rejected(self):
        with pytest.raises(ValidationError):
            GeocodeInput(search_text="x" * 201)

    def test_limit_bounds(self):
        with pytest.raises(ValidationError):
            GeocodeInput(search_text="Bern", limit=0)
        with pytest.raises(ValidationError):
            GeocodeInput(search_text="Bern", limit=51)

    def test_limit_at_bounds(self):
        m1 = GeocodeInput(search_text="Bern", limit=1)
        assert m1.limit == 1
        m2 = GeocodeInput(search_text="Bern", limit=50)
        assert m2.limit == 50

    def test_extra_fields_forbidden(self):
        with pytest.raises(ValidationError):
            GeocodeInput(search_text="Bern", foo="bar")

    def test_origins_none_allowed(self):
        m = GeocodeInput(search_text="Bern", origins=None)
        assert m.origins is None

    def test_origins_set(self):
        m = GeocodeInput(search_text="3000", origins="zipcode")
        assert m.origins == "zipcode"


class TestReverseGeocodeInput:
    def test_defaults(self):
        m = ReverseGeocodeInput(lat=47.38, lon=8.54)
        assert m.limit == 5
        assert m.sr == 4326

    def test_custom_values(self):
        m = ReverseGeocodeInput(lat=46.95, lon=7.44, limit=3, sr=2056)
        assert m.limit == 3
        assert m.sr == 2056

    def test_lat_too_low(self):
        with pytest.raises(ValidationError):
            ReverseGeocodeInput(lat=45.7, lon=8.0)

    def test_lat_too_high(self):
        with pytest.raises(ValidationError):
            ReverseGeocodeInput(lat=48.0, lon=8.0)

    def test_lon_too_low(self):
        with pytest.raises(ValidationError):
            ReverseGeocodeInput(lat=47.0, lon=5.8)

    def test_lon_too_high(self):
        with pytest.raises(ValidationError):
            ReverseGeocodeInput(lat=47.0, lon=10.6)

    def test_lat_lon_at_bounds(self):
        m = ReverseGeocodeInput(lat=45.8, lon=5.9)
        assert m.lat == 45.8
        m2 = ReverseGeocodeInput(lat=47.9, lon=10.5)
        assert m2.lon == 10.5

    def test_limit_bounds(self):
        with pytest.raises(ValidationError):
            ReverseGeocodeInput(lat=47.0, lon=8.0, limit=0)
        with pytest.raises(ValidationError):
            ReverseGeocodeInput(lat=47.0, lon=8.0, limit=11)

    def test_limit_at_bounds(self):
        m1 = ReverseGeocodeInput(lat=47.0, lon=8.0, limit=1)
        assert m1.limit == 1
        m2 = ReverseGeocodeInput(lat=47.0, lon=8.0, limit=10)
        assert m2.limit == 10

    def test_extra_fields_forbidden(self):
        with pytest.raises(ValidationError):
            ReverseGeocodeInput(lat=47.0, lon=8.0, extra="no")


# ---------------------------------------------------------------------------
# Format Helper
# ---------------------------------------------------------------------------


class TestFormatGeocodeResults:
    def test_empty(self):
        result = format_geocode_results([])
        assert "Keine" in result or "keine" in result.lower()

    def test_typical(self):
        results = [
            {
                "attrs": {
                    "label": "Bundesplatz 1, 3005 Bern",
                    "lat": 46.9466,
                    "lon": 7.4441,
                    "origin": "address",
                    "detail": "Bundesplatz 1 3005 Bern",
                }
            },
            {
                "attrs": {
                    "label": "Bundesgasse 3, 3011 Bern",
                    "lat": 46.9470,
                    "lon": 7.4450,
                    "origin": "address",
                    "detail": "Bundesgasse 3 3011 Bern",
                }
            },
        ]
        md = format_geocode_results(results)
        assert "Adresse" in md
        assert "Lat" in md
        assert "Lon" in md
        assert "Bern" in md
        assert "46.9466" in md or "46.947" in md

    def test_table_structure(self):
        results = [
            {
                "attrs": {
                    "label": "Bahnhofstrasse 1, 8001 Zürich",
                    "lat": 47.3769,
                    "lon": 8.5417,
                    "origin": "address",
                    "detail": "Bahnhofstrasse 1 8001 Zürich",
                }
            }
        ]
        md = format_geocode_results(results)
        # Should be a Markdown table with pipes
        assert "|" in md

    def test_missing_attrs_graceful(self):
        results = [{"attrs": {}}]
        md = format_geocode_results(results)
        # Should not raise, should return something
        assert isinstance(md, str)

    def test_typ_column_shows_origin(self):
        results = [
            {
                "attrs": {
                    "label": "3000",
                    "lat": 46.94,
                    "lon": 7.44,
                    "origin": "zipcode",
                    "detail": "3000 Bern",
                }
            }
        ]
        md = format_geocode_results(results)
        assert "zipcode" in md


# ---------------------------------------------------------------------------
# Async Handler Tests (mocked)
# ---------------------------------------------------------------------------


class TestGeocodeHandler:
    async def test_geocode_mocked(self, monkeypatch):
        async def mock_request(path, params=None):
            return {
                "results": [
                    {
                        "attrs": {
                            "label": "Bundesplatz 1, 3005 Bern",
                            "lat": 46.9466,
                            "lon": 7.4441,
                            "origin": "address",
                            "detail": "Bundesplatz 1 3005 Bern",
                        }
                    }
                ]
            }

        monkeypatch.setattr("swisstopo_mcp.geocoding.geo_admin_request", mock_request)
        result = await geocode(GeocodeInput(search_text="Bundesplatz Bern"))
        assert "Bern" in result
        assert "46.9466" in result or "46.947" in result

    async def test_geocode_with_origins(self, monkeypatch):
        captured = {}

        async def mock_request(path, params=None):
            captured["params"] = params
            return {"results": []}

        monkeypatch.setattr("swisstopo_mcp.geocoding.geo_admin_request", mock_request)
        await geocode(GeocodeInput(search_text="3000", origins="zipcode"))
        assert captured["params"].get("origins") == "zipcode"

    async def test_geocode_no_origins_when_none(self, monkeypatch):
        captured = {}

        async def mock_request(path, params=None):
            captured["params"] = params
            return {"results": []}

        monkeypatch.setattr("swisstopo_mcp.geocoding.geo_admin_request", mock_request)
        await geocode(GeocodeInput(search_text="Bern"))
        # origins should not be in params when None
        assert "origins" not in captured["params"]

    async def test_geocode_empty_results(self, monkeypatch):
        async def mock_request(path, params=None):
            return {"results": []}

        monkeypatch.setattr("swisstopo_mcp.geocoding.geo_admin_request", mock_request)
        result = await geocode(GeocodeInput(search_text="xyznotfound"))
        assert "Keine" in result or "keine" in result.lower()

    async def test_geocode_api_error(self, monkeypatch):
        import httpx

        async def mock_request(path, params=None):
            resp = httpx.Response(500, request=httpx.Request("GET", "http://test"))
            raise httpx.HTTPStatusError("Server error", request=resp.request, response=resp)

        monkeypatch.setattr("swisstopo_mcp.geocoding.geo_admin_request", mock_request)
        result = await geocode(GeocodeInput(search_text="Bern"))
        assert "Fehler" in result

    async def test_geocode_passes_correct_params(self, monkeypatch):
        captured = {}

        async def mock_request(path, params=None):
            captured["path"] = path
            captured["params"] = params
            return {"results": []}

        monkeypatch.setattr("swisstopo_mcp.geocoding.geo_admin_request", mock_request)
        await geocode(GeocodeInput(search_text="Bern", limit=5, sr=2056))
        assert captured["params"]["type"] == "locations"
        assert captured["params"]["searchText"] == "Bern"
        assert captured["params"]["limit"] == 5
        assert captured["params"]["sr"] == 2056
        assert captured["params"]["returnGeometry"] == "true"


class TestReverseGeocodeHandler:
    async def test_reverse_geocode_mocked(self, monkeypatch):
        async def mock_request(path, params=None):
            return {
                "results": [
                    {
                        "attrs": {
                            "label": "Bahnhofstrasse 1, 8001 Zürich",
                            "lat": 47.3769,
                            "lon": 8.5417,
                            "origin": "address",
                            "detail": "Bahnhofstrasse 1 8001 Zürich",
                        }
                    }
                ]
            }

        monkeypatch.setattr("swisstopo_mcp.geocoding.geo_admin_request", mock_request)
        result = await reverse_geocode(ReverseGeocodeInput(lat=47.3769, lon=8.5417))
        assert "Zürich" in result or "Zurich" in result or "8001" in result

    async def test_reverse_geocode_empty_results(self, monkeypatch):
        async def mock_request(path, params=None):
            return {"results": []}

        monkeypatch.setattr("swisstopo_mcp.geocoding.geo_admin_request", mock_request)
        result = await reverse_geocode(ReverseGeocodeInput(lat=46.5, lon=6.5))
        assert "Keine" in result or "keine" in result.lower()

    async def test_reverse_geocode_bbox_params(self, monkeypatch):
        captured = {}

        async def mock_request(path, params=None):
            captured["params"] = params
            return {"results": []}

        monkeypatch.setattr("swisstopo_mcp.geocoding.geo_admin_request", mock_request)
        await reverse_geocode(ReverseGeocodeInput(lat=47.0, lon=8.0))
        p = captured["params"]
        assert p["type"] == "locations"
        assert p["origins"] == "address"
        # bbox should be set and contain the coordinates
        assert "bbox" in p
        bbox_str = p["bbox"]
        # bbox = lon-0.005, lat-0.005, lon+0.005, lat+0.005
        assert "7.995" in bbox_str
        assert "46.995" in bbox_str

    async def test_reverse_geocode_api_error(self, monkeypatch):
        import httpx

        async def mock_request(path, params=None):
            resp = httpx.Response(404, request=httpx.Request("GET", "http://test"))
            raise httpx.HTTPStatusError("Not found", request=resp.request, response=resp)

        monkeypatch.setattr("swisstopo_mcp.geocoding.geo_admin_request", mock_request)
        result = await reverse_geocode(ReverseGeocodeInput(lat=47.0, lon=8.0))
        assert "Fehler" in result


# ---------------------------------------------------------------------------
# Live Tests (network required)
# ---------------------------------------------------------------------------


@pytest.mark.live
async def test_live_geocode():
    result = await geocode(GeocodeInput(search_text="Bundesplatz Bern"))
    assert "Bern" in result or "bern" in result.lower()


@pytest.mark.live
async def test_live_geocode_with_origins():
    result = await geocode(GeocodeInput(search_text="3000", origins="zipcode"))
    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.live
async def test_live_reverse_geocode():
    # Bundesplatz Bern approximately
    result = await reverse_geocode(ReverseGeocodeInput(lat=46.9466, lon=7.4441))
    assert isinstance(result, str)
    assert len(result) > 0
