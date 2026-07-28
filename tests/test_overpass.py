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
    _classify_error,
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

    def test_classify_error_recognises_an_xml_error_page(self):
        # Fundstück: Overpass returns XML errors even for [out:json].
        err = _classify_error(XML_ERROR)
        assert err is not None
        assert "Abfrage" in err  # the parse-error classification

    def test_classify_error_none_for_json(self):
        assert _classify_error('{"elements": []}') is None


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
        assert "Abfrage" in r.summary  # parse-error classification
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
        assert "Zeitlimit" in r.summary  # classified, not echoed

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


# ---------------------------------------------------------------------------
# No upstream text reaches the user (audit OBS-002)
#
# The previous implementation returned `text.strip()[:300]` of any body
# containing "error", straight into the tool summary. A real Overpass error page
# echoes the submitted query and names server-side paths, so that handed the
# model both infrastructure detail and a channel a third party controls. These
# tests use a body shaped like the real thing.
# ---------------------------------------------------------------------------

REALISTIC_ERROR_PAGE = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    "<osm-derived><note>The data included in this document is from "
    "www.openstreetmap.org.</note>\n"
    '<html><body><p><strong style="color:#FF0000">Error</strong>: '
    "open64: 2 No such file or directory /opt/osm/db/overpass_db/nodes.bin . "
    "Dispatcher_Client::request_read_and_idx::rate_limited</p>\n"
    "<p>The output of your query:</p><pre>"
    "[out:json][timeout:25];(node[\"amenity\"=\"school\"](around:500,47.36,8.52););"
    "out center tags 50;</pre></body></html>"
)

LEAKED_FRAGMENTS = (
    "/opt/osm/db",
    "nodes.bin",
    "open64",
    "Dispatcher_Client",
    "around:500",
    "out center tags",
    "openstreetmap.org",
)


class TestNoUpstreamTextInSummary:
    async def _run(self, monkeypatch, body):
        async def fake_request(method, url, **kwargs):
            return httpx.Response(200, text=body)

        monkeypatch.setattr(overpass, "request_with_retry", fake_request)
        return await query_osm_features(
            QueryOsmFeaturesInput(feature_type="school", area="47.36,8.52")
        )

    async def test_error_page_body_never_reaches_the_summary(self, monkeypatch):
        r = await self._run(monkeypatch, REALISTIC_ERROR_PAGE)
        assert r.is_error
        for fragment in LEAKED_FRAGMENTS:
            assert fragment not in r.summary, f"upstream text leaked: {fragment!r}"

    async def test_error_page_is_still_classified_usefully(self, monkeypatch):
        """Masking must not turn into a useless message — the caller still
        learns it was rate-limited and can act on it."""
        r = await self._run(monkeypatch, REALISTIC_ERROR_PAGE)
        assert "Rate-Limiting" in r.summary

    async def test_body_is_logged_for_the_operator(self, monkeypatch):
        """Masking is only acceptable if the detail is still recoverable — an
        operator debugging a broken Overpass instance needs the body. Asserted
        against the logger rather than stderr: structlog binds the stream at
        configure time, so pytest's capture fixtures do not see it reliably."""
        recorded: list[tuple[str, dict]] = []

        class _Recorder:
            def warning(self, event, **kw):
                recorded.append((event, kw))

        monkeypatch.setattr(overpass, "_log", _Recorder())
        await self._run(monkeypatch, REALISTIC_ERROR_PAGE)

        assert recorded, "the error body was dropped instead of logged"
        event, kw = recorded[0]
        assert event == "overpass_error_page"
        assert "/opt/osm/db" in kw["body"], "the detail must survive in the log"

    async def test_summary_is_bounded(self, monkeypatch):
        """A body of pure junk cannot inflate the summary — the classification
        set is fixed, so length does not depend on upstream input."""
        r = await self._run(monkeypatch, "error " + ("X" * 50_000))
        assert len(r.summary) < 500

    async def test_remark_path_is_classified_too(self, monkeypatch):
        async def fake_request(method, url, **kwargs):
            return httpx.Response(
                200,
                json={
                    "elements": [],
                    "remark": (
                        "runtime error: Query run out of memory in "
                        '"recurse" at line 1 using about 2048 MB of RAM '
                        "(/opt/osm/db/overpass_db)"
                    ),
                },
            )

        monkeypatch.setattr(overpass, "request_with_retry", fake_request)
        r = await query_osm_features(
            QueryOsmFeaturesInput(feature_type="school", area="47.36,8.52")
        )
        assert r.is_error
        assert "/opt/osm/db" not in r.summary
        assert "2048 MB" not in r.summary
        assert "zu gross" in r.summary

    async def test_osm_errors_carry_the_odbl_licence(self, monkeypatch):
        """CH-004 on the same lines: an ODbL source must not be labelled with
        the swisstopo default."""
        r = await self._run(monkeypatch, REALISTIC_ERROR_PAGE)
        assert "ODbL" in r.license
