# tests/test_lv95_input.py
"""Tests for LV95 coordinate input on the point-based tools.

Covers the shared `SwissPointInput` contract and each tool that inherits it.
The reference point is Seilergraben 76, Zürich: WGS84 (47.3769, 8.5417) ==
LV95 (2683304, 1247926).
"""

from __future__ import annotations

import httpx
import pytest
import respx
from pydantic import ValidationError

from swisstopo_mcp.api_client import GEO_ADMIN_BASE
from swisstopo_mcp.coords import SwissPointInput, check_deprecated_sr
from swisstopo_mcp.height import HeightInput, get_height
from swisstopo_mcp.oereb import GetEgridInput
from swisstopo_mcp.rest_api import IdentifyInput, identify_features

LAT, LON = 47.3769, 8.5417
EAST, NORTH = 2683304.0, 1247926.0


# ---------------------------------------------------------------------------
# Shared contract
# ---------------------------------------------------------------------------


class TestSwissPointInput:
    def test_accepts_wgs84_pair(self):
        p = SwissPointInput(lat=LAT, lon=LON)
        assert p.as_wgs84 == (LAT, LON)

    def test_accepts_lv95_pair(self):
        p = SwissPointInput(easting=EAST, northing=NORTH)
        assert p.as_lv95 == (EAST, NORTH)

    def test_lv95_input_converts_to_wgs84(self):
        p = SwissPointInput(easting=EAST, northing=NORTH)
        lat, lon = p.as_wgs84
        assert lat == pytest.approx(LAT, abs=1e-3)
        assert lon == pytest.approx(LON, abs=1e-3)

    def test_wgs84_input_converts_to_lv95(self):
        p = SwissPointInput(lat=LAT, lon=LON)
        e, n = p.as_lv95
        assert e == pytest.approx(EAST, abs=1.0)
        assert n == pytest.approx(NORTH, abs=1.0)

    def test_roundtrip_is_stable(self):
        e, n = SwissPointInput(lat=LAT, lon=LON).as_lv95
        lat, lon = SwissPointInput(easting=e, northing=n).as_wgs84
        assert lat == pytest.approx(LAT, abs=1e-5)
        assert lon == pytest.approx(LON, abs=1e-5)

    def test_rejects_both_pairs(self):
        with pytest.raises(ValidationError, match="nicht beides"):
            SwissPointInput(lat=LAT, lon=LON, easting=EAST, northing=NORTH)

    def test_rejects_no_coordinates(self):
        with pytest.raises(ValidationError, match="Koordinaten fehlen"):
            SwissPointInput()

    def test_rejects_partial_wgs84(self):
        with pytest.raises(ValidationError, match="lat und lon"):
            SwissPointInput(lat=LAT)

    def test_rejects_partial_lv95(self):
        with pytest.raises(ValidationError, match="easting und northing"):
            SwissPointInput(easting=EAST)

    def test_rejects_degrees_in_lv95_fields(self):
        """The likely mistake: WGS84 degrees passed as easting/northing."""
        with pytest.raises(ValidationError, match="WGS84-Grad"):
            SwissPointInput(easting=LON, northing=LAT)

    def test_rejects_lv95_outside_switzerland(self):
        with pytest.raises(ValidationError, match="ausserhalb der Schweiz"):
            SwissPointInput(easting=1_000_000.0, northing=1_247_926.0)

    def test_rejects_wgs84_outside_switzerland(self):
        with pytest.raises(ValidationError):
            SwissPointInput(lat=48.85, lon=2.35)  # Paris


class TestCheckDeprecatedSr:
    def test_4326_passes(self):
        check_deprecated_sr(4326)

    def test_other_sr_raises_with_tool_specific_hint(self):
        with pytest.raises(ValueError, match="coordinate_system"):
            check_deprecated_sr(2056, alternative="coordinate_system='lv95'")


# ---------------------------------------------------------------------------
# Per-tool inheritance
# ---------------------------------------------------------------------------


