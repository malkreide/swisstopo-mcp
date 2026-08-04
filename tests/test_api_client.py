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

    def test_the_budget_timeout_reads_as_a_timeout_too(self):
        """`request_with_retry` bounds a call with `asyncio.timeout`, which
        raises the *builtin* `TimeoutError` — not an httpx exception. It fell
        through to "Unerwarteter interner Fehler", so the one wait this server
        promises to bound reported worse than an unbounded one, and a caller
        could not tell a slow upstream from a bug here.
        """
        result = handle_api_error(TimeoutError(), "Test")
        assert "Zeitüberschreitung" in result
        assert "Unerwarteter" not in result

    def test_connection_error(self):
        result = handle_api_error(httpx.ConnectError("fail"), "Test")
        assert "Verbindung" in result or "verbindung" in result.lower()

    def test_generic_error_is_masked(self):
        # OBS-002: unexpected errors must not leak raw exception text to the LLM.
        result = handle_api_error(RuntimeError("boom"), "Test")
        assert "boom" not in result
        assert "Unerwarteter interner Fehler" in result

    def test_value_error_message_preserved(self):
        # Intentional, user-facing validation errors keep their helpful message.
        result = handle_api_error(ValueError("Mindestens 2 Koordinatenpaare"), "Test")
        assert "Mindestens 2 Koordinatenpaare" in result


class TestEgressRefusalsDoNotDiscloseConfiguration:
    """OBS-002: a PermissionError used to be returned verbatim, which handed the
    model the complete ten-host egress allow-list or the internal address a name
    resolved to. The caller learns the request was refused; the detail is logged.
    """

    def test_allow_list_is_not_in_the_message(self):
        from swisstopo_mcp.api_client import ALLOWED_HOSTS, assert_host_allowed

        try:
            assert_host_allowed("https://evil.example.com/x")
        except PermissionError as exc:
            result = handle_api_error(exc, "Test")
        else:  # pragma: no cover - the guard must raise
            raise AssertionError("expected PermissionError")

        for host in ALLOWED_HOSTS:
            assert host not in result, f"egress allow-list disclosed: {host}"
        assert "evil.example.com" not in result
        assert "Egress-Richtlinie" in result

    def test_resolved_internal_address_is_not_in_the_message(self):
        exc = PermissionError(
            "Host 'x.example' löst auf eine interne Adresse auf (10.4.5.6). "
            "Blockiert (SSRF/DNS-Rebinding-Schutz)."
        )
        result = handle_api_error(exc, "Test")
        assert "10.4.5.6" not in result
        assert "x.example" not in result

    def test_detail_survives_in_the_log(self, monkeypatch):
        from swisstopo_mcp import api_client

        recorded: list[tuple[str, dict]] = []

        class _Recorder:
            def warning(self, event, **kw):
                recorded.append((event, kw))

        monkeypatch.setattr(api_client, "_log", _Recorder())
        handle_api_error(PermissionError("Host nicht auf der Egress-Allow-List: 'q'"), "Test")

        assert recorded, "the refusal detail was dropped instead of logged"
        event, kw = recorded[0]
        assert event == "egress_blocked"
        assert "Egress-Allow-List" in kw["detail"]


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
