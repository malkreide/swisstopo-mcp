# tests/test_geodata.py
"""Tests for the consolidated geodata façade (query_geodata + discovery)."""
from __future__ import annotations

import httpx
import pytest
from pydantic import ValidationError

from swisstopo_mcp import geodata
from swisstopo_mcp.geodata import (
    ListLayersInput,
    QueryGeodataInput,
    _bbox_from_point,
    _find_geodienste_entry,
    _is_free,
    list_available_layers,
    query_geodata,
)

# --- Sample catalogue entries (shape verified in Phase-1 live probe) ---
FREE_OGC = {
    "base_topic": "kataster_belasteter_standorte",
    "topic": "kataster_belasteter_standorte_v1_5",
    "topic_title": "Kataster der belasteten Standorte",
    "canton": "ZH",
    "contract_required_wms": False,
    "opendata_terms_wms": "Freie Nutzung",
    "ogc_api_features": ["https://geodienste.ch/db/kbs/deu/ogcapi"],
    "getcapabilities_wfs": ["https://geodienste.ch/db/kbs/deu?SERVICE=WFS"],
    "updated_at": "2025-01-01",
}
CONTRACT_ENTRY = {
    "base_topic": "rohrleitungsanlagen",
    "topic": "rohrleitungsanlagen",
    "topic_title": "Rohrleitungsanlagen",
    "canton": "ZH",
    "contract_required_wms": True,
    "opendata_terms_wms": "keine Angabe",
    "ogc_api_features": None,
}


class TestIsFree:
    def test_free_entry(self):
        assert _is_free(FREE_OGC, "wms") is True

    def test_contract_entry_not_free(self):
        assert _is_free(CONTRACT_ENTRY, "wms") is False

    def test_free_text_terms_not_boolean(self):
        # Fundstück: opendata_terms is free text, not a bool.
        e = {**FREE_OGC, "opendata_terms_wms": "Freie Nutzung. Quellenangabe ist Pflicht."}
        assert _is_free(e, "wms") is True
        e2 = {**FREE_OGC, "opendata_terms_wms": "keine Angabe"}
        assert _is_free(e2, "wms") is False


class TestBboxFromPoint:
    def test_bbox_ordering(self):
        min_lon, min_lat, max_lon, max_lat = _bbox_from_point(47.36, 8.52, 500)
        assert min_lon < 8.52 < max_lon
        assert min_lat < 47.36 < max_lat


class TestFindEntry:
    def test_match_by_base_topic_and_canton(self):
        cat = [FREE_OGC, CONTRACT_ENTRY]
        got = _find_geodienste_entry(cat, "kataster_belasteter_standorte", "zh")
        assert got is FREE_OGC

    def test_no_match(self):
        assert _find_geodienste_entry([FREE_OGC], "nope", "ZH") is None


class TestQueryGeodataInput:
    def test_valid_point(self):
        m = QueryGeodataInput(layer="strassenverzeichnis", point="47.36,8.52")
        assert m.radius_m == 150
        assert m.format == "summary"

    def test_bad_point_pattern(self):
        with pytest.raises(ValidationError):
            QueryGeodataInput(layer="strassenverzeichnis", point="not,a,point,x")

    def test_extra_forbidden(self):
        with pytest.raises(ValidationError):
            QueryGeodataInput(layer="x", foo="bar")

    def test_radius_bounds(self):
        with pytest.raises(ValidationError):
            QueryGeodataInput(layer="x", point="47.3,8.5", radius_m=99999)