class TestToolsAcceptLv95:
    def test_height_input(self):
        m = HeightInput(easting=EAST, northing=NORTH)
        assert m.as_lv95 == (EAST, NORTH)

    def test_identify_input(self):
        m = IdentifyInput(layers="ch.are.bauzonen", easting=EAST, northing=NORTH)
        assert m.as_lv95 == (EAST, NORTH)

    def test_egrid_input(self):
        m = GetEgridInput(easting=EAST, northing=NORTH, canton="ZH")
        assert m.as_lv95 == (EAST, NORTH)

    def test_identify_still_accepts_wgs84(self):
        """Backward compatibility: existing clients pass lat/lon."""
        m = IdentifyInput(layers="ch.are.bauzonen", lat=LAT, lon=LON)
        assert m.as_wgs84 == (LAT, LON)

    def test_identify_rejects_legacy_sr(self):
        with pytest.raises(ValidationError, match="easting/northing"):
            IdentifyInput(layers="ch.are.bauzonen", lat=LAT, lon=LON, sr=2056)


# ---------------------------------------------------------------------------
# Handlers send the right coordinates upstream
# ---------------------------------------------------------------------------


class TestHandlersUseLv95:
    @respx.mock
    async def test_height_sends_lv95_unchanged(self):
        """LV95 input must reach the upstream height API verbatim, not round-tripped."""
        route = respx.get(f"{GEO_ADMIN_BASE}/rest/services/height").mock(
            return_value=httpx.Response(200, json={"height": "408.7"})
        )
        out = await get_height(HeightInput(easting=EAST, northing=NORTH))
        assert out.is_error is False

        params = route.calls[0].request.url.params
        assert float(params["easting"]) == pytest.approx(EAST)
        assert float(params["northing"]) == pytest.approx(NORTH)
        assert params["sr"] == "2056"

    @respx.mock
    async def test_height_result_carries_both_systems(self):
        respx.get(f"{GEO_ADMIN_BASE}/rest/services/height").mock(
            return_value=httpx.Response(200, json={"height": "408.7"})
        )
        out = await get_height(HeightInput(lat=LAT, lon=LON))
        rec = out.results[0]
        assert rec["lat"] == pytest.approx(LAT)
        assert rec["easting"] == pytest.approx(EAST, abs=1.0)

    @respx.mock
    async def test_identify_converts_lv95_to_wgs84_for_upstream(self):
        """identify is called with sr=4326, so LV95 input must be converted."""
        route = respx.get(f"{GEO_ADMIN_BASE}/rest/services/ech/MapServer/identify").mock(
            return_value=httpx.Response(200, json={"results": []})
        )
        out = await identify_features(
            IdentifyInput(layers="ch.are.bauzonen", easting=EAST, northing=NORTH)
        )
        assert out.is_error is False

        params = route.calls[0].request.url.params
        assert params["sr"] == "4326"
        lon_str, lat_str = params["geometry"].split(",")
        assert float(lat_str) == pytest.approx(LAT, abs=1e-3)
        assert float(lon_str) == pytest.approx(LON, abs=1e-3)


class TestBaseModelConfigIsStrict:
    """Regression for audit SEC-018: the base class carried an empty config.

    Every concrete subclass re-declared it, so nothing shipped was permissive —
    but a subclass that forgot would have silently accepted extra fields.
    """

    def test_base_rejects_extra_fields(self):
        with pytest.raises(ValidationError):
            SwissPointInput(lat=LAT, lon=LON, bogus="x")

    def test_base_rejects_string_coercion(self):
        with pytest.raises(ValidationError):
            SwissPointInput(lat="47.0", lon="8.5")

    def test_subclass_without_own_config_stays_strict(self):
        class Derived(SwissPointInput):
            pass

        with pytest.raises(ValidationError):
            Derived(lat=LAT, lon=LON, bogus="x")
