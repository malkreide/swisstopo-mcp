# tests/test_openplz.py
"""OpenPLZ administrative-address tools: input validation, happy paths, the
abbreviation→key resolution, pagination, retry/timeout and graceful degradation."""
from __future__ import annotations

import httpx
import pytest
import respx
from pydantic import ValidationError

from swisstopo_mcp import api_client
from swisstopo_mcp.models import OPENPLZ_LICENSE, OPENPLZ_SOURCE, ToolResponse
from swisstopo_mcp.openplz import (
    FindCommuneInput,
    LookupPostalCodeInput,
    SearchAddressInput,
    _canton_key_for_bfs,
    find_commune,
    lookup_postal_code,
    reset_canton_cache,
    search_address,
)

BASE = "https://openplzapi.org/ch"


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    """Patch out the real 2s/4s/8s backoff so retry tests run instantly."""

    async def fake_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(api_client, "_sleep", fake_sleep)


@pytest.fixture(autouse=True)
def _fresh_canton_cache():
    """Each test starts with an empty canton abbreviation→key cache."""
    reset_canton_cache()
    yield
    reset_canton_cache()


# --- Fixtures / helpers -------------------------------------------------------

CANTONS_JSON = [
    {"key": "1", "historicalCode": "1", "name": "Zürich", "shortName": "ZH"},
    {"key": "2", "historicalCode": "2", "name": "Bern / Berne", "shortName": "BE"},
]

LOCALITY_8001 = [
    {
        "postalCode": "8001",
        "name": "Zürich",
        "commune": {"key": "261", "name": "Zürich", "shortName": "Zürich"},
        "district": {"key": "112", "name": "Bezirk Zürich", "shortName": "Zürich"},
        "canton": {"key": "1", "name": "Zürich", "shortName": "ZH"},
    }
]


def _commune(key: str, name: str, dkey: str = "109", dname: str = "Bezirk Uster") -> dict:
    return {
        "key": key,
        "historicalCode": "99999",
        "name": name,
        "shortName": name,
        "district": {"key": dkey, "name": dname, "shortName": dname},
        "canton": {"key": "1", "name": "Zürich", "shortName": "ZH"},
    }


# ---------------------------------------------------------------------------
# Input model validation
# ---------------------------------------------------------------------------


class TestInputModels:
    def test_postal_code_ok(self):
        assert LookupPostalCodeInput(postal_code="8001").postal_code == "8001"

    def test_postal_code_rejects_non_4_digit(self):
        with pytest.raises(ValidationError):
            LookupPostalCodeInput(postal_code="801")
        with pytest.raises(ValidationError):
            LookupPostalCodeInput(postal_code="80010")
        with pytest.raises(ValidationError):
            LookupPostalCodeInput(postal_code="ABCD")

    def test_find_commune_requires_exactly_one(self):
        with pytest.raises(ValidationError):
            FindCommuneInput()  # none
        with pytest.raises(ValidationError):
            FindCommuneInput(name="Uster", canton="ZH")  # two

    def test_find_commune_single_ok(self):
        assert FindCommuneInput(name="Uster").name == "Uster"
        assert FindCommuneInput(bfs_number=198).bfs_number == 198
        assert FindCommuneInput(canton="ZH").canton == "ZH"
        assert FindCommuneInput(canton="1").canton == "1"
        assert FindCommuneInput(district="109").district == "109"

    def test_find_commune_rejects_bad_canton(self):
        with pytest.raises(ValidationError):
            FindCommuneInput(canton="ZZZ")

    def test_bfs_number_bounds(self):
        with pytest.raises(ValidationError):
            FindCommuneInput(bfs_number=0)
        with pytest.raises(ValidationError):
            FindCommuneInput(bfs_number=10000)

    def test_search_limit_bounds(self):
        with pytest.raises(ValidationError):
            SearchAddressInput(query="x" * 2, limit=0)
        with pytest.raises(ValidationError):
            SearchAddressInput(query="Bahnhof", limit=51)
        assert SearchAddressInput(query="Bahnhof").limit == 20

    def test_extra_forbidden(self):
        with pytest.raises(ValidationError):
            LookupPostalCodeInput(postal_code="8001", foo="bar")


# ---------------------------------------------------------------------------
# BFS-number → canton block mapping (pure function)
# ---------------------------------------------------------------------------


