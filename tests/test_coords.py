# tests/test_coords.py
"""Tests for the REFRAME coordinate-conversion tool."""

from __future__ import annotations

import httpx
import pytest
import respx
from pydantic import ValidationError

from swisstopo_mcp.api_client import ALLOWED_HOSTS, REFRAME_BASE, assert_host_allowed
from swisstopo_mcp.coords import (
    ConvertCoordinatesInput,
    _to_float,
    convert_coordinates,
    format_conversion,
)
from swisstopo_mcp.models import REFRAME_SOURCE, ToolResponse

# Reference point: Seilergraben 76, Zürich.
WGS84_LAT, WGS84_LON = 47.3769, 8.5417
LV95_E, LV95_N = 2683303.8872351027, 1247925.6157973814


# ---------------------------------------------------------------------------
# Input Validation
# ---------------------------------------------------------------------------


class TestConvertCoordinatesInput:
    def test_defaults_to_wgs84_to_lv95(self):
        m = ConvertCoordinatesInput(easting=WGS84_LON, northing=WGS84_LAT)
        assert m.direction == "wgs84_to_lv95"

    def test_accepts_lv95_input(self):
        m = ConvertCoordinatesInput(easting=LV95_E, northing=LV95_N, direction="lv95_to_wgs84")
        assert m.direction == "lv95_to_wgs84"

    def test_rejects_unknown_direction(self):
        with pytest.raises(ValidationError):
            ConvertCoordinatesInput(easting=8.5, northing=47.3, direction="lv03_to_wgs84")

    def test_rejects_extra_fields(self):
        with pytest.raises(ValidationError):
            ConvertCoordinatesInput(easting=8.5, northing=47.3, sr=2056)

    def test_rejects_lv95_values_in_wgs84_direction(self):
        """LV95 magnitudes with the WGS84 direction must fail, not silently convert."""
        with pytest.raises(ValidationError):
            ConvertCoordinatesInput(easting=LV95_E, northing=LV95_N, direction="wgs84_to_lv95")

    def test_rejects_wgs84_values_in_lv95_direction(self):
        with pytest.raises(ValidationError):
            ConvertCoordinatesInput(
                easting=WGS84_LON, northing=WGS84_LAT, direction="lv95_to_wgs84"
            )

    def test_rejects_swapped_axes(self):
        """lat as easting / lon as northing is out of range and must be rejected."""
        with pytest.raises(ValidationError):
            ConvertCoordinatesInput(
                easting=WGS84_LAT, northing=WGS84_LON, direction="wgs84_to_lv95"
            )

    def test_rejects_point_outside_switzerland(self):
        with pytest.raises(ValidationError):
            ConvertCoordinatesInput(easting=2.35, northing=48.85)  # Paris


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class TestToFloat:
    def test_coerces_string(self):
        """REFRAME returns numbers as JSON strings — the documented quirk."""
        assert _to_float("2683303.8872351027") == pytest.approx(2683303.8872351027)

    def test_strips_whitespace(self):
        assert _to_float("  1247925.6  ") == pytest.approx(1247925.6)

    def test_passes_through_float(self):
        assert _to_float(1.5) == 1.5

    def test_raises_on_garbage(self):
        with pytest.raises(ValueError):
            _to_float("nicht-numerisch")

    def test_raises_on_none(self):
        with pytest.raises(ValueError):
            _to_float(None)


class TestFormatConversion:
    def test_lv95_target_mentions_epsg(self):
        out = format_conversion(LV95_E, LV95_N, "wgs84_to_lv95")
        assert "LV95" in out and "2056" in out

    def test_wgs84_target_shows_lat_lon_order(self):
        out = format_conversion(WGS84_LON, WGS84_LAT, "lv95_to_wgs84")
        assert "WGS84" in out and "lat, lon" in out


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------


