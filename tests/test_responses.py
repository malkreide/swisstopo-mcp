# tests/test_responses.py
"""Regression tests for SDK-002 + CH-004: structured ToolResponse envelope."""
from __future__ import annotations

import pytest

from swisstopo_mcp.geocoding import GeocodeInput, geocode
from swisstopo_mcp.height import HeightInput, get_height
from swisstopo_mcp.models import OEREB_SOURCE, SWISSTOPO_SOURCE, ToolResponse
from swisstopo_mcp.oereb import GetEgridInput, get_egrid


class TestToolResponseModel:
    def test_ok_sets_count_from_results(self):
        r = ToolResponse.ok("summary", [{"a": 1}, {"a": 2}], match_type="exact")
        assert r.count == 2
        assert r.is_error is False
        assert r.source == SWISSTOPO_SOURCE
        assert r.license and r.provenance == "live_api"
        assert r.retrieved_at  # populated

    def test_error_sets_flag_and_empty_results(self):
        r = ToolResponse.error("kaputt")
        assert r.is_error is True
        assert r.count == 0 and r.results == []

    def test_extra_fields_forbidden(self):
        with pytest.raises(Exception):
            ToolResponse(summary="x", bogus=1)  # type: ignore[call-arg]


class TestHandlerEnvelopes:
    async def test_geocode_populates_structured_results(self, monkeypatch):
        async def mock_request(path, params=None):
            return {"results": [{"attrs": {"label": "Bern", "lat": 46.9, "lon": 7.4}}]}

        monkeypatch.setattr("swisstopo_mcp.geocoding.geo_admin_request", mock_request)
        r = await geocode(GeocodeInput(search_text="Bern"))
        assert isinstance(r, ToolResponse)
        assert r.count == 1 and r.match_type == "exact"
        assert r.results[0]["attrs"]["label"] == "Bern"
        assert r.source == SWISSTOPO_SOURCE
        assert "Bern" in r.summary

    async def test_geocode_empty_is_match_none(self, monkeypatch):
        async def mock_request(path, params=None):
            return {"results": []}

        monkeypatch.setattr("swisstopo_mcp.geocoding.geo_admin_request", mock_request)
        r = await geocode(GeocodeInput(search_text="zzzznope"))
        assert r.count == 0 and r.match_type == "none" and r.is_error is False

    async def test_height_has_single_structured_record(self, monkeypatch):
        async def mock_request(path, params=None):
            return {"height": "553.6"}

        monkeypatch.setattr("swisstopo_mcp.height.geo_admin_request", mock_request)
        r = await get_height(HeightInput(lat=46.9481, lon=7.4474))
        assert r.count == 1
        assert r.results[0]["height"] == "553.6"

    async def test_oereb_unsupported_canton_is_error_with_oereb_source(self, monkeypatch):
        monkeypatch.setenv("SWISSTOPO_OEREB_CANTONS", "ZH")
        r = await get_egrid(GetEgridInput(lat=47.0, lon=8.5, canton="XX"))
        assert r.is_error is True
        assert r.source == OEREB_SOURCE
        assert "nicht unterstützt" in r.summary


class TestFastMCPStructuredOutput:
    async def test_tool_emits_structured_content_and_schema(self, monkeypatch):
        async def mock_request(path, params=None):
            return {"results": [{"attrs": {"label": "Bern", "lat": 46.9, "lon": 7.4}}]}

        monkeypatch.setattr("swisstopo_mcp.geocoding.geo_admin_request", mock_request)
        from swisstopo_mcp.server import mcp

        tools = {t.name: t for t in await mcp.list_tools()}
        assert tools["swisstopo_geocode"].outputSchema is not None

        _content, structured = await mcp.call_tool("swisstopo_geocode", {"params": {"search_text": "Bern"}})
        assert structured["source"] == SWISSTOPO_SOURCE
        assert structured["count"] == 1
        assert structured["match_type"] == "exact"
