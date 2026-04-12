# tests/test_api_client.py
from __future__ import annotations

import httpx
import pytest

from swisstopo_mcp.api_client import (
    format_coordinates,
    handle_api_error,
    lv95_to_wgs84,
    parse_coordinate_string,
    validate_sr,
    wgs84_to_lv95,
)


class TestWgs84ToLv95:
    def test_bern_federal_palace(self):
        """Bern Bundesplatz: known reference point (~2m accuracy)."""
        e, n = wgs84_to_lv95(46.9481, 7.4474)
        # Actual LV95 of Bern Bundesplatz area: E≈2600670, N≈1199670
        assert abs(e - 2600670) < 500
        assert abs(n - 1199670) < 500

    def test_zurich_hb(self):
        """Zürich HB: approximate check."""
        e, n = wgs84_to_lv95(47.3769, 8.5417)
        assert 2680000 < e < 2690000
        assert 1245000 < n < 1255000

    def test_round_trip(self):
        """WGS84 → LV95 → WGS84 should be close to original."""
        lat_orig, lon_orig = 47.38, 8.54
        e, n = wgs84_to_lv95(lat_orig, lon_orig)
        lat_back, lon_back = lv95_to_wgs84(e, n)
        assert abs(lat_back - lat_orig) < 0.001
        assert abs(lon_back - lon_orig) < 0.001


class TestValidateSr:
    def test_valid_srs(self):
        for sr in (4326, 2056, 21781, 3857):
            assert validate_sr(sr) == sr

    def test_invalid_sr_raises(self):
        with pytest.raises(ValueError, match="Nicht unterstütztes Koordinatensystem"):
            validate_sr(9999)


class TestFormatCoordinates:
    def test_wgs84_format(self):
        result = format_coordinates(47.38, 8.54, 4326)
        assert "47.38" in result
        assert "8.54" in result
        assert "WGS84" in result

    def test_lv95_format(self):
        result = format_coordinates(2683000, 1248000, 2056)
        assert "LV95" in result


class TestHandleApiError:
    def test_404_error(self):
        request = httpx.Request("GET", "https://example.com")
        response = httpx.Response(404, request=request)
        error = httpx.HTTPStatusError("Not found", request=request, response=response)
        result = handle_api_error(error, "Test")
        assert "nicht gefunden" in result.lower()

    def test_timeout_error(self):
        result = handle_api_error(httpx.TimeoutException("timeout"), "Test")
        assert "Zeitüberschreitung" in result or "zeitüberschreitung" in result.lower()

    def test_connection_error(self):
        result = handle_api_error(httpx.ConnectError("fail"), "Test")
        assert "Verbindung" in result or "verbindung" in result.lower()

    def test_generic_error(self):
        result = handle_api_error(RuntimeError("boom"), "Test")
        assert "boom" in result


class TestParseCoordinateString:
    def test_two_points(self):
        pairs = parse_coordinate_string("47.38,8.54;47.39,8.55")
        assert len(pairs) == 2
        assert pairs[0] == (47.38, 8.54)

    def test_three_points(self):
        pairs = parse_coordinate_string("47.38,8.54;47.39,8.55;47.40,8.56")
        assert len(pairs) == 3

    def test_single_point_raises(self):
        with pytest.raises(ValueError, match="Mindestens 2"):
            parse_coordinate_string("47.38,8.54")

    def test_invalid_format_raises(self):
        with pytest.raises(ValueError):
            parse_coordinate_string("47.38;8.54")
