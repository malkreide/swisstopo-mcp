# tests/test_stac.py
from __future__ import annotations

import pytest
from pydantic import ValidationError

from swisstopo_mcp.stac import (
    GetCollectionInput,
    SearchGeodataInput,
    format_collection_card,
    format_collection_detail,
    format_search_results,
    get_collection,
    search_geodata,
)


# ---------------------------------------------------------------------------
# Input Model Validation: SearchGeodataInput
# ---------------------------------------------------------------------------


class TestSearchGeodataInput:
    def test_defaults(self):
        m = SearchGeodataInput(query="swissALTI3D")
        assert m.query == "swissALTI3D"
        assert m.limit == 10

    def test_custom_limit(self):
        m = SearchGeodataInput(query="Orthofoto", limit=5)
        assert m.limit == 5

    def test_strip_whitespace(self):
        m = SearchGeodataInput(query="  swissALTI3D  ")
        assert m.query == "swissALTI3D"

    def test_query_too_short(self):
        with pytest.raises(ValidationError):
            SearchGeodataInput(query="")

    def test_query_too_long(self):
        with pytest.raises(ValidationError):
            SearchGeodataInput(query="x" * 201)

    def test_query_exactly_one_char(self):
        m = SearchGeodataInput(query="a")
        assert m.query == "a"

    def test_query_exactly_200_chars(self):
        m = SearchGeodataInput(query="a" * 200)
        assert len(m.query) == 200

    def test_limit_too_low(self):
        with pytest.raises(ValidationError):
            SearchGeodataInput(query="test", limit=0)

    def test_limit_too_high(self):
        with pytest.raises(ValidationError):
            SearchGeodataInput(query="test", limit=51)

    def test_limit_at_bounds(self):
        m1 = SearchGeodataInput(query="test", limit=1)
        assert m1.limit == 1
        m2 = SearchGeodataInput(query="test", limit=50)
        assert m2.limit == 50

    def test_extra_fields_forbidden(self):
        with pytest.raises(ValidationError):
            SearchGeodataInput(query="test", foo="bar")


# ---------------------------------------------------------------------------
# Input Model Validation: GetCollectionInput
# ---------------------------------------------------------------------------


class TestGetCollectionInput:
    def test_basic(self):
        m = GetCollectionInput(collection_id="ch.swisstopo.swissalti3d")
        assert m.collection_id == "ch.swisstopo.swissalti3d"

    def test_strip_whitespace(self):
        m = GetCollectionInput(collection_id="  ch.swisstopo.swissalti3d  ")
        assert m.collection_id == "ch.swisstopo.swissalti3d"

    def test_too_short(self):
        with pytest.raises(ValidationError):
            GetCollectionInput(collection_id="x")

    def test_exactly_two_chars(self):
        m = GetCollectionInput(collection_id="ab")
        assert m.collection_id == "ab"

    def test_extra_fields_forbidden(self):
        with pytest.raises(ValidationError):
            GetCollectionInput(collection_id="ch.swisstopo.test", foo="bar")


# ---------------------------------------------------------------------------
# Format Helpers
# ---------------------------------------------------------------------------


SAMPLE_COLLECTION = {
    "id": "ch.swisstopo.swissalti3d",
    "title": "swissALTI3D",
    "description": "Hochpräzises digitales Höhenmodell der Schweiz.",
    "license": "proprietary",
    "extent": {
        "spatial": {"bbox": [[5.96, 45.82, 10.49, 47.81]]},
        "temporal": {"interval": [["2000-01-01T00:00:00Z", None]]},
    },
    "links": [
        {"rel": "self", "href": "https://data.geo.admin.ch/api/stac/v0.9/collections/ch.swisstopo.swissalti3d"},
        {"rel": "items", "href": "https://data.geo.admin.ch/api/stac/v0.9/collections/ch.swisstopo.swissalti3d/items", "title": "Items"},
        {"rel": "enclosure", "href": "https://example.com/download.zip", "title": "Download ZIP"},
    ],
}


