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
        async def mock_request(path, params=None, **_):
            return {"results": [{"attrs": {"label": "Bern", "lat": 46.9, "lon": 7.4}}]}

        monkeypatch.setattr("swisstopo_mcp.geocoding.geo_admin_request", mock_request)
        r = await geocode(GeocodeInput(search_text="Bern"))
        assert isinstance(r, ToolResponse)
        assert r.count == 1 and r.match_type == "exact"
        assert r.results[0]["attrs"]["label"] == "Bern"
        assert r.source == SWISSTOPO_SOURCE
        assert "Bern" in r.summary

    async def test_geocode_empty_is_match_none(self, monkeypatch):
        async def mock_request(path, params=None, **_):
            return {"results": []}

        monkeypatch.setattr("swisstopo_mcp.geocoding.geo_admin_request", mock_request)
        r = await geocode(GeocodeInput(search_text="zzzznope"))
        assert r.count == 0 and r.match_type == "none" and r.is_error is False

    async def test_height_has_single_structured_record(self, monkeypatch):
        async def mock_request(path, params=None, **_):
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
        async def mock_request(path, params=None, **_):
            return {"results": [{"attrs": {"label": "Bern", "lat": 46.9, "lon": 7.4}}]}

        monkeypatch.setattr("swisstopo_mcp.geocoding.geo_admin_request", mock_request)
        from swisstopo_mcp.server import mcp

        tools = {t.name: t for t in await mcp.list_tools()}
        assert tools["swisstopo_geocode"].outputSchema is not None

        _content, structured = await mcp.call_tool("swisstopo_geocode", {"params": {"search_text": "Bern"}})
        assert structured["source"] == SWISSTOPO_SOURCE
        assert structured["count"] == 1
        assert structured["match_type"] == "exact"


class TestProtocolErrors:
    """OBS-001: protocol-level errors (bad tool / invalid params) are raised by
    the SDK rather than returned as a `ToolResponse`, which is what separates
    them from the structured `is_error` envelope used for handled execution
    errors. Note this exercises `call_tool` directly — over the wire mcp 1.28.1
    turns these into `isError` tool results, not JSON-RPC error objects, as a
    runtime probe in audit run `2026-07-27T162602-Z` showed."""

    async def test_invalid_params_raises(self):
        from swisstopo_mcp.server import mcp

        with pytest.raises(Exception):
            # search_text below min_length -> validation / -32602
            await mcp.call_tool("swisstopo_geocode", {"params": {"search_text": "x"}})

    async def test_unknown_tool_raises(self):
        from swisstopo_mcp.server import mcp

        with pytest.raises(Exception):
            await mcp.call_tool("does_not_exist", {})


# ---------------------------------------------------------------------------
# Source/licence coupling (audit CH-004)
#
# The licence was a separate parameter defaulting to the swisstopo value, and it
# drifted twice — 14 error call sites passed `source=` without `license=`, so
# ODbL OpenStreetMap data and the cantonal ÖREB terms went out labelled as Swiss
# OGD. Relabelling ODbL drops the share-alike obligation, so this is a licence
# misstatement rather than a missing field.
#
# The licence is now derived from the source. These tests hold the two halves
# that make that safe: the mapping is exhaustive over the declared sources, and
# no call site can pair a source with someone else's licence.
# ---------------------------------------------------------------------------


class TestSourceLicenceCoupling:
    @staticmethod
    def _declared_sources() -> dict[str, str]:
        from swisstopo_mcp import models

        return {
            name: getattr(models, name)
            for name in dir(models)
            if name.endswith("_SOURCE") and isinstance(getattr(models, name), str)
        }

    def test_every_declared_source_has_a_licence(self):
        from swisstopo_mcp.models import LICENSE_BY_SOURCE

        missing = {
            name: value
            for name, value in self._declared_sources().items()
            if value not in LICENSE_BY_SOURCE
        }
        assert not missing, (
            f"source constants with no licence mapping: {sorted(missing)}. "
            "Add them to LICENSE_BY_SOURCE — an unmapped source silently falls "
            "back to the swisstopo licence, which is the CH-004 defect."
        )

    @pytest.mark.parametrize("attr", sorted(_declared_sources.__func__()))
    def test_error_attributes_the_same_licence_as_ok(self, attr):
        """The error path is where the split-parameter design failed."""
        from swisstopo_mcp import models

        source = getattr(models, attr)
        assert (
            ToolResponse.error("x", source=source).license
            == ToolResponse.ok("x", source=source).license
        )

    def test_osm_errors_are_odbl_not_swiss_ogd(self):
        """The sharpest case, stated explicitly so it cannot regress quietly."""
        from swisstopo_mcp.models import OSM_SOURCE

        r = ToolResponse.error("Overpass down", source=OSM_SOURCE)
        assert "ODbL" in r.license
        assert "opendata.swiss" not in r.license

    def test_oereb_errors_carry_the_cantonal_terms(self):
        from swisstopo_mcp.models import OEREB_LICENSE

        assert ToolResponse.error("x", source=OEREB_SOURCE).license == OEREB_LICENSE

    def test_explicit_licence_still_wins(self):
        """Discovery tools legitimately describe a composite licence."""
        r = ToolResponse.ok("x", source=SWISSTOPO_SOURCE, license="gemischt")
        assert r.license == "gemischt"


