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
        async def fake_request(path, params=None):
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
        async def fake_request(path, params=None):
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
