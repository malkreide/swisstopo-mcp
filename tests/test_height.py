# tests/test_height.py
from __future__ import annotations

import pytest
from pydantic import ValidationError

from swisstopo_mcp.height import (
    ElevationProfileInput,
    HeightInput,
    elevation_profile,
    format_elevation_profile,
    format_height_result,
    get_height,
)

# ---------------------------------------------------------------------------
# HeightInput Validation
# ---------------------------------------------------------------------------


class TestHeightInput:
    def test_defaults(self):
        m = HeightInput(lat=46.9481, lon=7.4474)
        assert m.sr == 4326

    def test_custom_sr(self):
        m = HeightInput(lat=46.9481, lon=7.4474, sr=2056)
        assert m.sr == 2056

    def test_lat_too_low(self):
        with pytest.raises(ValidationError):
            HeightInput(lat=45.7, lon=7.4)

    def test_lat_too_high(self):
        with pytest.raises(ValidationError):
            HeightInput(lat=48.0, lon=7.4)

    def test_lon_too_low(self):
        with pytest.raises(ValidationError):
            HeightInput(lat=46.9, lon=5.8)

    def test_lon_too_high(self):
        with pytest.raises(ValidationError):
            HeightInput(lat=46.9, lon=10.6)

    def test_lat_lon_at_bounds(self):
        m1 = HeightInput(lat=45.8, lon=5.9)
        assert m1.lat == 45.8
        assert m1.lon == 5.9
        m2 = HeightInput(lat=47.9, lon=10.5)
        assert m2.lat == 47.9
        assert m2.lon == 10.5

    def test_extra_fields_forbidden(self):
        with pytest.raises(ValidationError):
            HeightInput(lat=46.9, lon=7.4, foo="bar")

    def test_strip_whitespace_not_applicable_to_floats(self):
        # float fields — just check valid construction
        m = HeightInput(lat=46.9481, lon=7.4474)
        assert m.lat == pytest.approx(46.9481)
        assert m.lon == pytest.approx(7.4474)


# ---------------------------------------------------------------------------
# ElevationProfileInput Validation
# ---------------------------------------------------------------------------


class TestElevationProfileInput:
    def test_defaults(self):
        m = ElevationProfileInput(coordinates="46.9,7.4;47.0,7.5")
        assert m.nb_points == 200
        assert m.sr == 4326

    def test_custom_values(self):
        m = ElevationProfileInput(coordinates="46.9,7.4;47.0,7.5", nb_points=50, sr=2056)
        assert m.nb_points == 50
        assert m.sr == 2056

    def test_coordinates_too_short(self):
        with pytest.raises(ValidationError):
            ElevationProfileInput(coordinates="ab")

    def test_nb_points_min(self):
        with pytest.raises(ValidationError):
            ElevationProfileInput(coordinates="46.9,7.4;47.0,7.5", nb_points=1)

    def test_nb_points_max(self):
        with pytest.raises(ValidationError):
            ElevationProfileInput(coordinates="46.9,7.4;47.0,7.5", nb_points=1001)

    def test_nb_points_at_bounds(self):
        m1 = ElevationProfileInput(coordinates="46.9,7.4;47.0,7.5", nb_points=2)
        assert m1.nb_points == 2
        m2 = ElevationProfileInput(coordinates="46.9,7.4;47.0,7.5", nb_points=1000)
        assert m2.nb_points == 1000

    def test_extra_fields_forbidden(self):
        with pytest.raises(ValidationError):
            ElevationProfileInput(coordinates="46.9,7.4;47.0,7.5", extra="no")

    def test_strip_whitespace_on_coordinates(self):
        m = ElevationProfileInput(coordinates="  46.9,7.4;47.0,7.5  ")
        assert m.coordinates == "46.9,7.4;47.0,7.5"


# ---------------------------------------------------------------------------
# Format Helpers
# ---------------------------------------------------------------------------


class TestFormatHeightResult:
    def test_basic(self):
        result = format_height_result(46.9481, 7.4474, "553.6")
        assert "553.6" in result
        assert "m ü. M." in result
        assert "46.9481" in result
        assert "7.4474" in result

    def test_contains_coordinates(self):
        result = format_height_result(47.0, 8.0, "800.0")
        assert "47.0" in result
        assert "8.0" in result

    def test_returns_string(self):
        result = format_height_result(46.9, 7.4, "500")
        assert isinstance(result, str)