class TestNoCallSitePairsTheWrongLicence:
    """An AST sweep over `src/`. Derivation protects the sites that omit the
    licence; this protects the ones that state it, which derivation cannot see.
    """

    # A literal licence string is allowed only where no single source applies.
    # Listing them here means adding one is a deliberate act, not a slip.
    ALLOWED_OVERRIDES = {"gemischt — siehe je Layer (Feld `license` pro Record)"}

    @staticmethod
    def _call_sites():
        import ast
        import pathlib

        from swisstopo_mcp import models

        src = pathlib.Path(models.__file__).parent
        for path in sorted(src.glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                if not (
                    isinstance(func, ast.Attribute)
                    and func.attr in ("ok", "error")
                    and isinstance(func.value, ast.Name)
                    and func.value.id == "ToolResponse"
                ):
                    continue
                kw = {k.arg: k.value for k in node.keywords if k.arg}
                yield path.name, node.lineno, kw.get("source"), kw.get("license")

    def test_stated_pairs_agree_with_the_mapping(self):
        import ast

        from swisstopo_mcp import models
        from swisstopo_mcp.models import LICENSE_BY_SOURCE

        mismatches = []
        for filename, lineno, source_node, license_node in self._call_sites():
            if source_node is None or license_node is None:
                continue  # derived — covered by the tests above
            if not (isinstance(source_node, ast.Name) and isinstance(license_node, ast.Name)):
                if isinstance(license_node, ast.Constant):
                    assert license_node.value in self.ALLOWED_OVERRIDES, (
                        f"{filename}:{lineno} states a literal licence "
                        f"{license_node.value!r} that is not a declared override"
                    )
                continue
            source = getattr(models, source_node.id, None)
            license_ = getattr(models, license_node.id, None)
            if source is None or license_ is None:
                continue
            expected = LICENSE_BY_SOURCE.get(source)
            if expected is not None and license_ != expected:
                mismatches.append(f"{filename}:{lineno} {source_node.id} + {license_node.id}")

        assert not mismatches, "call sites pairing a source with the wrong licence: " + "; ".join(
            mismatches
        )

    def test_the_sweep_actually_finds_call_sites(self):
        """A scanner that matches nothing passes vacuously — the failure mode
        the SEC-021 CI gate had."""
        sites = list(self._call_sites())
        assert len(sites) > 50, f"AST sweep found only {len(sites)} call sites"
        assert any(s is not None for _, _, s, _ in sites)


class TestLayerCatalogueCarriesPerRecordLicence:
    """The catalogue's envelope licence is necessarily composite, so the
    per-record licence is what a caller can actually act on (CH-004)."""

    async def test_each_record_names_its_own_licence(self, monkeypatch):
        from swisstopo_mcp import geodata
        from swisstopo_mcp.geodata import ListLayersInput, list_available_layers
        from swisstopo_mcp.models import GEODIENSTE_LICENSE, SWISSTOPO_LICENSE

        async def fake_catalog():
            return [
                {
                    "canton": "ZH",
                    "base_topic": "nutzungsplanung",
                    "topic_title": "Nutzungsplanung",
                    "wms": "Freier Zugriff",
                    "ogc_api": "Freier Zugriff",
                    "updated_at": "2026-01-01",
                }
            ]

        monkeypatch.setattr(geodata, "load_geodienste_catalog", fake_catalog)
        r = await list_available_layers(ListLayersInput())

        assert r.results, "no records to check"
        for record in r.results:
            assert record.get("license"), f"record without a licence: {record.get('layer')}"
        by_source = {rec["source"]: rec["license"] for rec in r.results}
        assert by_source.get("swisstopo") == SWISSTOPO_LICENSE
        if "geodienste" in by_source:
            assert by_source["geodienste"] == GEODIENSTE_LICENSE