class TestQueryGeodataDispatch:
    async def test_unknown_layer(self):
        r = await query_geodata(QueryGeodataInput(layer="does-not-exist", point="47.3,8.5"))
        assert r.is_error
        assert "list_available_layers" in r.summary

    async def test_streets_requires_location(self):
        r = await query_geodata(QueryGeodataInput(layer="strassenverzeichnis"))
        assert r.is_error

    async def test_streets_happy_path(self, monkeypatch):
        async def fake_request(path, params=None, **_):
            return {
                "results": [
                    {
                        "featureId": "1",
                        "attributes": {
                            "stn_label": "Bederstrasse",
                            "zip_label": "8002 Zürich",
                            "com_name": "Zürich",
                            "str_status": "bestehend",
                        },
                    },
                    {  # duplicate street name -> de-duplicated
                        "featureId": "2",
                        "attributes": {"stn_label": "Bederstrasse", "com_name": "Zürich"},
                    },
                ]
            }

        monkeypatch.setattr(geodata, "geo_admin_request", fake_request)
        r = await query_geodata(
            QueryGeodataInput(layer="strassenverzeichnis", point="47.360966,8.525343")
        )
        assert not r.is_error
        assert r.count == 1  # de-duplicated
        assert r.results[0]["street"] == "Bederstrasse"
        assert "swisstopo" in r.source.lower()

    async def test_oereb_availability_happy(self, monkeypatch):
        async def fake_request(path, params=None, **_):
            return {
                "results": [
                    {
                        "attributes": {
                            "gemeindename": "Zürich",
                            "kanton": "Zürich",
                            "bfs_nr": 261,
                            "oereb_status_de": "ÖREB-Kataster eingeführt",
                            "firmenname": "ARE ZH",
                            "email": "x@zh.ch",
                        }
                    }
                ]
            }

        monkeypatch.setattr(geodata, "geo_admin_request", fake_request)
        r = await query_geodata(
            QueryGeodataInput(layer="oereb-verfuegbarkeit", point="47.360966,8.525343")
        )
        assert not r.is_error
        assert r.count == 1
        assert "eingeführt" in r.summary
        assert r.results[0]["canton"] == "Zürich"

    async def test_geodienste_happy(self, monkeypatch):
        async def fake_catalog(force=False):
            return [FREE_OGC]

        async def fake_request(method, url, **kwargs):
            if url.endswith("/collections"):
                payload = {"collections": [{"id": "belastete_standorte_flaechen"}]}
            else:
                payload = {
                    "numberMatched": 42,
                    "features": [
                        {"properties": {"katasternummer": "ZH-1", "kanton": "ZH"}}
                    ],
                }
            return httpx.Response(200, json=payload)

        monkeypatch.setattr(geodata, "load_geodienste_catalog", fake_catalog)
        monkeypatch.setattr(geodata, "request_with_retry", fake_request)
        r = await query_geodata(
            QueryGeodataInput(
                layer="geodienste:kataster_belasteter_standorte:ZH",
                point="47.360966,8.525343",
                radius_m=1000,
            )
        )
        assert not r.is_error
        assert r.count == 1
        assert "geodienste" in r.source.lower()
        assert "Freie Nutzung" in r.license

    async def test_geodienste_contract_blocked(self, monkeypatch):
        async def fake_catalog(force=False):
            return [CONTRACT_ENTRY]

        monkeypatch.setattr(geodata, "load_geodienste_catalog", fake_catalog)
        r = await query_geodata(
            QueryGeodataInput(layer="geodienste:rohrleitungsanlagen:ZH", point="47.3,8.5")
        )
        assert r.is_error
        assert "frei" in r.summary.lower()

    async def test_geodienste_bad_layer_format(self):
        r = await query_geodata(
            QueryGeodataInput(layer="geodienste:onlytopic", point="47.3,8.5")
        )
        assert r.is_error
        assert "geodienste:" in r.summary


class TestListAvailableLayers:
    async def test_static_only_when_source_swisstopo(self):
        r = await list_available_layers(ListLayersInput(source="swisstopo"))
        assert not r.is_error
        assert any(rec["layer"] == "strassenverzeichnis" for rec in r.results)
        assert all(rec["source"] == "swisstopo" for rec in r.results)

    async def test_geodienste_canton_concrete_layers(self, monkeypatch):
        async def fake_catalog(force=False):
            return [FREE_OGC, CONTRACT_ENTRY]

        monkeypatch.setattr(geodata, "load_geodienste_catalog", fake_catalog)
        r = await list_available_layers(
            ListLayersInput(source="geodienste", canton="ZH", free_only=True)
        )
        assert not r.is_error
        layers = [rec["layer"] for rec in r.results]
        assert "geodienste:kataster_belasteter_standorte:ZH" in layers
        # contract-required topic excluded when free_only
        assert "geodienste:rohrleitungsanlagen:ZH" not in layers
        assert r.provenance == "cached"

    async def test_topic_overview_without_canton(self, monkeypatch):
        async def fake_catalog(force=False):
            return [FREE_OGC, {**FREE_OGC, "canton": "BE"}]

        monkeypatch.setattr(geodata, "load_geodienste_catalog", fake_catalog)
        r = await list_available_layers(ListLayersInput(source="geodienste"))
        assert not r.is_error
        # overview uses placeholder <KANTON>
        assert any("<KANTON>" in rec["layer"] for rec in r.results)


# ---------------------------------------------------------------------------
# Live tests (excluded from CI via `-m "not live"`)
# ---------------------------------------------------------------------------


@pytest.mark.live
async def test_live_streets_around_bederstrasse():
    r = await query_geodata(
        QueryGeodataInput(layer="strassenverzeichnis", point="47.360966,8.525343", radius_m=150)
    )
    assert not r.is_error
    assert r.count > 0


@pytest.mark.live
async def test_live_geodienste_zh_kbs():
    r = await query_geodata(
        QueryGeodataInput(
            layer="geodienste:kataster_belasteter_standorte:ZH",
            point="47.360966,8.525343",
            radius_m=1000,
            limit=2,
        )
    )
    assert not r.is_error


@pytest.mark.live
async def test_live_list_layers_zh():
    r = await list_available_layers(ListLayersInput(source="geodienste", canton="ZH"))
    assert r.count > 0


# ---------------------------------------------------------------------------
# Collection fan-out (audit ARCH-007)
#
# The loop over discovered geodienste collections was strictly sequential —
# the check's named anti-pattern for an aggregation tool. But it stopped as soon
# as it had `limit` records, often after one request, and a naive `gather` over
# every collection would have thrown that away: a single dataset can hold 24
# collections (measured against geodienste av_0), so all-at-once means 24
# requests against a cantonal service on every call.
#
# Waves keep the early exit and still cut the worst case. These tests hold all
# three properties — concurrency, the early exit, and the bound — because a fix
# that satisfied only the first would be worse than the defect.
# ---------------------------------------------------------------------------


