# tests/test_overpass.py
"""Tests for query_osm_features (Overpass). Focus on the fragile-source
behaviours found in the Phase-1 live probe: XML errors for [out:json],
timeout remarks in HTTP-200 bodies, graceful degradation."""
from __future__ import annotations

import httpx
import pytest
from pydantic import ValidationError

from swisstopo_mcp import overpass
from swisstopo_mcp.overpass import (
    FEATURE_TAGS,
    QueryOsmFeaturesInput,
    _build_query,
    _extract_error,
    _looks_like_point,
    query_osm_features,
)

XML_ERROR = (
    '<?xml version="1.0"?><html><body>'
    '<p><strong style="color:#FF0000">Error</strong>: line 1: parse error: '
    "']' expected - ';' found. </p></body></html>"
)


class TestInput:
    def test_valid(self):
        m = QueryOsmFeaturesInput(feature_type="school", area="47.36,8.52")
        assert m.radius_m == 500
        assert m.limit == 50

    def test_unknown_feature_type_rejected(self):
        with pytest.raises(ValidationError):
            QueryOsmFeaturesInput(feature_type="nuclear_reactor", area="47.36,8.52")

    def test_radius_cap(self):
        with pytest.raises(ValidationError):
            QueryOsmFeaturesInput(feature_type="school", area="47.36,8.52", radius_m=99999)

    def test_all_feature_types_have_tags(self):
        for ft in FEATURE_TAGS:
            m = QueryOsmFeaturesInput(feature_type=ft, area="47.36,8.52")
            assert FEATURE_TAGS[m.feature_type]


class TestHelpers:
    def test_looks_like_point(self):
        assert _looks_like_point("47.36,8.52")
        assert not _looks_like_point("Bederstrasse 109")

    def test_build_query_has_guards(self):
        q = _build_query('"amenity"="school"', 47.36, 8.52, 500, 50)
        assert "[out:json]" in q
        assert "[timeout:25]" in q
        assert "out center tags 50;" in q
        assert "around:500,47.36,8.52" in q

    def test_extract_error_from_xml(self):
        # Fundstück: Overpass returns XML errors even for [out:json].
        err = _extract_error(XML_ERROR)
        assert err is not None
        assert "parse error" in err

    def test_extract_error_none_for_json(self):
        assert _extract_error('{"elements": []}') is None


class TestQueryHandler:
    async def test_happy_path(self, monkeypatch):
        async def fake_geocode(*a, **k):  # not used (point given)
            raise AssertionError("should not geocode a point")

        async def fake_request(method, url, **kwargs):
            return httpx.Response(
                200,
                json={
                    "elements": [
                        {
                            "type": "node",
                            "id": 1,
                            "lat": 47.36,
                            "lon": 8.52,
                            "tags": {"name": "Schule Gabler", "amenity": "school"},
                        }
                    ]
                },
            )

        monkeypatch.setattr(overpass, "request_with_retry", fake_request)
        r = await query_osm_features(
            QueryOsmFeaturesInput(feature_type="school", area="47.360966,8.525343", radius_m=500)
        )
        assert not r.is_error
        assert r.count == 1
        assert r.results[0]["name"] == "Schule Gabler"
        assert "OpenStreetMap" in r.source
        assert "ODbL" in r.license

    async def test_xml_error_body_degrades(self, monkeypatch):
        async def fake_request(method, url, **kwargs):
            return httpx.Response(200, text=XML_ERROR)

        monkeypatch.setattr(overpass, "request_with_retry", fake_request)
        r = await query_osm_features(
            QueryOsmFeaturesInput(feature_type="school", area="47.36,8.52")
        )
        assert r.is_error
        assert "Overpass-Fehler" in r.summary
        assert "erneut versuchen" in r.summary  # graceful-degradation hint

    async def test_timeout_remark_degrades(self, monkeypatch):
        async def fake_request(method, url, **kwargs):
            return httpx.Response(
                200,
                json={"elements": [], "remark": "runtime error: Query timed out in 'query'"},
            )

        monkeypatch.setattr(overpass, "request_with_retry", fake_request)
        r = await query_osm_features(
            QueryOsmFeaturesInput(feature_type="school", area="47.36,8.52")
        )
        assert r.is_error
        assert "Laufzeitfehler" in r.summary

    async def test_network_failure_degrades(self, monkeypatch):
        async def fake_request(method, url, **kwargs):
            raise httpx.ConnectError("boom")

        monkeypatch.setattr(overpass, "request_with_retry", fake_request)
        r = await query_osm_features(
            QueryOsmFeaturesInput(feature_type="school", area="47.36,8.52")
        )
        assert r.is_error
        assert "erneut versuchen" in r.summary

    async def test_geocodes_place_name(self, monkeypatch):
        async def fake_geo(path, params=None):
            return {"results": [{"attrs": {"lat": 47.36, "lon": 8.52}}]}

        async def fake_request(method, url, **kwargs):
            return httpx.Response(200, json={"elements": []})

        monkeypatch.setattr(overpass, "geo_admin_request", fake_geo)
        monkeypatch.setattr(overpass, "request_with_retry", fake_request)
        r = await query_osm_features(
            QueryOsmFeaturesInput(feature_type="playground", area="Bederstrasse 109 Zürich")
        )
        assert not r.is_error
        assert "Keine 'playground'" in r.summary


@pytest.mark.live
async def test_live_schools_around_bederstrasse():
    r = await query_osm_features(
        QueryOsmFeaturesInput(feature_type="school", area="47.360966,8.525343", radius_m=500)
    )
    assert not r.is_error
    assert r.count >= 1