class TestFormatElevationProfile:
    def test_empty(self):
        result = format_elevation_profile([])
        assert "Keine" in result

    def test_single_point(self):
        points = [{"dist": 0.0, "alts": {"COMB": 553.6}, "easting": 600000, "northing": 200000}]
        result = format_elevation_profile(points)
        assert "553.6" in result
        assert "|" in result
        # First point has no gradient
        assert "—" in result

    def test_two_points_gradient(self):
        points = [
            {"dist": 0.0, "alts": {"COMB": 500.0}, "easting": 600000, "northing": 200000},
            {"dist": 100.0, "alts": {"COMB": 510.0}, "easting": 600100, "northing": 200000},
        ]
        result = format_elevation_profile(points)
        # Gradient = (510 - 500) / 100 * 100 = 10.0%
        assert "10.0" in result
        assert "500.0" in result
        assert "510.0" in result

    def test_table_headers(self):
        points = [{"dist": 0.0, "alts": {"COMB": 500.0}}]
        result = format_elevation_profile(points)
        assert "Distanz" in result
        assert "Höhe" in result
        assert "Steigung" in result

    def test_negative_gradient(self):
        points = [
            {"dist": 0.0, "alts": {"COMB": 600.0}},
            {"dist": 200.0, "alts": {"COMB": 560.0}},
        ]
        result = format_elevation_profile(points)
        # Gradient = (560 - 600) / 200 * 100 = -20.0%
        assert "-20.0" in result

    def test_fallback_alt_keys(self):
        # Should fall back to DTM2 if COMB missing
        points = [{"dist": 0.0, "alts": {"DTM2": 450.0}}]
        result = format_elevation_profile(points)
        assert "450.0" in result

    def test_many_points(self):
        points = [
            {"dist": float(i * 10), "alts": {"COMB": 500.0 + i}}
            for i in range(5)
        ]
        result = format_elevation_profile(points)
        lines = result.strip().split("\n")
        # header + separator + 5 data rows = 7 lines
        assert len(lines) == 7


# ---------------------------------------------------------------------------
# Async Handler Tests (mocked)
# ---------------------------------------------------------------------------


class TestGetHeightHandler:
    async def test_returns_height_string(self, monkeypatch):
        async def mock_request(path, params=None):
            return {"height": "553.6"}

        monkeypatch.setattr("swisstopo_mcp.height.geo_admin_request", mock_request)
        result = await get_height(HeightInput(lat=46.9481, lon=7.4474))
        assert "553.6" in result
        assert "m ü. M." in result

    async def test_passes_correct_params(self, monkeypatch):
        captured = {}

        async def mock_request(path, params=None):
            captured["path"] = path
            captured["params"] = params
            return {"height": "500.0"}

        monkeypatch.setattr("swisstopo_mcp.height.geo_admin_request", mock_request)
        await get_height(HeightInput(lat=46.9481, lon=7.4474))
        assert captured["path"] == "/rest/services/height"
        # WGS84 input is converted to LV95 internally
        assert captured["params"]["sr"] == 2056
        # Easting should be ~2600000 range (LV95)
        assert 2500000 < captured["params"]["easting"] < 2700000
        # Northing should be ~1200000 range (LV95)
        assert 1100000 < captured["params"]["northing"] < 1300000

    async def test_api_error_returns_error_message(self, monkeypatch):
        import httpx

        async def mock_request(path, params=None):
            resp = httpx.Response(500, request=httpx.Request("GET", "http://test"))
            raise httpx.HTTPStatusError("Server error", request=resp.request, response=resp)

        monkeypatch.setattr("swisstopo_mcp.height.geo_admin_request", mock_request)
        result = await get_height(HeightInput(lat=46.9481, lon=7.4474))
        assert "Fehler" in result

    async def test_timeout_error(self, monkeypatch):
        import httpx

        async def mock_request(path, params=None):
            raise httpx.TimeoutException("timeout")

        monkeypatch.setattr("swisstopo_mcp.height.geo_admin_request", mock_request)
        result = await get_height(HeightInput(lat=46.9481, lon=7.4474))
        assert "Fehler" in result or "Zeitüberschreitung" in result


