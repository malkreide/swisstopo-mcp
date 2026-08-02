# tests/test_empty_results.py
"""Empty results always carry a next step (audit ARCH-003).

A bare negative is where an LLM either gives up or invents. The `note` field
existed but reached 5 of ~25 sites that can report `match_type: "none"`, and
nothing enforced it — so the coverage could regress silently, and did not grow
between two audit runs.

Three layers are asserted here, weakest to strongest:

1. the envelope guarantees *a* note whenever `match_type == "none"`;
2. an AST sweep proves every call site supplies its own, so the fallback is a
   safety net rather than the answer;
3. the tools most likely to legitimately return nothing are driven end to end
   and their notes checked for an actual next step.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

from swisstopo_mcp.models import FALLBACK_NOTE, ToolResponse


class TestEnvelopeInvariant:
    def test_none_without_a_note_gets_the_fallback(self):
        r = ToolResponse.ok("nichts gefunden", [], match_type="none")
        assert r.note == FALLBACK_NOTE

    def test_an_explicit_note_is_never_overwritten(self):
        r = ToolResponse.ok("nichts", [], match_type="none", note="mach X")
        assert r.note == "mach X"

    def test_non_empty_results_get_no_note(self):
        assert ToolResponse.ok("x", [{"a": 1}], match_type="exact").note is None

    def test_the_invariant_holds_after_direct_construction(self):
        """Not only via `ok()` — the validator is on the model, so a handler
        that builds a `ToolResponse` directly is covered too."""
        assert ToolResponse(summary="x", match_type="none").note == FALLBACK_NOTE


class TestEveryCallSiteSuppliesItsOwnNote:
    """The fallback is a floor. A site that relies on it is a site whose author
    did not think about what the caller should do next."""

    @staticmethod
    def _none_capable_sites():
        for path in sorted(pathlib.Path("src/swisstopo_mcp").glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                if not (
                    isinstance(func, ast.Attribute)
                    and func.attr == "ok"
                    and isinstance(func.value, ast.Name)
                    and func.value.id == "ToolResponse"
                ):
                    continue
                kwargs = {k.arg for k in node.keywords if k.arg}
                match_type = next((k.value for k in node.keywords if k.arg == "match_type"), None)
                if match_type is None:
                    continue
                if "none" in ast.unparse(match_type):
                    yield path.name, node.lineno, kwargs

    def test_the_sweep_finds_the_sites(self):
        """A sweep that matches nothing passes vacuously."""
        sites = list(self._none_capable_sites())
        assert len(sites) >= 20, f"only found {len(sites)} none-capable call sites"

    def test_no_site_relies_on_the_fallback(self):
        bare = [
            f"{name}:{line}"
            for name, line, kwargs in self._none_capable_sites()
            if "note" not in kwargs
        ]
        assert not bare, (
            "call sites that can report match_type='none' without their own note: "
            + ", ".join(bare)
            + ". The envelope fallback keeps these from being bare negatives, but "
            "a generic hint is not a next step — add one that names the tool or "
            "parameter to try."
        )


class TestFuzzyIsNoLongerADeadBranch:
    """`match_type: "fuzzy"` was a member of the Literal that no code produced.
    Geocoding is the main discovery entry point, so that is where relaxing a
    failed query pays."""

    @staticmethod
    async def _geocode(monkeypatch, responses):
        from swisstopo_mcp.geocoding import GeocodeInput, geocode

        calls: list[str] = []

        async def fake(path, params=None, **_):
            calls.append(params["searchText"])
            return responses.pop(0)

        monkeypatch.setattr("swisstopo_mcp.geocoding.geo_admin_request", fake)
        result = await geocode(GeocodeInput(search_text="Musterstrasse 999 Zürich"))
        return result, calls

    async def test_exact_hit_does_not_retry(self, monkeypatch):
        hit = {"results": [{"attrs": {"label": "Bern", "lat": 46.9, "lon": 7.4}}]}
        result, calls = await self._geocode(monkeypatch, [hit])
        assert result.match_type == "exact"
        assert len(calls) == 1, "an exact hit must not cost a second upstream call"
        assert result.note is None

    async def test_relaxed_hit_is_reported_as_fuzzy(self, monkeypatch):
        hit = {"results": [{"attrs": {"label": "Zürich", "lat": 47.3, "lon": 8.5}}]}
        result, calls = await self._geocode(monkeypatch, [{"results": []}, hit])
        assert result.match_type == "fuzzy"
        assert calls == ["Musterstrasse 999 Zürich", "Musterstrasse 999"]
        assert result.count == 1

    async def test_a_fuzzy_result_says_so(self, monkeypatch):
        """Silently returning a different query's answer would be worse than
        returning nothing."""
        hit = {"results": [{"attrs": {"label": "Zürich", "lat": 47.3, "lon": 8.5}}]}
        result, _ = await self._geocode(monkeypatch, [{"results": []}, hit])
        assert "Musterstrasse 999" in result.note
        assert "prüfen" in result.note

    async def test_both_empty_is_none_with_a_specific_note(self, monkeypatch):
        result, calls = await self._geocode(monkeypatch, [{"results": []}, {"results": []}])
        assert result.match_type == "none"
        assert len(calls) == 2
        assert result.note != FALLBACK_NOTE
        assert "swisstopo_search_address" in result.note

    async def test_single_token_query_is_not_retried(self, monkeypatch):
        from swisstopo_mcp.geocoding import GeocodeInput, geocode

        calls: list[str] = []

        async def fake(path, params=None, **_):
            calls.append(params["searchText"])
            return {"results": []}

        monkeypatch.setattr("swisstopo_mcp.geocoding.geo_admin_request", fake)
        result = await geocode(GeocodeInput(search_text="Zzzznope"))
        assert len(calls) == 1, "relaxing a one-token query repeats the same search"
        assert result.match_type == "none"


class TestRelaxQuery:
    @pytest.mark.parametrize(
        ("query", "expected"),
        [
            ("Musterstrasse 999 Zürich", "Musterstrasse 999"),
            ("Bahnhofstrasse 1, Zürich", "Bahnhofstrasse 1"),
            ("Bern", None),
            ("   ", None),
        ],
    )
    def test_relaxation(self, query, expected):
        from swisstopo_mcp.geocoding import _relax_query

        assert _relax_query(query) == expected


class TestTheToolsThatMostOftenReturnNothing:
    """The ÖREB cluster is the sharp case: only ZH is enabled by default, so an
    empty answer is the *normal* answer almost everywhere in Switzerland — and
    a bare negative there reads as 'no restrictions exist', which is a
    materially wrong statement about a legally binding cadastre."""

    async def test_oereb_unsupported_canton_names_a_next_step(self):
        from swisstopo_mcp.oereb import GetEgridInput, get_egrid

        r = await get_egrid(GetEgridInput(lat=47.0, lon=8.5, canton="XX"))
        assert r.is_error is True
        assert "ZH" in r.summary, "the caller must learn which cantons do work"

    async def test_oereb_no_egrid_points_at_municipality_at(self, monkeypatch):
        from swisstopo_mcp import oereb
        from swisstopo_mcp.oereb import GetEgridInput, get_egrid

        async def none_found(*a, **k):
            return []

        monkeypatch.setattr(oereb, "_fetch_egrid_records", none_found)
        r = await get_egrid(GetEgridInput(lat=47.37, lon=8.54, canton="ZH"))
        assert r.match_type == "none"
        assert r.note != FALLBACK_NOTE
        assert "swisstopo_municipality_at" in r.note

    async def test_zoning_outside_a_building_zone_explains_and_redirects(self, monkeypatch):
        from swisstopo_mcp.rest_api import ZoningAtInput, zoning_at

        async def empty(path, params=None, **_):
            return {"results": []}

        monkeypatch.setattr("swisstopo_mcp.rest_api.geo_admin_request", empty)
        r = await zoning_at(ZoningAtInput(lat=46.5, lon=7.5))
        assert r.match_type == "none"
        assert r.note != FALLBACK_NOTE
        assert "swisstopo_query_geodata" in r.note, (
            "the legally binding cantonal plan is the actual next step"
        )


# ---------------------------------------------------------------------------
# Error paths against the real upstream (audit ARCH-003, second half)
#
# ARCH-003 stopped one step short. An *empty* result must carry a next step and
# an AST sweep enforces it — but an error could not carry one at all, because
# `ToolResponse.error` had no `note` parameter. So a mistyped layer ID produced
# the bare string "Fehler bei Layer-Info: HTTP-Fehler 400.", while the same tool
# answering *nothing* would have explained where to look. An error is the more
# confusing of the two outcomes, not the less.
#
# These run live on purpose. What upstream does with a bad identifier is a
# contract like any other — api3 answers an unknown layer with 400 and an
# unknown feature with 404, and if that ever becomes a 200 carrying an error
# body, every one of these tools would report success on a failed lookup. No
# live test touched an error path before this.
# ---------------------------------------------------------------------------


@pytest.mark.live
class TestUpstreamErrorsCarryANextStep:
    async def test_unknown_layer_is_an_error_that_points_at_discovery(self):
        from swisstopo_mcp.rest_api import MapQueryInput, map_query

        r = await map_query(
            MapQueryInput(operation="layer_info", layer="ch.gibt.es.definitiv.nicht")
        )
        assert r.is_error is True, "an unknown layer must not read as success"
        assert r.note, "an error without a next step is where a caller gives up"
        assert "search_layers" in r.note

    async def test_unknown_feature_id_is_an_error_that_points_at_discovery(self):
        from swisstopo_mcp.rest_api import MapQueryInput, map_query

        r = await map_query(
            MapQueryInput(
                operation="feature_by_id",
                layer="ch.are.bauzonen",
                feature_id="99999999999",
            )
        )
        assert r.is_error is True
        assert r.note and "features_at_point" in r.note

    async def test_unknown_collection_is_an_error_that_points_at_discovery(self):
        from swisstopo_mcp.stac import GetCollectionInput, get_collection

        r = await get_collection(GetCollectionInput(collection_id="ch.gibt.es.nicht"))
        assert r.is_error is True
        assert r.note and "swisstopo_search_geodata" in r.note

    async def test_an_error_still_carries_source_and_licence(self):
        """The envelope guarantee that CH-004 established must survive the note
        being added — an error attributes the same source as a success."""
        from swisstopo_mcp.rest_api import MapQueryInput, map_query

        r = await map_query(MapQueryInput(operation="layer_info", layer="ch.nope.nope"))
        assert r.is_error is True
        assert r.source and r.license

    async def test_a_real_empty_result_is_not_reported_as_an_error(self):
        """The counterpart: a query that legitimately finds nothing must stay a
        soft miss. Confusing the two is what makes a caller retry a lookup that
        was answered correctly."""
        from swisstopo_mcp.stac import SearchGeodataInput, search_geodata

        r = await search_geodata(SearchGeodataInput(query="zzzqqqxyzzz"))
        assert r.is_error is False
        assert r.match_type == "none"
        assert r.note