class TestBfsBlockMapping:
    def test_zurich_block(self):
        assert _canton_key_for_bfs(1) == "1"
        assert _canton_key_for_bfs(261) == "1"  # Zürich city
        assert _canton_key_for_bfs(230) == "1"  # Winterthur
        assert _canton_key_for_bfs(198) == "1"  # Uster

    def test_bern_block(self):
        assert _canton_key_for_bfs(301) == "2"
        assert _canton_key_for_bfs(351) == "2"  # Bern city

    def test_below_range(self):
        assert _canton_key_for_bfs(0) is None


# ---------------------------------------------------------------------------
# lookup_postal_code
# ---------------------------------------------------------------------------


class TestLookupPostalCode:
    @respx.mock
    async def test_happy_path_exposes_bfs_top_level(self):
        respx.get(f"{BASE}/Localities").mock(
            return_value=httpx.Response(200, json=LOCALITY_8001)
        )
        res = await lookup_postal_code(LookupPostalCodeInput(postal_code="8001"))
        assert isinstance(res, ToolResponse)
        assert res.count == 1
        rec = res.results[0]
        # bfs_commune_number must be a named top-level field, not nested.
        assert rec["bfs_commune_number"] == "261"
        assert rec["commune_name"] == "Zürich"
        assert rec["canton"] == "ZH"
        assert res.source == OPENPLZ_SOURCE
        assert res.license == OPENPLZ_LICENSE
        assert "261" in res.summary

    @respx.mock
    async def test_unknown_plz_graceful(self):
        # Live probe finding: unknown PLZ → 200 [] (not 404).
        respx.get(f"{BASE}/Localities").mock(return_value=httpx.Response(200, json=[]))
        res = await lookup_postal_code(LookupPostalCodeInput(postal_code="9999"))
        assert res.count == 0
        assert res.match_type == "none"
        assert not res.is_error
        assert "9999" in res.summary

    @respx.mock
    async def test_retry_on_503_then_success(self):
        respx.get(f"{BASE}/Localities").mock(
            side_effect=[
                httpx.Response(503),
                httpx.Response(200, json=LOCALITY_8001),
            ]
        )
        res = await lookup_postal_code(LookupPostalCodeInput(postal_code="8001"))
        assert res.count == 1
        assert res.results[0]["bfs_commune_number"] == "261"

    @respx.mock
    async def test_timeout_degrades_gracefully(self):
        respx.get(f"{BASE}/Localities").mock(side_effect=httpx.ReadTimeout("slow"))
        res = await lookup_postal_code(LookupPostalCodeInput(postal_code="8001"))
        assert res.is_error
        assert res.source == OPENPLZ_SOURCE
        assert "Fehler" in res.summary


# ---------------------------------------------------------------------------
# find_commune — abbreviation→key resolution + pagination
# ---------------------------------------------------------------------------


class TestFindCommuneByName:
    @respx.mock
    async def test_name_resolves_to_bfs(self):
        respx.get(f"{BASE}/Localities").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "postalCode": "8610",
                        "name": "Uster",
                        "commune": {"key": "198", "name": "Uster", "shortName": "Uster"},
                        "district": {"key": "109", "name": "Bezirk Uster", "shortName": "Uster"},
                        "canton": {"key": "1", "name": "Zürich", "shortName": "ZH"},
                    }
                ],
            )
        )
        res = await find_commune(FindCommuneInput(name="Uster"))
        assert res.count == 1
        assert res.results[0]["bfs_commune_number"] == "198"


class TestFindCommuneByCanton:
    @respx.mock
    async def test_abbreviation_is_resolved_to_numeric_key(self):
        """The core trap: 'ZH' must be translated to key '1' before the path call,
        otherwise the API returns 200 [] silently."""
        cantons = respx.get(f"{BASE}/Cantons").mock(
            return_value=httpx.Response(200, json=CANTONS_JSON)
        )
        communes = respx.get(f"{BASE}/Cantons/1/Communes").mock(
            return_value=httpx.Response(
                200,
                json=[_commune("198", "Uster"), _commune("199", "Volketswil")],
                headers={"x-total-count": "2"},
            )
        )
        res = await find_commune(FindCommuneInput(canton="ZH"))
        assert cantons.called  # abbreviation was resolved via the live list
        assert communes.called
        # The request must have gone to /Cantons/1/Communes, never /Cantons/ZH/...
        called_urls = [str(c.request.url) for c in communes.calls]
        assert all("/Cantons/1/Communes" in u for u in called_urls)
        assert res.count == 2
        assert {r["bfs_commune_number"] for r in res.results} == {"198", "199"}

    @respx.mock
    async def test_numeric_canton_key_skips_canton_lookup(self):
        cantons = respx.get(f"{BASE}/Cantons").mock(
            return_value=httpx.Response(200, json=CANTONS_JSON)
        )
        respx.get(f"{BASE}/Cantons/1/Communes").mock(
            return_value=httpx.Response(
                200, json=[_commune("198", "Uster")], headers={"x-total-count": "1"}
            )
        )
        res = await find_commune(FindCommuneInput(canton="1"))
        assert not cantons.called  # numeric key needs no abbreviation resolution
        assert res.count == 1

    @respx.mock
    async def test_pagination_fetches_all_pages(self):
        """160-style case: pageSize is capped at 50, so a >50 list needs paging."""
        page1 = [_commune(str(1000 + i), f"G{i}") for i in range(50)]
        page2 = [_commune(str(1000 + 50 + i), f"H{i}") for i in range(10)]

        def _responder(request):
            page = request.url.params.get("page")
            batch = page1 if page == "1" else page2
            return httpx.Response(200, json=batch, headers={"x-total-count": "60"})

        respx.get(f"{BASE}/Cantons/1/Communes").mock(side_effect=_responder)
        res = await find_commune(FindCommuneInput(canton="1"))
        assert res.count == 60  # both pages merged, not just the first 50