class TestFormatCollectionCard:
    def test_contains_title(self):
        card = format_collection_card(SAMPLE_COLLECTION)
        assert "swissALTI3D" in card

    def test_contains_id(self):
        card = format_collection_card(SAMPLE_COLLECTION)
        assert "ch.swisstopo.swissalti3d" in card

    def test_contains_description(self):
        card = format_collection_card(SAMPLE_COLLECTION)
        assert "Höhenmodell" in card

    def test_contains_separator(self):
        card = format_collection_card(SAMPLE_COLLECTION)
        assert "---" in card

    def test_heading_format(self):
        card = format_collection_card(SAMPLE_COLLECTION)
        assert card.startswith("### ")

    def test_long_description_truncated(self):
        col = dict(SAMPLE_COLLECTION)
        col["description"] = "x" * 400
        card = format_collection_card(col)
        assert len(card) < 600
        assert "..." in card

    def test_missing_title_falls_back_to_id(self):
        col = {"id": "ch.test.id"}
        card = format_collection_card(col)
        assert "ch.test.id" in card

    def test_missing_description_handled(self):
        col = {"id": "ch.test.id", "title": "Test"}
        card = format_collection_card(col)
        assert isinstance(card, str)


class TestFormatCollectionDetail:
    def test_contains_title_as_heading(self):
        detail = format_collection_detail(SAMPLE_COLLECTION)
        assert "# swissALTI3D" in detail

    def test_contains_id(self):
        detail = format_collection_detail(SAMPLE_COLLECTION)
        assert "ch.swisstopo.swissalti3d" in detail

    def test_contains_license(self):
        detail = format_collection_detail(SAMPLE_COLLECTION)
        assert "proprietary" in detail

    def test_contains_description(self):
        detail = format_collection_detail(SAMPLE_COLLECTION)
        assert "Höhenmodell" in detail

    def test_contains_spatial_extent(self):
        detail = format_collection_detail(SAMPLE_COLLECTION)
        assert "5.96" in detail or "45.82" in detail

    def test_contains_temporal_extent(self):
        detail = format_collection_detail(SAMPLE_COLLECTION)
        assert "2000" in detail

    def test_temporal_end_shows_aktuell_when_none(self):
        detail = format_collection_detail(SAMPLE_COLLECTION)
        assert "aktuell" in detail

    def test_contains_download_links(self):
        detail = format_collection_detail(SAMPLE_COLLECTION)
        assert "Download" in detail or "Items" in detail or "example.com" in detail

    def test_missing_extent_handled(self):
        col = {"id": "ch.test", "title": "Test"}
        detail = format_collection_detail(col)
        assert isinstance(detail, str)


class TestFormatSearchResults:
    def test_empty_list_returns_empty_string(self):
        result = format_search_results([])
        assert result == ""

    def test_single_collection(self):
        result = format_search_results([SAMPLE_COLLECTION])
        assert "swissALTI3D" in result

    def test_multiple_collections_separated(self):
        col2 = {"id": "ch.swisstopo.swissimage", "title": "SWISSIMAGE", "description": "Luftbilder"}
        result = format_search_results([SAMPLE_COLLECTION, col2])
        assert "swissALTI3D" in result
        assert "SWISSIMAGE" in result


# ---------------------------------------------------------------------------
# Async Handler Tests (mocked)
# ---------------------------------------------------------------------------