class TestConvertCoordinates:
    @respx.mock
    async def test_wgs84_to_lv95(self):
        respx.get(f"{REFRAME_BASE}/wgs84tolv95").mock(
            return_value=httpx.Response(200, json={"easting": str(LV95_E), "northing": str(LV95_N)})
        )
        out = await convert_coordinates(
            ConvertCoordinatesInput(easting=WGS84_LON, northing=WGS84_LAT)
        )
        assert isinstance(out, ToolResponse)
        assert out.is_error is False
        assert out.count == 1
        rec = out.results[0]
        assert rec["easting"] == pytest.approx(LV95_E)
        assert rec["northing"] == pytest.approx(LV95_N)
        assert rec["target_srid"] == 2056
        assert out.source == REFRAME_SOURCE

    @respx.mock
    async def test_lv95_to_wgs84_exposes_lat_lon(self):
        """The WGS84 result must also carry lat/lon so it feeds the other tools."""
        respx.get(f"{REFRAME_BASE}/lv95towgs84").mock(
            return_value=httpx.Response(
                200, json={"easting": str(WGS84_LON), "northing": str(WGS84_LAT)}
            )
        )
        out = await convert_coordinates(
            ConvertCoordinatesInput(easting=LV95_E, northing=LV95_N, direction="lv95_to_wgs84")
        )
        rec = out.results[0]
        assert rec["lat"] == pytest.approx(WGS84_LAT)
        assert rec["lon"] == pytest.approx(WGS84_LON)
        assert rec["target_srid"] == 4326

    @respx.mock
    async def test_missing_coordinates_is_handled_error(self):
        respx.get(f"{REFRAME_BASE}/wgs84tolv95").mock(
            return_value=httpx.Response(200, json={"unexpected": "payload"})
        )
        out = await convert_coordinates(
            ConvertCoordinatesInput(easting=WGS84_LON, northing=WGS84_LAT)
        )
        assert out.is_error is True
        assert out.count == 0

    @respx.mock
    async def test_non_numeric_payload_is_handled_error(self):
        respx.get(f"{REFRAME_BASE}/wgs84tolv95").mock(
            return_value=httpx.Response(200, json={"easting": "n/a", "northing": "n/a"})
        )
        out = await convert_coordinates(
            ConvertCoordinatesInput(easting=WGS84_LON, northing=WGS84_LAT)
        )
        assert out.is_error is True

    @respx.mock
    async def test_upstream_500_is_handled_error(self):
        respx.get(f"{REFRAME_BASE}/wgs84tolv95").mock(return_value=httpx.Response(500, text="boom"))
        out = await convert_coordinates(
            ConvertCoordinatesInput(easting=WGS84_LON, northing=WGS84_LAT)
        )
        assert out.is_error is True
        # Upstream detail must not leak into the user-facing summary (OBS-002).
        assert "boom" not in out.summary


# ---------------------------------------------------------------------------
# Egress
# ---------------------------------------------------------------------------


class TestReframeEgress:
    def test_reframe_host_is_allowed(self):
        assert "geodesy.geo.admin.ch" in ALLOWED_HOSTS
        assert_host_allowed(f"{REFRAME_BASE}/wgs84tolv95")

    def test_lookalike_host_rejected(self):
        with pytest.raises(PermissionError):
            assert_host_allowed("https://geodesy.geo.admin.ch.evil.com/reframe/wgs84tolv95")


# ---------------------------------------------------------------------------
# Live (skipped in CI)
# ---------------------------------------------------------------------------


@pytest.mark.live
class TestReframeLive:
    async def test_roundtrip_matches_input(self):
        """WGS84 -> LV95 -> WGS84 must return to the starting point."""
        fwd = await convert_coordinates(
            ConvertCoordinatesInput(easting=WGS84_LON, northing=WGS84_LAT)
        )
        assert fwd.is_error is False
        e, n = fwd.results[0]["easting"], fwd.results[0]["northing"]

        back = await convert_coordinates(
            ConvertCoordinatesInput(easting=e, northing=n, direction="lv95_to_wgs84")
        )
        assert back.is_error is False
        assert back.results[0]["lat"] == pytest.approx(WGS84_LAT, abs=1e-6)
        assert back.results[0]["lon"] == pytest.approx(WGS84_LON, abs=1e-6)

    async def test_polynomial_stays_within_a_metre_of_reframe(self):
        """Guards the decision to keep the local polynomial as the fast path.

        If this drifts beyond a metre the trade-off documented in coords.py and
        docs/merge-plan-swiss-geodata-mcp.md no longer holds.
        """
        from swisstopo_mcp.api_client import wgs84_to_lv95

        official = await convert_coordinates(
            ConvertCoordinatesInput(easting=WGS84_LON, northing=WGS84_LAT)
        )
        ref_e = official.results[0]["easting"]
        ref_n = official.results[0]["northing"]
        poly_e, poly_n = wgs84_to_lv95(WGS84_LAT, WGS84_LON)

        assert abs(poly_e - ref_e) < 1.0
        assert abs(poly_n - ref_n) < 1.0