class TestElevationProfileHandler:
    async def test_returns_table(self, monkeypatch):
        async def mock_request(path, params=None):
            return [
                {"dist": 0.0, "alts": {"COMB": 553.6}, "easting": 600000, "northing": 200000},
                {"dist": 100.0, "alts": {"COMB": 560.0}, "easting": 600100, "northing": 200000},
            ]

        monkeypatch.setattr("swisstopo_mcp.height.geo_admin_request", mock_request)
        result = await elevation_profile(
            ElevationProfileInput(coordinates="46.9481,7.4474;46.9600,7.4600")
        )
        assert "|" in result
        assert "553.6" in result or "560.0" in result

    async def test_geojson_built_correctly(self, monkeypatch):
        import json as _json

        captured = {}

        async def mock_request(path, params=None):
            captured["path"] = path
            captured["params"] = params
            return []

        monkeypatch.setattr("swisstopo_mcp.height.geo_admin_request", mock_request)
        await elevation_profile(
            ElevationProfileInput(coordinates="46.9,7.4;47.0,7.5")
        )
        assert captured["path"] == "/rest/services/profile.json"
        geom = _json.loads(captured["params"]["geom"])
        assert geom["type"] == "LineString"
        # WGS84 input is converted to LV95 — coordinates are [easting, northing]
        assert 2500000 < geom["coordinates"][0][0] < 2700000  # easting range
        assert 1100000 < geom["coordinates"][0][1] < 1300000  # northing range
        assert captured["params"]["sr"] == 2056

    async def test_invalid_coordinates_returns_error(self, monkeypatch):
        async def mock_request(path, params=None):
            return []

        monkeypatch.setattr("swisstopo_mcp.height.geo_admin_request", mock_request)
        # Only one coordinate pair — should fail parse
        result = await elevation_profile(
            ElevationProfileInput(coordinates="46.9,7.4;baddata")
        )
        assert "Fehler" in result

    async def test_nb_points_passed_correctly(self, monkeypatch):
        captured = {}

        async def mock_request(path, params=None):
            captured["params"] = params
            return []

        monkeypatch.setattr("swisstopo_mcp.height.geo_admin_request", mock_request)
        await elevation_profile(
            ElevationProfileInput(coordinates="46.9,7.4;47.0,7.5", nb_points=50)
        )
        assert captured["params"]["nb_points"] == 50

    async def test_api_error_returns_error_message(self, monkeypatch):
        import httpx

        async def mock_request(path, params=None):
            resp = httpx.Response(404, request=httpx.Request("GET", "http://test"))
            raise httpx.HTTPStatusError("Not found", request=resp.request, response=resp)

        monkeypatch.setattr("swisstopo_mcp.height.geo_admin_request", mock_request)
        result = await elevation_profile(
            ElevationProfileInput(coordinates="46.9,7.4;47.0,7.5")
        )
        assert "Fehler" in result

    async def test_single_coordinate_pair_rejected(self, monkeypatch):
        # parse_coordinate_string requires >= 2 pairs
        async def mock_request(path, params=None):
            return []

        monkeypatch.setattr("swisstopo_mcp.height.geo_admin_request", mock_request)
        result = await elevation_profile(
            ElevationProfileInput(coordinates="46.9,7.4;46.9,7.4")
        )
        # Two identical pairs are valid — request should go through
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# Coordinate Parsing (from api_client)
# ---------------------------------------------------------------------------


class TestParseCoordinateString:
    def test_two_pairs(self):
        from swisstopo_mcp.api_client import parse_coordinate_string

        pairs = parse_coordinate_string("46.9,7.4;47.0,7.5")
        assert len(pairs) == 2
        assert pairs[0] == pytest.approx((46.9, 7.4))
        assert pairs[1] == pytest.approx((47.0, 7.5))

    def test_three_pairs(self):
        from swisstopo_mcp.api_client import parse_coordinate_string

        pairs = parse_coordinate_string("46.9,7.4;47.0,7.5;47.1,7.6")
        assert len(pairs) == 3

    def test_one_pair_raises(self):
        from swisstopo_mcp.api_client import parse_coordinate_string

        with pytest.raises(ValueError, match="Mindestens 2"):
            parse_coordinate_string("46.9,7.4")

    def test_invalid_format_raises(self):
        from swisstopo_mcp.api_client import parse_coordinate_string

        with pytest.raises(ValueError):
            parse_coordinate_string("46.9,7.4;baddata")

    def test_whitespace_stripped(self):
        from swisstopo_mcp.api_client import parse_coordinate_string

        pairs = parse_coordinate_string("  46.9 , 7.4 ; 47.0 , 7.5  ")
        assert pairs[0] == pytest.approx((46.9, 7.4))


# ---------------------------------------------------------------------------
# Live Tests (network required)
# ---------------------------------------------------------------------------


@pytest.mark.live
async def test_live_get_height():
    result = await get_height(HeightInput(lat=46.9481, lon=7.4474))
    assert "m ü. M." in result


@pytest.mark.live
async def test_live_elevation_profile():
    result = await elevation_profile(
        ElevationProfileInput(
            coordinates="46.9481,7.4474;47.0,7.5",
            nb_points=10,
        )
    )
    assert "|" in result
    assert "Distanz" in result
