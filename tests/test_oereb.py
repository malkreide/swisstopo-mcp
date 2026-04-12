# tests/test_oereb.py
"""Tests for ÖREB Cadastre module (no live network calls)."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

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
        monkeypatch.delenv("SWISSTOPO_OEREB_CANTONS", raising=False)
        result = get_active_cantons()
        assert "ZH" in result
        assert "BE" not in result

    def test_env_var_zh_only(self, monkeypatch):
        monkeypatch.setenv("SWISSTOPO_OEREB_CANTONS", "ZH")
        result = get_active_cantons()
        assert "ZH" in result
        assert "BE" not in result

    def test_env_var_be_only(self, monkeypatch):
        monkeypatch.setenv("SWISSTOPO_OEREB_CANTONS", "BE")
        result = get_active_cantons()
        assert "BE" in result
        assert "ZH" not in result

    def test_env_var_both(self, monkeypatch):
        monkeypatch.setenv("SWISSTOPO_OEREB_CANTONS", "ZH,BE")
        result = get_active_cantons()
        assert "ZH" in result
        assert "BE" in result

    def test_env_var_with_spaces(self, monkeypatch):
        monkeypatch.setenv("SWISSTOPO_OEREB_CANTONS", "ZH, BE")
        result = get_active_cantons()
        assert "ZH" in result
        assert "BE" in result

    def test_env_var_lowercase_normalized(self, monkeypatch):
        monkeypatch.setenv("SWISSTOPO_OEREB_CANTONS", "zh,be")
        result = get_active_cantons()
        assert "ZH" in result
        assert "BE" in result

    def test_unknown_canton_filtered_out(self, monkeypatch):
        monkeypatch.setenv("SWISSTOPO_OEREB_CANTONS", "XX")
        result = get_active_cantons()
        assert len(result) == 0

    def test_returns_dict(self, monkeypatch):
        monkeypatch.delenv("SWISSTOPO_OEREB_CANTONS", raising=False)
        result = get_active_cantons()
        assert isinstance(result, dict)


class TestGetOerebEndpoint:
    def test_zh_returns_url(self, monkeypatch):
        monkeypatch.setenv("SWISSTOPO_OEREB_CANTONS", "ZH,BE")
        result = get_oereb_endpoint("ZH")
        assert result is not None
        assert result.startswith("https://")

    def test_be_returns_url(self, monkeypatch):
        monkeypatch.setenv("SWISSTOPO_OEREB_CANTONS", "ZH,BE")
        result = get_oereb_endpoint("BE")
        assert result is not None

    def test_unknown_returns_none(self, monkeypatch):
        monkeypatch.delenv("SWISSTOPO_OEREB_CANTONS", raising=False)
        result = get_oereb_endpoint("XX")
        assert result is None

    def test_inactive_canton_returns_none(self, monkeypatch):
        monkeypatch.setenv("SWISSTOPO_OEREB_CANTONS", "ZH")
        result = get_oereb_endpoint("BE")
        assert result is None

    def test_lowercase_input_normalized(self, monkeypatch):
        monkeypatch.setenv("SWISSTOPO_OEREB_CANTONS", "ZH,BE")
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
        monkeypatch.setenv("SWISSTOPO_OEREB_CANTONS", "ZH")
        result = await get_egrid(GetEgridInput(lat=47.0, lon=8.5, canton="BE"))
        assert "BE" in result
        assert "nicht unterstützt" in result or "nicht" in result
        assert "oereb.cadastre.ch" in result

    async def test_get_egrid_unknown_canton(self, monkeypatch):
        monkeypatch.setenv("SWISSTOPO_OEREB_CANTONS", "ZH")
        result = await get_egrid(GetEgridInput(lat=47.0, lon=8.5, canton="XX"))
        assert "XX" in result
        assert "oereb.cadastre.ch" in result

    async def test_get_egrid_message_contains_available(self, monkeypatch):
        monkeypatch.setenv("SWISSTOPO_OEREB_CANTONS", "ZH,BE")
        # Use a canton not in registry at all
        result = await get_egrid(GetEgridInput(lat=47.0, lon=8.5, canton="XX"))
        # Should mention available cantons
        assert "ZH" in result or "BE" in result

    async def test_get_oereb_extract_unsupported_canton(self, monkeypatch):
        monkeypatch.setenv("SWISSTOPO_OEREB_CANTONS", "ZH")
        result = await get_oereb_extract(
            GetOerebExtractInput(egrid="CH767982496078", canton="BE")
        )
        assert "BE" in result
        assert "nicht unterstützt" in result or "nicht" in result
        assert "oereb.cadastre.ch" in result

    async def test_get_oereb_extract_unknown_canton(self, monkeypatch):
        monkeypatch.setenv("SWISSTOPO_OEREB_CANTONS", "ZH")
        result = await get_oereb_extract(
            GetOerebExtractInput(egrid="CH767982496078", canton="XX")
        )
        assert "XX" in result
        assert "oereb.cadastre.ch" in result


# ---------------------------------------------------------------------------
# Mocked HTTP Responses
# ---------------------------------------------------------------------------


class TestGetEgridHandler:
    async def test_returns_egrid_string(self, monkeypatch):
        monkeypatch.setenv("SWISSTOPO_OEREB_CANTONS", "ZH,BE")

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
        assert "CH767982496078" in result
        assert "Zürich" in result

    async def test_no_features_returns_not_found(self, monkeypatch):
        monkeypatch.setenv("SWISSTOPO_OEREB_CANTONS", "ZH,BE")

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
        assert "gefunden" in result.lower() or "kein" in result.lower()

    async def test_uses_lv95_coordinates_in_url(self, monkeypatch):
        monkeypatch.setenv("SWISSTOPO_OEREB_CANTONS", "ZH,BE")
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

        monkeypatch.setenv("SWISSTOPO_OEREB_CANTONS", "ZH,BE")

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
        assert "Fehler" in result

    async def test_timeout_returns_error_message(self, monkeypatch):
        import httpx

        monkeypatch.setenv("SWISSTOPO_OEREB_CANTONS", "ZH,BE")

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
        assert "Fehler" in result or "Zeitüberschreitung" in result

    async def test_multiple_features_returned(self, monkeypatch):
        monkeypatch.setenv("SWISSTOPO_OEREB_CANTONS", "ZH,BE")

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
        assert "CH111" in result
        assert "CH222" in result


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
        monkeypatch.setenv("SWISSTOPO_OEREB_CANTONS", "ZH,BE")
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
        assert "## ÖREB-Auszug für CH767982496078" in result
        assert "Nutzungsplanung" in result
        assert "Wohnzone W2" in result
        assert "Gemeinde Zürich" in result

    async def test_no_restrictions_returns_empty_message(self, monkeypatch):
        monkeypatch.setenv("SWISSTOPO_OEREB_CANTONS", "ZH,BE")
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
        assert "Keine" in result

    async def test_404_egrid_not_found(self, monkeypatch):
        import httpx

        monkeypatch.setenv("SWISSTOPO_OEREB_CANTONS", "ZH,BE")

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
        result = await get_oereb_extract(
            GetOerebExtractInput(egrid="INVALID_EGRID", canton="ZH")
        )
        assert "nicht gefunden" in result or "INVALID_EGRID" in result

    async def test_topics_filter_added_to_url(self, monkeypatch):
        monkeypatch.setenv("SWISSTOPO_OEREB_CANTONS", "ZH,BE")
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
        monkeypatch.setenv("SWISSTOPO_OEREB_CANTONS", "ZH,BE")
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
        monkeypatch.setenv("SWISSTOPO_OEREB_CANTONS", "ZH,BE")
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

        monkeypatch.setenv("SWISSTOPO_OEREB_CANTONS", "ZH,BE")

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
        assert "Fehler" in result

    async def test_grouped_by_topic(self, monkeypatch):
        monkeypatch.setenv("SWISSTOPO_OEREB_CANTONS", "ZH,BE")
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
        assert "### Nutzungsplanung" in result
        assert "### Waldabstand" in result
        assert "Wohnzone" in result
        assert "Waldabstandslinie" in result

    async def test_egrid_in_heading(self, monkeypatch):
        monkeypatch.setenv("SWISSTOPO_OEREB_CANTONS", "ZH,BE")
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
        assert "CH767982496078" in result