class TestSearchGeodataHandler:
    async def test_search_returns_match(self, monkeypatch):
        async def mock_stac(path, params=None):
            return {
                "collections": [
                    {"id": "ch.swisstopo.swissalti3d", "title": "swissALTI3D", "description": "Höhenmodell"},
                    {"id": "ch.swisstopo.swissimage", "title": "SWISSIMAGE", "description": "Luftbilder Schweiz"},
                ]
            }

        monkeypatch.setattr("swisstopo_mcp.stac.stac_request", mock_stac)
        result = await search_geodata(SearchGeodataInput(query="swissALTI3D"))
        assert "swissALTI3D" in result
        assert "SWISSIMAGE" not in result

    async def test_search_case_insensitive(self, monkeypatch):
        async def mock_stac(path, params=None):
            return {
                "collections": [
                    {"id": "ch.swisstopo.swissalti3d", "title": "swissALTI3D", "description": "Höhenmodell"},
                ]
            }

        monkeypatch.setattr("swisstopo_mcp.stac.stac_request", mock_stac)
        result = await search_geodata(SearchGeodataInput(query="SWISSALTI3D"))
        assert "swissALTI3D" in result

    async def test_search_matches_description(self, monkeypatch):
        async def mock_stac(path, params=None):
            return {
                "collections": [
                    {"id": "ch.swisstopo.swissimage", "title": "SWISSIMAGE", "description": "Luftbilder der Schweiz"},
                ]
            }

        monkeypatch.setattr("swisstopo_mcp.stac.stac_request", mock_stac)
        result = await search_geodata(SearchGeodataInput(query="Luftbilder"))
        assert "SWISSIMAGE" in result

    async def test_search_no_match(self, monkeypatch):
        async def mock_stac(path, params=None):
            return {
                "collections": [
                    {"id": "ch.swisstopo.swissalti3d", "title": "swissALTI3D", "description": "Höhenmodell"},
                ]
            }

        monkeypatch.setattr("swisstopo_mcp.stac.stac_request", mock_stac)
        result = await search_geodata(SearchGeodataInput(query="xyznotfound"))
        assert "Keine Geodaten gefunden" in result
        assert "xyznotfound" in result

    async def test_search_respects_limit(self, monkeypatch):
        collections = [
            {"id": f"ch.test.col{i}", "title": f"Collection {i}", "description": "test collection"}
            for i in range(20)
        ]

        async def mock_stac(path, params=None):
            return {"collections": collections}

        monkeypatch.setattr("swisstopo_mcp.stac.stac_request", mock_stac)
        result = await search_geodata(SearchGeodataInput(query="test", limit=3))
        # 3 cards means 3 occurrences of "**ID:**"
        assert result.count("**ID:**") == 3

    async def test_search_api_error(self, monkeypatch):
        import httpx

        async def mock_stac(path, params=None):
            resp = httpx.Response(500, request=httpx.Request("GET", "http://test"))
            raise httpx.HTTPStatusError("Server error", request=resp.request, response=resp)

        monkeypatch.setattr("swisstopo_mcp.stac.stac_request", mock_stac)
        result = await search_geodata(SearchGeodataInput(query="test"))
        assert "Fehler" in result

    async def test_search_calls_collections_endpoint(self, monkeypatch):
        captured = {}

        async def mock_stac(path, params=None):
            captured["path"] = path
            return {"collections": []}

        monkeypatch.setattr("swisstopo_mcp.stac.stac_request", mock_stac)
        await search_geodata(SearchGeodataInput(query="test"))
        assert captured["path"] == "/collections"


class TestGetCollectionHandler:
    async def test_get_collection_returns_detail(self, monkeypatch):
        async def mock_stac(path, params=None):
            return SAMPLE_COLLECTION

        monkeypatch.setattr("swisstopo_mcp.stac.stac_request", mock_stac)
        result = await get_collection(GetCollectionInput(collection_id="ch.swisstopo.swissalti3d"))
        assert "swissALTI3D" in result
        assert "Höhenmodell" in result

    async def test_get_collection_calls_correct_path(self, monkeypatch):
        captured = {}

        async def mock_stac(path, params=None):
            captured["path"] = path
            return {"id": "ch.swisstopo.swissalti3d", "title": "Test", "description": "test"}

        monkeypatch.setattr("swisstopo_mcp.stac.stac_request", mock_stac)
        await get_collection(GetCollectionInput(collection_id="ch.swisstopo.swissalti3d"))
        assert captured["path"] == "/collections/ch.swisstopo.swissalti3d"

    async def test_get_collection_404(self, monkeypatch):
        import httpx

        async def mock_stac(path, params=None):
            resp = httpx.Response(404, request=httpx.Request("GET", "http://test"))
            raise httpx.HTTPStatusError("Not found", request=resp.request, response=resp)

        monkeypatch.setattr("swisstopo_mcp.stac.stac_request", mock_stac)
        result = await get_collection(GetCollectionInput(collection_id="ch.invalid.id"))
        assert "Fehler" in result
        assert "404" in result

    async def test_get_collection_timeout(self, monkeypatch):
        import httpx

        async def mock_stac(path, params=None):
            raise httpx.TimeoutException("timeout")

        monkeypatch.setattr("swisstopo_mcp.stac.stac_request", mock_stac)
        result = await get_collection(GetCollectionInput(collection_id="ch.test.id"))
        assert "Fehler" in result
        assert "Zeitüberschreitung" in result or "timeout" in result.lower()


# ---------------------------------------------------------------------------
# Live Tests (network required)
# ---------------------------------------------------------------------------


@pytest.mark.live
async def test_live_search_swissalti3d():
    result = await search_geodata(SearchGeodataInput(query="swissALTI3D"))
    assert isinstance(result, str)
    assert len(result) > 0
    # Should find something
    assert "Keine Geodaten gefunden" not in result