class TestCollectionFanOut:
    @staticmethod
    def _catalog_entry():
        return {
            "canton": "ZH",
            "base_topic": "nutzungsplanung",
            "topic_title": "Nutzungsplanung",
            "wms": "Freier Zugriff",
            "opendata_terms_wms": "Freie Nutzung",
            "contract_required_wms": False,
            "ogc_api_features": ["https://geodienste.ch/db/np_0/deu/ogcapi"],
        }

    @staticmethod
    def _install(monkeypatch, collection_count, features_per_collection, recorder):
        """Fake the catalogue and the OGC API with `collection_count` collections."""
        import asyncio as _asyncio

        from swisstopo_mcp import geodata as gd

        async def fake_catalog(force=False):
            return [TestCollectionFanOut._catalog_entry()]

        class _Resp:
            def __init__(self, payload):
                self._payload = payload

            def json(self):
                return self._payload

        async def fake_request(method, url, **kwargs):
            if url.endswith("/collections"):
                return _Resp(
                    {"collections": [{"id": f"C{i}"} for i in range(collection_count)]}
                )
            cid = url.rsplit("/collections/", 1)[1].split("/")[0]
            recorder["order"].append(cid)
            recorder["in_flight"] += 1
            recorder["peak"] = max(recorder["peak"], recorder["in_flight"])
            try:
                await _asyncio.sleep(0.01)  # overlap window
            finally:
                recorder["in_flight"] -= 1
            n = features_per_collection.get(cid, 0)
            return _Resp(
                {
                    "numberMatched": n,
                    "features": [
                        {"properties": {"id": f"{cid}-{k}"}} for k in range(n)
                    ],
                }
            )

        monkeypatch.setattr(gd, "load_geodienste_catalog", fake_catalog)
        monkeypatch.setattr(gd, "request_with_retry", fake_request)

    @staticmethod
    def _recorder():
        return {"order": [], "in_flight": 0, "peak": 0}

    async def _run(self, monkeypatch, collection_count, features, limit=20):
        from swisstopo_mcp.geodata import QueryGeodataInput, query_geodata

        recorder = self._recorder()
        self._install(monkeypatch, collection_count, features, recorder)
        result = await query_geodata(
            QueryGeodataInput(
                layer="geodienste:nutzungsplanung:ZH",
                bbox="8.5,47.3,8.6,47.4",
                limit=limit,
            )
        )
        return result, recorder

    async def test_requests_actually_overlap(self, monkeypatch):
        """The point of the change: sequential means peak concurrency of 1."""
        _, rec = await self._run(monkeypatch, 8, {})
        assert rec["peak"] > 1, "collections were still fetched one at a time"

    async def test_concurrency_is_bounded(self, monkeypatch):
        """Unbounded fan-out against a cantonal service is the other failure."""
        from swisstopo_mcp.geodata import _COLLECTION_CONCURRENCY

        _, rec = await self._run(monkeypatch, 12, {})
        assert rec["peak"] <= _COLLECTION_CONCURRENCY

    async def test_the_early_exit_survives(self, monkeypatch):
        """If the first wave already fills `limit`, later collections must not
        be requested at all — that virtue of the sequential loop is why a naive
        gather would have been a regression."""
        from swisstopo_mcp.geodata import _COLLECTION_CONCURRENCY

        result, rec = await self._run(monkeypatch, 12, {"C0": 25}, limit=5)
        assert result.count == 5
        assert len(rec["order"]) <= _COLLECTION_CONCURRENCY, (
            f"queried {len(rec['order'])} collections after the first wave "
            "already satisfied the limit"
        )

    async def test_results_stay_deterministic(self, monkeypatch):
        """Concurrency must not make the record order depend on which upstream
        answered first."""
        features = {"C0": 1, "C1": 1, "C2": 1, "C3": 1}
        first, _ = await self._run(monkeypatch, 4, features)
        second, _ = await self._run(monkeypatch, 4, features)
        assert [r["collection"] for r in first.results] == [
            r["collection"] for r in second.results
        ]
        assert [r["collection"] for r in first.results] == ["C0", "C1", "C2", "C3"]

    async def test_the_scan_cap_is_not_silent(self, monkeypatch):
        """A cap nobody is told about reads as 'this is everything'."""
        from swisstopo_mcp.geodata import _MAX_COLLECTIONS_SCANNED

        result, rec = await self._run(
            monkeypatch, _MAX_COLLECTIONS_SCANNED + 8, {"C0": 1}, limit=50
        )
        assert len(rec["order"]) <= _MAX_COLLECTIONS_SCANNED
        assert result.note and "Collections" in result.note, (
            "the response does not say the scan was truncated"
        )

    async def test_no_truncation_note_when_everything_was_scanned(self, monkeypatch):
        result, _ = await self._run(monkeypatch, 3, {"C0": 1}, limit=50)
        assert result.note is None or "Collections" not in result.note
