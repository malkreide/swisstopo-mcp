# tests/test_oereb.py
"""Tests for ÖREB Cadastre module (no live network calls)."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from swisstopo_mcp.config import settings
from swisstopo_mcp.models import OEREB_LICENSE, OEREB_SOURCE
from swisstopo_mcp.oereb import (
    OEREB_ENDPOINTS,
    GetEgridInput,
    GetOerebExtractInput,
    get_active_cantons,
    get_egrid,
    get_oereb_endpoint,
    get_oereb_extract,
)

# ---------------------------------------------------------------------------
# Canton Registry
# ---------------------------------------------------------------------------


class TestOerebEndpoints:
    def test_zh_present(self):
        assert "ZH" in OEREB_ENDPOINTS

    def test_be_present(self):
        assert "BE" in OEREB_ENDPOINTS

    def test_zh_url(self):
        assert OEREB_ENDPOINTS["ZH"].startswith("https://")

    def test_be_url(self):
        assert OEREB_ENDPOINTS["BE"].startswith("https://")

    def test_xx_not_present(self):
        assert "XX" not in OEREB_ENDPOINTS


class TestGetActiveCantons:
    def test_default_returns_zh_only(self, monkeypatch):
        monkeypatch.setattr(settings, "oereb_cantons", "ZH")
        result = get_active_cantons()
        assert "ZH" in result
        assert "BE" not in result

    def test_env_var_zh_only(self, monkeypatch):
        monkeypatch.setattr(settings, "oereb_cantons", "ZH")
        result = get_active_cantons()
        assert "ZH" in result
        assert "BE" not in result

    def test_env_var_be_only(self, monkeypatch):
        monkeypatch.setattr(settings, "oereb_cantons", "BE")
        result = get_active_cantons()
        assert "BE" in result
        assert "ZH" not in result

    def test_env_var_both(self, monkeypatch):
        monkeypatch.setattr(settings, "oereb_cantons", "ZH,BE")
        result = get_active_cantons()
        assert "ZH" in result
        assert "BE" in result

    def test_env_var_with_spaces(self, monkeypatch):
        monkeypatch.setattr(settings, "oereb_cantons", "ZH, BE")
        result = get_active_cantons()
        assert "ZH" in result
        assert "BE" in result

    def test_env_var_lowercase_normalized(self, monkeypatch):
        monkeypatch.setattr(settings, "oereb_cantons", "zh,be")
        result = get_active_cantons()
        assert "ZH" in result
        assert "BE" in result

    def test_unknown_canton_filtered_out(self, monkeypatch):
        monkeypatch.setattr(settings, "oereb_cantons", "XX")
        result = get_active_cantons()
        assert len(result) == 0

    def test_returns_dict(self, monkeypatch):
        monkeypatch.setattr(settings, "oereb_cantons", "ZH")
        result = get_active_cantons()
        assert isinstance(result, dict)


class TestGetOerebEndpoint:
    def test_zh_returns_url(self, monkeypatch):
        monkeypatch.setattr(settings, "oereb_cantons", "ZH,BE")
        result = get_oereb_endpoint("ZH")
        assert result is not None
        assert result.startswith("https://")

    def test_be_returns_url(self, monkeypatch):
        monkeypatch.setattr(settings, "oereb_cantons", "ZH,BE")
        result = get_oereb_endpoint("BE")
        assert result is not None

    def test_unknown_returns_none(self, monkeypatch):
        monkeypatch.setattr(settings, "oereb_cantons", "ZH")
        result = get_oereb_endpoint("XX")
        assert result is None

    def test_inactive_canton_returns_none(self, monkeypatch):
        monkeypatch.setattr(settings, "oereb_cantons", "ZH")
        result = get_oereb_endpoint("BE")
        assert result is None

    def test_lowercase_input_normalized(self, monkeypatch):
        monkeypatch.setattr(settings, "oereb_cantons", "ZH,BE")
        result = get_oereb_endpoint("zh")
        assert result is not None


# ---------------------------------------------------------------------------
# Input Model Validation
# ---------------------------------------------------------------------------


class TestGetEgridInput:
    def test_valid_input(self):
        m = GetEgridInput(lat=47.376, lon=8.541, canton="ZH")
        assert m.lat == pytest.approx(47.376)
        assert m.lon == pytest.approx(8.541)
        assert m.canton == "ZH"

    def test_canton_required(self):
        with pytest.raises(ValidationError):
            GetEgridInput(lat=47.376, lon=8.541)

    def test_lat_required(self):
        with pytest.raises(ValidationError):
            GetEgridInput(lon=8.541, canton="ZH")

    def test_lon_required(self):
        with pytest.raises(ValidationError):
            GetEgridInput(lat=47.376, canton="ZH")

    def test_lat_too_low(self):
        with pytest.raises(ValidationError):
            GetEgridInput(lat=45.7, lon=8.5, canton="ZH")

    def test_lat_too_high(self):
        with pytest.raises(ValidationError):
            GetEgridInput(lat=48.0, lon=8.5, canton="ZH")

    def test_lon_too_low(self):
        with pytest.raises(ValidationError):
            GetEgridInput(lat=47.0, lon=5.8, canton="ZH")

    def test_lon_too_high(self):
        with pytest.raises(ValidationError):
            GetEgridInput(lat=47.0, lon=10.6, canton="ZH")

    def test_canton_too_short(self):
        with pytest.raises(ValidationError):
            GetEgridInput(lat=47.0, lon=8.5, canton="Z")

    def test_canton_too_long(self):
        with pytest.raises(ValidationError):
            GetEgridInput(lat=47.0, lon=8.5, canton="ZHH")

    def test_canton_stripped(self):
        m = GetEgridInput(lat=47.0, lon=8.5, canton="ZH")
        assert m.canton == "ZH"

    def test_at_bounds(self):
        m = GetEgridInput(lat=45.8, lon=5.9, canton="BE")
        assert m.lat == 45.8
        m2 = GetEgridInput(lat=47.9, lon=10.5, canton="ZH")
        assert m2.lat == 47.9

    def test_extra_fields_forbidden(self):
        with pytest.raises(ValidationError):
            GetEgridInput(lat=47.0, lon=8.5, canton="ZH", extra="bad")


class TestGetOerebExtractInput:
    def test_valid_input(self):
        m = GetOerebExtractInput(egrid="CH767982496078", canton="ZH")
        assert m.egrid == "CH767982496078"
        assert m.canton == "ZH"
        assert m.lang == "de"
        assert m.topics is None

    def test_egrid_too_short(self):
        with pytest.raises(ValidationError):
            GetOerebExtractInput(egrid="CH12", canton="ZH")

    def test_egrid_required(self):
        with pytest.raises(ValidationError):
            GetOerebExtractInput(canton="ZH")

    def test_canton_required(self):
        with pytest.raises(ValidationError):
            GetOerebExtractInput(egrid="CH767982496078")

    def test_canton_too_short(self):
        with pytest.raises(ValidationError):
            GetOerebExtractInput(egrid="CH767982496078", canton="Z")

    def test_canton_too_long(self):
        with pytest.raises(ValidationError):
            GetOerebExtractInput(egrid="CH767982496078", canton="ZHH")

    def test_topics_optional(self):
        m = GetOerebExtractInput(egrid="CH767982496078", canton="ZH", topics="Nutzungsplanung")
        assert m.topics == "Nutzungsplanung"

    def test_lang_default_de(self):
        m = GetOerebExtractInput(egrid="CH767982496078", canton="ZH")
        assert m.lang == "de"

    def test_lang_custom(self):
        m = GetOerebExtractInput(egrid="CH767982496078", canton="ZH", lang="fr")
        assert m.lang == "fr"

    def test_extra_fields_forbidden(self):
        with pytest.raises(ValidationError):
            GetOerebExtractInput(egrid="CH767982496078", canton="ZH", foo="bar")


# ---------------------------------------------------------------------------
# Graceful Degradation (unsupported canton)
# ---------------------------------------------------------------------------


class TestUnsupportedCanton:
    async def test_get_egrid_unsupported_canton(self, monkeypatch):
        monkeypatch.setattr(settings, "oereb_cantons", "ZH")
        result = await get_egrid(GetEgridInput(lat=47.0, lon=8.5, canton="BE"))
        assert "BE" in result.summary
        assert "nicht unterstützt" in result.summary or "nicht" in result.summary
        assert "oereb.cadastre.ch" in result.summary

    async def test_get_egrid_unknown_canton(self, monkeypatch):
        monkeypatch.setattr(settings, "oereb_cantons", "ZH")
        result = await get_egrid(GetEgridInput(lat=47.0, lon=8.5, canton="XX"))
        assert "XX" in result.summary
        assert "oereb.cadastre.ch" in result.summary

    async def test_get_egrid_message_contains_available(self, monkeypatch):
        monkeypatch.setattr(settings, "oereb_cantons", "ZH,BE")
        # Use a canton not in registry at all
        result = await get_egrid(GetEgridInput(lat=47.0, lon=8.5, canton="XX"))
        # Should mention available cantons
        assert "ZH" in result.summary or "BE" in result.summary

    async def test_get_oereb_extract_unsupported_canton(self, monkeypatch):
        monkeypatch.setattr(settings, "oereb_cantons", "ZH")
        result = await get_oereb_extract(
            GetOerebExtractInput(egrid="CH767982496078", canton="BE")
        )
        assert "BE" in result.summary
        assert "nicht unterstützt" in result.summary or "nicht" in result.summary
        assert "oereb.cadastre.ch" in result.summary

    async def test_get_oereb_extract_unknown_canton(self, monkeypatch):
        monkeypatch.setattr(settings, "oereb_cantons", "ZH")
        result = await get_oereb_extract(
            GetOerebExtractInput(egrid="CH767982496078", canton="XX")
        )
        assert "XX" in result.summary
        assert "oereb.cadastre.ch" in result.summary


# ---------------------------------------------------------------------------
# Mocked HTTP Responses
# ---------------------------------------------------------------------------


class TestGetEgridHandler:
    async def test_returns_egrid_string(self, monkeypatch):
        monkeypatch.setattr(settings, "oereb_cantons", "ZH,BE")

        async def mock_get_client():
            class MockResponse:
                status_code = 200

                def raise_for_status(self):
                    pass

                def json(self):
                    return {
                        "features": [
                            {
                                "properties": {
                                    "egrid": "CH767982496078",
                                    "gemeindename": "Zürich",
                                }
                            }
                        ]
                    }

            class MockClient:
                async def get(self, url):
                    return MockResponse()

                async def __aenter__(self):
                    return self

                async def __aexit__(self, *args):
                    pass

            return MockClient()

        monkeypatch.setattr("swisstopo_mcp.oereb._get_client", mock_get_client)
        result = await get_egrid(GetEgridInput(lat=47.376, lon=8.541, canton="ZH"))
        assert "CH767982496078" in result.summary
        assert "Zürich" in result.summary

    async def test_no_features_returns_not_found(self, monkeypatch):
        monkeypatch.setattr(settings, "oereb_cantons", "ZH,BE")

        async def mock_get_client():
            class MockResponse:
                status_code = 200

                def raise_for_status(self):
                    pass

                def json(self):
                    return {"features": []}

            class MockClient:
                async def get(self, url):
                    return MockResponse()

                async def __aenter__(self):
                    return self

                async def __aexit__(self, *args):
                    pass

            return MockClient()

        monkeypatch.setattr("swisstopo_mcp.oereb._get_client", mock_get_client)
        result = await get_egrid(GetEgridInput(lat=47.376, lon=8.541, canton="ZH"))
        assert "gefunden" in result.summary.lower() or "kein" in result.summary.lower()

    async def test_uses_lv95_coordinates_in_url(self, monkeypatch):
        monkeypatch.setattr(settings, "oereb_cantons", "ZH,BE")
        captured_url = {}

        async def mock_get_client():
            class MockResponse:
                status_code = 200

                def raise_for_status(self):
                    pass

                def json(self):
                    return {"features": []}

            class MockClient:
                async def get(self, url):
                    captured_url["url"] = url
                    return MockResponse()

                async def __aenter__(self):
                    return self

                async def __aexit__(self, *args):
                    pass

            return MockClient()

        monkeypatch.setattr("swisstopo_mcp.oereb._get_client", mock_get_client)
        await get_egrid(GetEgridInput(lat=47.376, lon=8.541, canton="ZH"))
        # URL should contain EN= with LV95 coordinates (easting first)
        assert "EN=" in captured_url["url"]
        assert "/getegrid/json/" in captured_url["url"]

    async def test_http_error_returns_error_message(self, monkeypatch):
        import httpx

        monkeypatch.setattr(settings, "oereb_cantons", "ZH,BE")

        async def mock_get_client():
            class MockClient:
                async def get(self, url):
                    resp = httpx.Response(500, request=httpx.Request("GET", url))
                    raise httpx.HTTPStatusError("Server error", request=resp.request, response=resp)

                async def __aenter__(self):
                    return self

                async def __aexit__(self, *args):
                    pass

            return MockClient()

        monkeypatch.setattr("swisstopo_mcp.oereb._get_client", mock_get_client)
        result = await get_egrid(GetEgridInput(lat=47.376, lon=8.541, canton="ZH"))
        assert "Fehler" in result.summary

    async def test_timeout_returns_error_message(self, monkeypatch):
        import httpx

        monkeypatch.setattr(settings, "oereb_cantons", "ZH,BE")

        async def mock_get_client():
            class MockClient:
                async def get(self, url):
                    raise httpx.TimeoutException("timeout")

                async def __aenter__(self):
                    return self

                async def __aexit__(self, *args):
                    pass

            return MockClient()

        monkeypatch.setattr("swisstopo_mcp.oereb._get_client", mock_get_client)
        result = await get_egrid(GetEgridInput(lat=47.376, lon=8.541, canton="ZH"))
        assert "Fehler" in result.summary or "Zeitüberschreitung" in result.summary

    async def test_multiple_features_returned(self, monkeypatch):
        monkeypatch.setattr(settings, "oereb_cantons", "ZH,BE")

        async def mock_get_client():
            class MockResponse:
                status_code = 200

                def raise_for_status(self):
                    pass

                def json(self):
                    return {
                        "features": [
                            {"properties": {"egrid": "CH111", "gemeindename": "Zürich"}},
                            {"properties": {"egrid": "CH222", "gemeindename": "Zürich"}},
                        ]
                    }

            class MockClient:
                async def get(self, url):
                    return MockResponse()

                async def __aenter__(self):
                    return self

                async def __aexit__(self, *args):
                    pass

            return MockClient()

        monkeypatch.setattr("swisstopo_mcp.oereb._get_client", mock_get_client)
        result = await get_egrid(GetEgridInput(lat=47.376, lon=8.541, canton="ZH"))
        assert "CH111" in result.summary
        assert "CH222" in result.summary


class TestGetOerebExtractHandler:
    def _make_extract_response(self, topics=None):
        """Build a minimal ÖREB extract JSON response."""
        if topics is None:
            topics = []
        return {
            "GetExtractByIdResponse": {
                "RealEstate": {
                    "RestrictionOnLandownership": topics
                }
            }
        }

    def _make_restriction(self, topic="Nutzungsplanung", description="Wohnzone W2",
                          authority="Gemeinde Zürich", legal="Bau- und Zonenordnung"):
        return {
            "Topic": topic,
            "Information": [{"Text": description}],
            "ResponsibleOffice": {"Name": [{"Text": authority}]},
            "LegalProvisions": [{"Title": [{"Text": legal}]}],
        }

    async def test_returns_markdown_extract(self, monkeypatch):
        monkeypatch.setattr(settings, "oereb_cantons", "ZH,BE")
        restriction = self._make_restriction()
        response_data = self._make_extract_response([restriction])

        async def mock_get_client():
            class MockResponse:
                status_code = 200

                def raise_for_status(self):
                    pass

                def json(self):
                    return response_data

            class MockClient:
                async def get(self, url):
                    return MockResponse()

                async def __aenter__(self):
                    return self

                async def __aexit__(self, *args):
                    pass

            return MockClient()

        monkeypatch.setattr("swisstopo_mcp.oereb._get_client", mock_get_client)
        result = await get_oereb_extract(
            GetOerebExtractInput(egrid="CH767982496078", canton="ZH")
        )
        assert "## ÖREB-Auszug für CH767982496078" in result.summary
        assert "Nutzungsplanung" in result.summary
        assert "Wohnzone W2" in result.summary
        assert "Gemeinde Zürich" in result.summary

    async def test_no_restrictions_returns_empty_message(self, monkeypatch):
        monkeypatch.setattr(settings, "oereb_cantons", "ZH,BE")
        response_data = self._make_extract_response([])

        async def mock_get_client():
            class MockResponse:
                status_code = 200

                def raise_for_status(self):
                    pass

                def json(self):
                    return response_data

            class MockClient:
                async def get(self, url):
                    return MockResponse()

                async def __aenter__(self):
                    return self

                async def __aexit__(self, *args):
                    pass

            return MockClient()

        monkeypatch.setattr("swisstopo_mcp.oereb._get_client", mock_get_client)
        result = await get_oereb_extract(
            GetOerebExtractInput(egrid="CH767982496078", canton="ZH")
        )
        assert "Keine" in result.summary

    async def test_404_egrid_not_found(self, monkeypatch):
        import httpx

        monkeypatch.setattr(settings, "oereb_cantons", "ZH,BE")

        async def mock_get_client():
            class MockClient:
                async def get(self, url):
                    resp = httpx.Response(404, request=httpx.Request("GET", url))
                    # Don't raise — we handle 404 specially
                    return resp

                async def __aenter__(self):
                    return self

                async def __aexit__(self, *args):
                    pass

            return MockClient()

        monkeypatch.setattr("swisstopo_mcp.oereb._get_client", mock_get_client)
        # Valid EGRID format (alphanumeric) but non-existent -> upstream 404.
        result = await get_oereb_extract(
            GetOerebExtractInput(egrid="CH000000000000", canton="ZH")
        )
        assert "nicht gefunden" in result.summary or "CH000000000000" in result.summary

    async def test_topics_filter_added_to_url(self, monkeypatch):
        monkeypatch.setattr(settings, "oereb_cantons", "ZH,BE")
        captured_url = {}
        response_data = self._make_extract_response([])

        async def mock_get_client():
            class MockResponse:
                status_code = 200

                def raise_for_status(self):
                    pass

                def json(self):
                    return response_data

            class MockClient:
                async def get(self, url):
                    captured_url["url"] = url
                    return MockResponse()

                async def __aenter__(self):
                    return self

                async def __aexit__(self, *args):
                    pass

            return MockClient()

        monkeypatch.setattr("swisstopo_mcp.oereb._get_client", mock_get_client)
        await get_oereb_extract(
            GetOerebExtractInput(
                egrid="CH767982496078", canton="ZH", topics="Nutzungsplanung"
            )
        )
        assert "TOPICS=Nutzungsplanung" in captured_url["url"]

    async def test_no_topics_filter_absent_from_url(self, monkeypatch):
        monkeypatch.setattr(settings, "oereb_cantons", "ZH,BE")
        captured_url = {}
        response_data = self._make_extract_response([])

        async def mock_get_client():
            class MockResponse:
                status_code = 200

                def raise_for_status(self):
                    pass

                def json(self):
                    return response_data

            class MockClient:
                async def get(self, url):
                    captured_url["url"] = url
                    return MockResponse()

                async def __aenter__(self):
                    return self

                async def __aexit__(self, *args):
                    pass

            return MockClient()

        monkeypatch.setattr("swisstopo_mcp.oereb._get_client", mock_get_client)
        await get_oereb_extract(
            GetOerebExtractInput(egrid="CH767982496078", canton="ZH")
        )
        assert "TOPICS" not in captured_url["url"]

    async def test_lang_passed_in_url(self, monkeypatch):
        monkeypatch.setattr(settings, "oereb_cantons", "ZH,BE")
        captured_url = {}
        response_data = self._make_extract_response([])

        async def mock_get_client():
            class MockResponse:
                status_code = 200

                def raise_for_status(self):
                    pass

                def json(self):
                    return response_data

            class MockClient:
                async def get(self, url):
                    captured_url["url"] = url
                    return MockResponse()

                async def __aenter__(self):
                    return self

                async def __aexit__(self, *args):
                    pass

            return MockClient()

        monkeypatch.setattr("swisstopo_mcp.oereb._get_client", mock_get_client)
        await get_oereb_extract(
            GetOerebExtractInput(egrid="CH767982496078", canton="ZH", lang="fr")
        )
        assert "LANG=fr" in captured_url["url"]

    async def test_http_error_returns_error_message(self, monkeypatch):
        import httpx

        monkeypatch.setattr(settings, "oereb_cantons", "ZH,BE")

        async def mock_get_client():
            class MockClient:
                async def get(self, url):
                    resp = httpx.Response(500, request=httpx.Request("GET", url))
                    raise httpx.HTTPStatusError("Server error", request=resp.request, response=resp)

                async def __aenter__(self):
                    return self

                async def __aexit__(self, *args):
                    pass

            return MockClient()

        monkeypatch.setattr("swisstopo_mcp.oereb._get_client", mock_get_client)
        result = await get_oereb_extract(
            GetOerebExtractInput(egrid="CH767982496078", canton="ZH")
        )
        assert "Fehler" in result.summary

    async def test_grouped_by_topic(self, monkeypatch):
        monkeypatch.setattr(settings, "oereb_cantons", "ZH,BE")
        restrictions = [
            self._make_restriction(topic="Nutzungsplanung", description="Wohnzone"),
            self._make_restriction(topic="Waldabstand", description="Waldabstandslinie"),
        ]
        response_data = self._make_extract_response(restrictions)

        async def mock_get_client():
            class MockResponse:
                status_code = 200

                def raise_for_status(self):
                    pass

                def json(self):
                    return response_data

            class MockClient:
                async def get(self, url):
                    return MockResponse()

                async def __aenter__(self):
                    return self

                async def __aexit__(self, *args):
                    pass

            return MockClient()

        monkeypatch.setattr("swisstopo_mcp.oereb._get_client", mock_get_client)
        result = await get_oereb_extract(
            GetOerebExtractInput(egrid="CH767982496078", canton="ZH")
        )
        assert "### Nutzungsplanung" in result.summary
        assert "### Waldabstand" in result.summary
        assert "Wohnzone" in result.summary
        assert "Waldabstandslinie" in result.summary

    async def test_egrid_in_heading(self, monkeypatch):
        monkeypatch.setattr(settings, "oereb_cantons", "ZH,BE")
        response_data = self._make_extract_response([self._make_restriction()])

        async def mock_get_client():
            class MockResponse:
                status_code = 200

                def raise_for_status(self):
                    pass

                def json(self):
                    return response_data

            class MockClient:
                async def get(self, url):
                    return MockResponse()

                async def __aenter__(self):
                    return self

                async def __aexit__(self, *args):
                    pass

            return MockClient()

        monkeypatch.setattr("swisstopo_mcp.oereb._get_client", mock_get_client)
        result = await get_oereb_extract(
            GetOerebExtractInput(egrid="CH767982496078", canton="ZH")
        )
        assert "CH767982496078" in result.summary


# ---------------------------------------------------------------------------
# One-call aggregate (audit ARCH-007)
# ---------------------------------------------------------------------------

import httpx  # noqa: E402
import respx  # noqa: E402

from swisstopo_mcp.oereb import OerebAtInput, _first_egrid, oereb_at  # noqa: E402

_ZH = "https://oereb.geo.zh.ch"
_EGRID_PAYLOAD = {"features": [{"properties": {"egrid": "CH807306036483"}}]}


class TestFirstEgrid:
    def test_lowercase_key(self):
        assert _first_egrid([{"properties": {"egrid": "CH1"}}]) == "CH1"

    def test_uppercase_key(self):
        """Cantonal endpoints disagree on the casing."""
        assert _first_egrid([{"properties": {"EGRID": "CH2"}}]) == "CH2"

    def test_skips_features_without_an_egrid(self):
        assert _first_egrid([{"properties": {}}, {"properties": {"egrid": "CH3"}}]) == "CH3"

    def test_empty_gives_none(self):
        assert _first_egrid([]) is None


class TestOerebAt:
    @respx.mock
    async def test_resolves_egrid_and_returns_the_extract(self, monkeypatch):
        """The EGRID is an upstream identifier, not something the caller asked
        for — it must not require a second tool call (ARCH-007)."""
        monkeypatch.setattr(settings, "oereb_cantons", "ZH")
        egrid_route = respx.get(url__startswith=f"{_ZH}/getegrid/json/").mock(
            return_value=httpx.Response(200, json=_EGRID_PAYLOAD)
        )
        extract_route = respx.get(url__startswith=f"{_ZH}/extract/json/").mock(
            return_value=httpx.Response(200, json={"extract": {}})
        )
        out = await oereb_at(OerebAtInput(lat=47.3769, lon=8.5417, canton="ZH"))
        assert out.is_error is False
        assert egrid_route.called and extract_route.called
        # The resolved EGRID must reach the extract call.
        assert "CH807306036483" in str(extract_route.calls[0].request.url)

    @respx.mock
    async def test_no_parcel_is_a_soft_miss_with_a_hint(self, monkeypatch):
        monkeypatch.setattr(settings, "oereb_cantons", "ZH")
        respx.get(url__startswith=f"{_ZH}/getegrid/json/").mock(
            return_value=httpx.Response(200, json={"features": []})
        )
        out = await oereb_at(OerebAtInput(lat=47.3769, lon=8.5417, canton="ZH"))
        assert out.is_error is False
        assert out.match_type == "none"
        assert out.note and "municipality_at" in out.note

    async def test_unsupported_canton_is_reported(self, monkeypatch):
        monkeypatch.setattr(settings, "oereb_cantons", "ZH")
        out = await oereb_at(OerebAtInput(lat=47.3769, lon=8.5417, canton="GR"))
        assert out.is_error is True
        assert "GR" in out.summary

    @respx.mock
    async def test_upstream_failure_is_handled(self, monkeypatch):
        monkeypatch.setattr(settings, "oereb_cantons", "ZH")
        respx.get(url__startswith=f"{_ZH}/getegrid/json/").mock(
            return_value=httpx.Response(500, text="boom")
        )
        out = await oereb_at(OerebAtInput(lat=47.3769, lon=8.5417, canton="ZH"))
        assert out.is_error is True
        assert "boom" not in out.summary

    async def test_accepts_lv95_input(self, monkeypatch):
        monkeypatch.setattr(settings, "oereb_cantons", "ZH")
        m = OerebAtInput(easting=2683531.0, northing=1247914.0, canton="ZH")
        assert m.as_lv95 == (2683531.0, 1247914.0)


# ---------------------------------------------------------------------------
# Live tests (audit OPS-001)
#
# The nightly run had no coverage of this cluster at all, which is the sharpest
# gap it could have had: the cantonal ÖREB endpoints are the only per-canton,
# per-format upstream in this server, they are operated by cantons rather than
# by the Confederation, and their response shape is the thing most likely to
# change without notice. Everything else here talks to api3.geo.admin.ch.
#
# These are deliberately shallow. The job is contract drift — did the endpoint
# move, did the payload stop parsing — not correctness of a particular parcel.
# ---------------------------------------------------------------------------

# Zürich, Bederstrasse area. A point inside canton ZH, which is the one canton
# enabled by default.
ZH_LAT, ZH_LON = 47.360966, 8.525343


@pytest.mark.live
class TestOerebLive:
    async def test_get_egrid_resolves_a_zurich_point(self):
        result = await get_egrid(GetEgridInput(lat=ZH_LAT, lon=ZH_LON, canton="ZH"))
        assert result.is_error is False, result.summary
        # An empty answer is legitimate on a parcel boundary, so the contract
        # assertion is on the envelope, not on finding a parcel.
        assert result.source == OEREB_SOURCE
        assert result.match_type in {"exact", "none"}
        if result.results:
            egrid = result.results[0].get("egrid")
            assert isinstance(egrid, str) and egrid, "EGRID field shape changed"

    async def test_oereb_at_returns_one_call_answer(self):
        """The aggregate is the tool a caller should reach for; if the chain it
        collapses breaks upstream, this is where it shows."""
        result = await oereb_at(OerebAtInput(lat=ZH_LAT, lon=ZH_LON, canton="ZH"))
        assert result.is_error is False, result.summary
        assert result.source == OEREB_SOURCE
        assert result.license == OEREB_LICENSE
        assert result.match_type in {"exact", "none"}
        if result.match_type == "none":
            assert result.note, "an empty ÖREB answer must carry a next step"

    async def test_get_oereb_extract_accepts_a_resolved_egrid(self):
        """Chained on purpose: a hardcoded EGRID would rot, and resolving it
        first is also what exercises the pair the aggregate replaced."""
        located = await get_egrid(GetEgridInput(lat=ZH_LAT, lon=ZH_LON, canton="ZH"))
        if not located.results:
            pytest.skip("no parcel at the probe point today")
        egrid = located.results[0]["egrid"]
        result = await get_oereb_extract(GetOerebExtractInput(egrid=egrid, canton="ZH"))
        assert result.is_error is False, result.summary
        assert result.source == OEREB_SOURCE

    async def test_unsupported_canton_fails_cleanly(self):
        """Not an upstream call — but it pins the behaviour a caller hits almost
        everywhere in Switzerland, since only ZH is enabled by default."""
        result = await get_egrid(GetEgridInput(lat=46.95, lon=7.45, canton="XX"))
        assert result.is_error is True
        assert "ZH" in result.summary