class TestFindCommuneByBfs:
    @respx.mock
    async def test_bfs_reverse_lookup(self):
        respx.get(f"{BASE}/Cantons/1/Communes").mock(
            return_value=httpx.Response(
                200,
                json=[_commune("198", "Uster"), _commune("261", "Zürich")],
                headers={"x-total-count": "2"},
            )
        )
        res = await find_commune(FindCommuneInput(bfs_number=261))
        assert res.count == 1
        assert res.results[0]["commune_name"] == "Zürich"

    @respx.mock
    async def test_bfs_not_found_graceful(self):
        respx.get(f"{BASE}/Cantons/1/Communes").mock(
            return_value=httpx.Response(
                200, json=[_commune("198", "Uster")], headers={"x-total-count": "1"}
            )
        )
        res = await find_commune(FindCommuneInput(bfs_number=250))
        assert res.count == 0
        assert res.match_type == "none"
        assert not res.is_error
        assert "250" in res.summary


class TestFindCommuneByDistrict:
    @respx.mock
    async def test_district_list(self):
        respx.get(f"{BASE}/Districts/109/Communes").mock(
            return_value=httpx.Response(
                200,
                json=[_commune("191", "Dübendorf"), _commune("198", "Uster")],
                headers={"x-total-count": "2"},
            )
        )
        res = await find_commune(FindCommuneInput(district="109"))
        assert res.count == 2
        assert "BFS" in res.summary


# ---------------------------------------------------------------------------
# search_address
# ---------------------------------------------------------------------------


class TestSearchAddress:
    @respx.mock
    async def test_happy_path(self):
        respx.get(f"{BASE}/FullTextSearch").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "key": "10133611",
                        "name": "Aabachweg",
                        "postalCode": "8610",
                        "locality": "Uster",
                        "commune": {"key": "198", "name": "Uster", "shortName": "Uster"},
                        "district": {"key": "109", "name": "Bezirk Uster", "shortName": "Uster"},
                        "canton": {"key": "1", "name": "Zürich", "shortName": "ZH"},
                        "status": "Real",
                    }
                ],
                headers={"x-total-count": "403"},
            )
        )
        res = await search_address(SearchAddressInput(query="Uster"))
        assert res.count == 1
        assert res.results[0]["bfs_commune_number"] == "198"
        assert "403" in res.summary  # total surfaced

    @respx.mock
    async def test_empty_graceful(self):
        respx.get(f"{BASE}/FullTextSearch").mock(
            return_value=httpx.Response(200, json=[], headers={"x-total-count": "0"})
        )
        res = await search_address(SearchAddressInput(query="zzzznotfound"))
        assert res.count == 0
        assert res.match_type == "none"
        assert not res.is_error


# ---------------------------------------------------------------------------
# Live tests (network required) — excluded from CI via -m "not live"
# ---------------------------------------------------------------------------


@pytest.mark.live
async def test_live_lookup_postal_code():
    res = await lookup_postal_code(LookupPostalCodeInput(postal_code="8001"))
    assert res.count >= 1
    assert res.results[0]["bfs_commune_number"] == "261"


@pytest.mark.live
async def test_live_find_commune_canton_abbreviation():
    res = await find_commune(FindCommuneInput(canton="ZH"))
    assert res.count == 160  # ZH has 160 communes (live-probe reality check)


@pytest.mark.live
async def test_live_find_commune_district_uster():
    res = await find_commune(FindCommuneInput(district="109"))
    assert res.count == 10
    assert any(r["commune_name"] == "Uster" for r in res.results)
