# tests/test_oereb.py
"""Tests for ÖREB Cadastre module (no live network calls)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from swisstopo_mcp.config import settings
from swisstopo_mcp.models import OEREB_LICENSE, OEREB_SOURCE
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
        monkeypatch.setattr(settings, "oereb_cantons", "ZH")
        result = get_active_cantons()
        assert "ZH" in result
        assert "BE" not in result

    def test_env_var_zh_only(self, monkeypatch):
        monkeypatch.setattr(settings, "oereb_cantons", "ZH")
        result = get_active_cantons()
        assert "ZH" in result
        assert "BE" not in result

    def test_env_var_be_only(self, monkeypatch):
        monkeypatch.setattr(settings, "oereb_cantons", "BE")
        result = get_active_cantons()
        assert "BE" in result
        assert "ZH" not in result

    def test_env_var_both(self, monkeypatch):
        monkeypatch.setattr(settings, "oereb_cantons", "ZH,BE")
        result = get_active_cantons()
        assert "ZH" in result
        assert "BE" in result

    def test_env_var_with_spaces(self, monkeypatch):
        monkeypatch.setattr(settings, "oereb_cantons", "ZH, BE")
        result = get_active_cantons()
        assert "ZH" in result
        assert "BE" in result

    def test_env_var_lowercase_normalized(self, monkeypatch):
        monkeypatch.setattr(settings, "oereb_cantons", "zh,be")
        result = get_active_cantons()
        assert "ZH" in result
        assert "BE" in result

    def test_unknown_canton_filtered_out(self, monkeypatch):
        monkeypatch.setattr(settings, "oereb_cantons", "XX")
        result = get_active_cantons()
        assert len(result) == 0

    def test_returns_dict(self, monkeypatch):
        monkeypatch.setattr(settings, "oereb_cantons", "ZH")
        result = get_active_cantons()
        assert isinstance(result, dict)


class TestGetOerebEndpoint:
    def test_zh_returns_url(self, monkeypatch):
        monkeypatch.setattr(settings, "oereb_cantons", "ZH,BE")
        result = get_oereb_endpoint("ZH")
        assert result is not None
        assert result.startswith("https://")

    def test_be_returns_url(self, monkeypatch):
        monkeypatch.setattr(settings, "oereb_cantons", "ZH,BE")
        result = get_oereb_endpoint("BE")
        assert result is not None

    def test_unknown_returns_none(self, monkeypatch):
        monkeypatch.setattr(settings, "oereb_cantons", "ZH")
        result = get_oereb_endpoint("XX")
        assert result is None

    def test_inactive_canton_returns_none(self, monkeypatch):
        monkeypatch.setattr(settings, "oereb_cantons", "ZH")
        result = get_oereb_endpoint("BE")
        assert result is None

    def test_lowercase_input_normalized(self, monkeypatch):
        monkeypatch.setattr(settings, "oereb_cantons", "ZH,BE")
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

    @pytest.mark.parametrize(
        "topics",
        [
            "ch.Nutzungsplanung",
            "ch.BE.Gewaesserschutzbereiche",
            "ch.Nutzungsplanung,ch.Laermempfindlichkeitsstufen",
            # A space after the comma is what anyone writing a list does, and
            # the parser already strips it.
            "ch.Nutzungsplanung, ch.Laermempfindlichkeitsstufen",
            "ch.NutzungsplanungGrundnutzungNutzungszonen",
        ],
    )
    def test_topics_accepts_real_theme_codes(self, topics):
        """Every ÖREB theme code contains a dot. The charset used to omit it,
        so the field rejected all of these and accepted only the bare
        `Nutzungsplanung` — which matches no theme. The filter was unusable
        before it ever reached the network."""
        m = GetOerebExtractInput(egrid="CH767982496078", canton="ZH", topics=topics)
        assert m.topics == topics

    def test_the_one_call_tool_accepts_the_same_theme_codes(self):
        """`swisstopo_oereb_at` collapses the two-step chain, so a caller must
        be able to name a theme there too — it could not, when the charset fix
        landed on `GetOerebExtractInput` alone.

        The general guard now lives in
        `tests/test_input_validation.py::TestAggregatesValidateLikeTheirDelegates`,
        which compares every passed-through field of both aggregates. This one
        stays because it pins the behaviour rather than the constraint: it
        fails even if someone keeps the two definitions in sync at a value that
        rejects real codes.
        """
        from swisstopo_mcp.oereb import OerebAtInput

        m = OerebAtInput(lat=47.3769, lon=8.5417, canton="ZH", topics="ch.Nutzungsplanung")
        assert m.topics == "ch.Nutzungsplanung"

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
        monkeypatch.setattr(settings, "oereb_cantons", "ZH")
        result = await get_egrid(GetEgridInput(lat=47.0, lon=8.5, canton="BE"))
        assert "BE" in result.summary
        assert "nicht unterstützt" in result.summary or "nicht" in result.summary
        assert "oereb.cadastre.ch" in result.summary

    async def test_get_egrid_unknown_canton(self, monkeypatch):
        monkeypatch.setattr(settings, "oereb_cantons", "ZH")
        result = await get_egrid(GetEgridInput(lat=47.0, lon=8.5, canton="XX"))
        assert "XX" in result.summary
        assert "oereb.cadastre.ch" in result.summary

    async def test_get_egrid_message_contains_available(self, monkeypatch):
        monkeypatch.setattr(settings, "oereb_cantons", "ZH,BE")
        # Use a canton not in registry at all
        result = await get_egrid(GetEgridInput(lat=47.0, lon=8.5, canton="XX"))
        # Should mention available cantons
        assert "ZH" in result.summary or "BE" in result.summary

    async def test_get_oereb_extract_unsupported_canton(self, monkeypatch):
        monkeypatch.setattr(settings, "oereb_cantons", "ZH")
        result = await get_oereb_extract(GetOerebExtractInput(egrid="CH767982496078", canton="BE"))
        assert "BE" in result.summary
        assert "nicht unterstützt" in result.summary or "nicht" in result.summary
        assert "oereb.cadastre.ch" in result.summary

    async def test_get_oereb_extract_unknown_canton(self, monkeypatch):
        monkeypatch.setattr(settings, "oereb_cantons", "ZH")
        result = await get_oereb_extract(GetOerebExtractInput(egrid="CH767982496078", canton="XX"))
        assert "XX" in result.summary
        assert "oereb.cadastre.ch" in result.summary


# ---------------------------------------------------------------------------
# Mocked HTTP Responses
#
# The payloads below are trimmed copies of what `maps.zh.ch/oereb/v2` and
# `www.oereb2.apps.be.ch` actually return, not invented shapes. The previous
# fixtures modelled a GeoJSON `features` list and a flat `Topic`/`Information`
# restriction, neither of which exists in the ÖREB data-extract 2.0 schema the
# services speak — so the suite stayed green through a parser that returned
# "kein EGRID gefunden" and "keine Eigentumsbeschränkungen" for every parcel in
# the country. Keep these anchored to real responses.
# ---------------------------------------------------------------------------


def _mock_client(monkeypatch, payload, status_code=200, capture=None):
    """Point the ÖREB handlers at a canned JSON response.

    `capture` is an optional dict that receives the requested URL under "url".
    """
    import json as _json

    body = b"" if status_code == 204 else _json.dumps(payload).encode()

    async def mock_get_client():
        class MockResponse:
            content = body

            def __init__(self):
                self.status_code = status_code

            def raise_for_status(self):
                pass

            def json(self):
                return payload

        class MockClient:
            async def get(self, url):
                if capture is not None:
                    capture["url"] = url
                return MockResponse()

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

        return MockClient()

    monkeypatch.setattr("swisstopo_mcp.oereb._get_client", mock_get_client)


def _mock_raising_client(monkeypatch, exc_factory):
    """Point the handlers at a client whose GET raises."""

    async def mock_get_client():
        class MockClient:
            async def get(self, url):
                raise exc_factory(url)

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

        return MockClient()

    monkeypatch.setattr("swisstopo_mcp.oereb._get_client", mock_get_client)


def _egrid_payload(*entries):
    """A `getegrid` answer in the 2.0 shape both live cantons serve."""
    return {"GetEGRIDResponse": list(entries)}


class TestGetEgridHandler:
    async def test_returns_egrid_string(self, monkeypatch):
        monkeypatch.setattr(settings, "oereb_cantons", "ZH,BE")
        _mock_client(
            monkeypatch,
            _egrid_payload(
                {
                    "egrid": "CH767982496078",
                    "number": "WO6408",
                    "identDN": "ZH0200000261",
                }
            ),
        )
        result = await get_egrid(GetEgridInput(lat=47.376, lon=8.541, canton="ZH"))
        assert "CH767982496078" in result.summary
        # The parcel number is what the 2.0 answer actually carries; the old
        # formatter printed "Gemeinde: ?" because it looked for a name that is
        # not in this response at all.
        assert "WO6408" in result.summary
        assert result.results[0]["egrid"] == "CH767982496078"

    async def test_reads_the_legacy_geojson_shape(self, monkeypatch):
        """ZH served this until it moved to /oereb/v2; a canton that has not
        migrated yet must not read as an empty parcel."""
        monkeypatch.setattr(settings, "oereb_cantons", "ZH,BE")
        _mock_client(
            monkeypatch,
            {"features": [{"properties": {"egrid": "CH111", "gemeindename": "Zürich"}}]},
        )
        result = await get_egrid(GetEgridInput(lat=47.376, lon=8.541, canton="ZH"))
        assert "CH111" in result.summary
        assert "Zürich" in result.summary

    async def test_no_features_returns_not_found(self, monkeypatch):
        monkeypatch.setattr(settings, "oereb_cantons", "ZH,BE")
        _mock_client(monkeypatch, _egrid_payload())
        result = await get_egrid(GetEgridInput(lat=47.376, lon=8.541, canton="ZH"))
        assert "gefunden" in result.summary.lower() or "kein" in result.summary.lower()

    async def test_204_is_a_miss_not_an_error(self, monkeypatch):
        """A point with no parcel under it answers 204 with an empty body.
        Parsing that as JSON turns a legitimate miss into 'Unerwarteter
        interner Fehler'."""
        monkeypatch.setattr(settings, "oereb_cantons", "ZH,BE")
        _mock_client(monkeypatch, None, status_code=204)
        result = await get_egrid(GetEgridInput(lat=47.376, lon=8.541, canton="ZH"))
        assert result.is_error is False
        assert result.match_type == "none"

    async def test_uses_lv95_coordinates_in_url(self, monkeypatch):
        monkeypatch.setattr(settings, "oereb_cantons", "ZH,BE")
        captured = {}
        _mock_client(monkeypatch, _egrid_payload(), capture=captured)
        await get_egrid(GetEgridInput(lat=47.376, lon=8.541, canton="ZH"))
        # URL should contain EN= with LV95 coordinates (easting first)
        assert "EN=" in captured["url"]
        assert "/getegrid/json/" in captured["url"]

    async def test_http_error_returns_error_message(self, monkeypatch):
        import httpx

        monkeypatch.setattr(settings, "oereb_cantons", "ZH,BE")
        _mock_raising_client(
            monkeypatch,
            lambda url: httpx.HTTPStatusError(
                "Server error",
                request=httpx.Request("GET", url),
                response=httpx.Response(500, request=httpx.Request("GET", url)),
            ),
        )
        result = await get_egrid(GetEgridInput(lat=47.376, lon=8.541, canton="ZH"))
        assert "Fehler" in result.summary

    async def test_timeout_returns_error_message(self, monkeypatch):
        import httpx

        monkeypatch.setattr(settings, "oereb_cantons", "ZH,BE")
        _mock_raising_client(monkeypatch, lambda url: httpx.TimeoutException("timeout"))
        result = await get_egrid(GetEgridInput(lat=47.376, lon=8.541, canton="ZH"))
        assert "Fehler" in result.summary or "Zeitüberschreitung" in result.summary

    async def test_multiple_features_returned(self, monkeypatch):
        monkeypatch.setattr(settings, "oereb_cantons", "ZH,BE")
        _mock_client(
            monkeypatch,
            _egrid_payload({"egrid": "CH111"}, {"egrid": "CH222"}),
        )
        result = await get_egrid(GetEgridInput(lat=47.376, lon=8.541, canton="ZH"))
        assert "CH111" in result.summary
        assert "CH222" in result.summary


class TestGetOerebExtractHandler:
    def _make_extract_response(self, topics=None, wrapper="Extract"):
        """Build a minimal ÖREB extract JSON response.

        `wrapper` exists because the two live services disagree on it: ZH nests
        under `Extract`, BE under `extract`. Both are exercised below.
        """
        if topics is None:
            topics = []
        return {
            "GetExtractByIdResponse": {
                wrapper: {"RealEstate": {"RestrictionOnLandownership": topics}}
            }
        }

    def _make_restriction(
        self,
        topic="Nutzungsplanung",
        description="Wohnzone W2",
        authority="Gemeinde Zürich",
        legal="Bau- und Zonenordnung",
        code="ch.Nutzungsplanung",
        subcode=None,
    ):
        theme = {"Code": code, "Text": [{"Language": "de", "Text": topic}]}
        if subcode:
            theme["SubCode"] = subcode
        return {
            "Theme": theme,
            "LegendText": [{"Language": "de", "Text": description}],
            "Lawstatus": {"Code": "inForce", "Text": [{"Language": "de", "Text": "Rechtskräftig"}]},
            "ResponsibleOffice": {"Name": [{"Language": "de", "Text": authority}]},
            "LegalProvisions": [{"Title": [{"Language": "de", "Text": legal}]}],
            "AreaShare": 2556,
            "PartInPercent": 12.5,
        }

    async def test_returns_markdown_extract(self, monkeypatch):
        monkeypatch.setattr(settings, "oereb_cantons", "ZH,BE")
        _mock_client(monkeypatch, self._make_extract_response([self._make_restriction()]))
        result = await get_oereb_extract(GetOerebExtractInput(egrid="CH767982496078", canton="ZH"))
        assert "## ÖREB-Auszug für CH767982496078" in result.summary
        assert "Nutzungsplanung" in result.summary
        assert "Wohnzone W2" in result.summary
        assert "Gemeinde Zürich" in result.summary
        assert "Rechtskräftig" in result.summary

    async def test_reads_the_lowercase_extract_wrapper(self, monkeypatch):
        """BE spells the same node `extract`. Descending into the wrong one used
        to report every parcel as unencumbered."""
        monkeypatch.setattr(settings, "oereb_cantons", "ZH,BE")
        _mock_client(
            monkeypatch,
            self._make_extract_response([self._make_restriction()], wrapper="extract"),
        )
        result = await get_oereb_extract(GetOerebExtractInput(egrid="CH507635214670", canton="BE"))
        assert result.match_type == "exact"
        assert "Wohnzone W2" in result.summary

    async def test_results_are_compact_records(self, monkeypatch):
        """A raw ZH restriction carries an encoded WMS GetMap request and the
        full theme legend; eighteen of those would bury the answer."""
        monkeypatch.setattr(settings, "oereb_cantons", "ZH,BE")
        restriction = self._make_restriction()
        restriction["Map"] = {"ReferenceWMS": [{"Language": "de", "Text": "https://" + "x" * 5000}]}
        _mock_client(monkeypatch, self._make_extract_response([restriction]))
        result = await get_oereb_extract(GetOerebExtractInput(egrid="CH767982496078", canton="ZH"))
        record = result.results[0]
        assert record == {
            "theme": "Nutzungsplanung",
            "theme_code": "ch.Nutzungsplanung",
            "theme_subcode": "",
            "legend_text": "Wohnzone W2",
            "lawstatus": "Rechtskräftig",
            "responsible_office": "Gemeinde Zürich",
            "legal_provisions": ["Bau- und Zonenordnung"],
            "area_share_m2": 2556,
            "part_in_percent": 12.5,
        }

    async def test_no_restrictions_returns_empty_message(self, monkeypatch):
        monkeypatch.setattr(settings, "oereb_cantons", "ZH,BE")
        _mock_client(monkeypatch, self._make_extract_response([]))
        result = await get_oereb_extract(GetOerebExtractInput(egrid="CH767982496078", canton="ZH"))
        assert "Keine" in result.summary

    async def test_404_egrid_not_found(self, monkeypatch):
        monkeypatch.setattr(settings, "oereb_cantons", "ZH,BE")
        _mock_client(monkeypatch, None, status_code=404)
        # Valid EGRID format (alphanumeric) but non-existent -> upstream 404.
        result = await get_oereb_extract(GetOerebExtractInput(egrid="CH000000000000", canton="ZH"))
        assert "nicht gefunden" in result.summary or "CH000000000000" in result.summary

    async def test_204_egrid_not_found(self, monkeypatch):
        """ZH answers an unknown EGRID with 204 and an empty body rather than
        404 — same meaning, and equally not JSON."""
        monkeypatch.setattr(settings, "oereb_cantons", "ZH,BE")
        result_payload = None
        _mock_client(monkeypatch, result_payload, status_code=204)
        result = await get_oereb_extract(GetOerebExtractInput(egrid="CH000000000000", canton="ZH"))
        assert result.is_error is False
        assert result.match_type == "none"
        assert "CH000000000000" in result.summary

    async def test_topics_never_reaches_the_url(self, monkeypatch):
        """The filter is applied here, not upstream, and that is deliberate.

        `TOPICS` is honoured by BE and ignored outright by ZH — passing it
        would make the same call behave differently per canton. Worse, where it
        *did* work the upstream returned a bare empty extract, so "your filter
        matched nothing" was indistinguishable from "this parcel carries no
        restrictions". Fetching unfiltered keeps the full theme list in hand.
        """
        monkeypatch.setattr(settings, "oereb_cantons", "ZH,BE")
        captured = {}
        _mock_client(monkeypatch, self._make_extract_response([]), capture=captured)
        await get_oereb_extract(
            GetOerebExtractInput(egrid="CH767982496078", canton="ZH", topics="ch.Nutzungsplanung")
        )
        assert "TOPICS" not in captured["url"]

    async def test_topics_filters_by_theme_code(self, monkeypatch):
        monkeypatch.setattr(settings, "oereb_cantons", "ZH,BE")
        _mock_client(
            monkeypatch,
            self._make_extract_response(
                [
                    self._make_restriction(code="ch.Nutzungsplanung", description="Wohnzone"),
                    self._make_restriction(
                        code="ch.Laermempfindlichkeitsstufen",
                        topic="Lärm",
                        description="ES II",
                    ),
                ]
            ),
        )
        result = await get_oereb_extract(
            GetOerebExtractInput(egrid="CH767982496078", canton="ZH", topics="ch.Nutzungsplanung")
        )
        assert result.count == 1
        assert "Wohnzone" in result.summary
        assert "ES II" not in result.summary

    async def test_topics_accepts_several_codes_and_ignores_case(self, monkeypatch):
        monkeypatch.setattr(settings, "oereb_cantons", "ZH,BE")
        _mock_client(
            monkeypatch,
            self._make_extract_response(
                [
                    self._make_restriction(code="ch.Nutzungsplanung"),
                    self._make_restriction(code="ch.Laermempfindlichkeitsstufen", topic="Lärm"),
                    self._make_restriction(code="ch.BelasteteStandorte", topic="Altlasten"),
                ]
            ),
        )
        result = await get_oereb_extract(
            GetOerebExtractInput(
                egrid="CH767982496078",
                canton="ZH",
                topics="CH.NUTZUNGSPLANUNG, ch.Laermempfindlichkeitsstufen",
            )
        )
        assert result.count == 2

    async def test_topics_matches_a_subcode(self, monkeypatch):
        """BE files three different sub-codes under the single code
        `ch.Nutzungsplanung`; matching only on the code makes them unreachable."""
        monkeypatch.setattr(settings, "oereb_cantons", "ZH,BE")
        _mock_client(
            monkeypatch,
            self._make_extract_response(
                [
                    self._make_restriction(
                        subcode="ch.NutzungsplanungGrundnutzungNutzungszonen",
                        description="Nutzungszone",
                    ),
                    self._make_restriction(
                        subcode="ch.NutzungsplanungUeberlagerung",
                        description="Überlagerung",
                    ),
                ],
                wrapper="extract",
            ),
        )
        result = await get_oereb_extract(
            GetOerebExtractInput(
                egrid="CH507635214670",
                canton="BE",
                topics="ch.NutzungsplanungUeberlagerung",
            )
        )
        assert result.count == 1
        assert "Überlagerung" in result.summary

    async def test_topics_matching_nothing_names_the_available_themes(self, monkeypatch):
        """The failure this guards against is the one the envelope bug had: an
        empty answer that reads like an unencumbered parcel."""
        monkeypatch.setattr(settings, "oereb_cantons", "ZH,BE")
        _mock_client(
            monkeypatch,
            self._make_extract_response(
                [
                    self._make_restriction(code="ch.Nutzungsplanung"),
                    self._make_restriction(code="ch.BelasteteStandorte", topic="Altlasten"),
                ]
            ),
        )
        result = await get_oereb_extract(
            GetOerebExtractInput(egrid="CH767982496078", canton="ZH", topics="ch.Waldgrenzen")
        )
        assert result.is_error is False
        assert result.match_type == "none"
        assert result.results == []
        # The caller must be able to tell "wrong filter" from "nothing here",
        # and must not have to guess the spelling for the retry.
        assert "2 Beschränkung" in result.summary
        assert "ch.Nutzungsplanung" in result.note
        assert "ch.BelasteteStandorte" in result.note

    async def test_an_empty_extract_does_not_blame_the_filter(self, monkeypatch):
        """The other side of the same coin: no restrictions at all is not a
        filter problem, and the note must not send the caller chasing one."""
        monkeypatch.setattr(settings, "oereb_cantons", "ZH,BE")
        _mock_client(monkeypatch, self._make_extract_response([]))
        result = await get_oereb_extract(
            GetOerebExtractInput(egrid="CH767982496078", canton="ZH", topics="ch.Nutzungsplanung")
        )
        assert result.match_type == "none"
        assert "unabhängig von einem Themenfilter" in result.note

    async def test_lang_passed_in_url(self, monkeypatch):
        monkeypatch.setattr(settings, "oereb_cantons", "ZH,BE")
        captured = {}
        _mock_client(monkeypatch, self._make_extract_response([]), capture=captured)
        await get_oereb_extract(
            GetOerebExtractInput(egrid="CH767982496078", canton="ZH", lang="fr")
        )
        assert "LANG=fr" in captured["url"]

    async def test_lang_selects_the_translation(self, monkeypatch):
        """The multilingual fields carry every language at once; asking for `fr`
        and rendering the German text would be a silent mistranslation."""
        monkeypatch.setattr(settings, "oereb_cantons", "ZH,BE")
        restriction = self._make_restriction()
        restriction["LegendText"] = [
            {"Language": "de", "Text": "Wohnzone W2"},
            {"Language": "fr", "Text": "Zone d'habitation W2"},
        ]
        _mock_client(monkeypatch, self._make_extract_response([restriction]))
        result = await get_oereb_extract(
            GetOerebExtractInput(egrid="CH767982496078", canton="ZH", lang="fr")
        )
        assert "Zone d'habitation W2" in result.summary
        assert "Wohnzone W2" not in result.summary

    async def test_http_error_returns_error_message(self, monkeypatch):
        import httpx

        monkeypatch.setattr(settings, "oereb_cantons", "ZH,BE")
        _mock_raising_client(
            monkeypatch,
            lambda url: httpx.HTTPStatusError(
                "Server error",
                request=httpx.Request("GET", url),
                response=httpx.Response(500, request=httpx.Request("GET", url)),
            ),
        )
        result = await get_oereb_extract(GetOerebExtractInput(egrid="CH767982496078", canton="ZH"))
        assert "Fehler" in result.summary

    async def test_grouped_by_topic(self, monkeypatch):
        monkeypatch.setattr(settings, "oereb_cantons", "ZH,BE")
        _mock_client(
            monkeypatch,
            self._make_extract_response(
                [
                    self._make_restriction(topic="Nutzungsplanung", description="Wohnzone"),
                    self._make_restriction(topic="Waldabstand", description="Waldabstandslinie"),
                ]
            ),
        )
        result = await get_oereb_extract(GetOerebExtractInput(egrid="CH767982496078", canton="ZH"))
        assert "### Nutzungsplanung" in result.summary
        assert "### Waldabstand" in result.summary
        assert "Wohnzone" in result.summary
        assert "Waldabstandslinie" in result.summary

    async def test_egrid_in_heading(self, monkeypatch):
        monkeypatch.setattr(settings, "oereb_cantons", "ZH,BE")
        _mock_client(monkeypatch, self._make_extract_response([self._make_restriction()]))
        result = await get_oereb_extract(GetOerebExtractInput(egrid="CH767982496078", canton="ZH"))
        assert "CH767982496078" in result.summary


# ---------------------------------------------------------------------------
# One-call aggregate (audit ARCH-007)
# ---------------------------------------------------------------------------

import httpx  # noqa: E402
import respx  # noqa: E402

from swisstopo_mcp.oereb import (  # noqa: E402
    OerebAtInput,
    _first_egrid,
    _parse_egrid_payload,
    oereb_at,
)

_ZH = "https://maps.zh.ch/oereb/v2"
_EGRID_PAYLOAD = _egrid_payload({"egrid": "CH807306036483", "number": "WO6408"})


class TestParseEgridPayload:
    def test_reads_the_2_0_shape(self):
        assert _parse_egrid_payload(_EGRID_PAYLOAD) == [
            {"egrid": "CH807306036483", "number": "WO6408"}
        ]

    def test_uppercase_key(self):
        """Cantonal endpoints disagree on the casing."""
        assert _parse_egrid_payload({"GetEGRIDResponse": [{"EGRID": "CH2"}]}) == [{"egrid": "CH2"}]

    def test_skips_entries_without_an_egrid(self):
        payload = {"GetEGRIDResponse": [{"number": "1"}, {"egrid": "CH3"}]}
        assert _parse_egrid_payload(payload) == [{"egrid": "CH3"}]

    def test_reads_the_legacy_geojson_shape(self):
        payload = {"features": [{"properties": {"egrid": "CH4", "gemeindename": "Uster"}}]}
        assert _parse_egrid_payload(payload) == [{"egrid": "CH4", "municipality": "Uster"}]

    def test_unknown_shape_gives_nothing(self):
        assert _parse_egrid_payload({"something": "else"}) == []
        assert _parse_egrid_payload("not json at all") == []


class TestFirstEgrid:
    def test_takes_the_first_record(self):
        assert _first_egrid([{"egrid": "CH1"}, {"egrid": "CH2"}]) == "CH1"

    def test_skips_records_without_an_egrid(self):
        assert _first_egrid([{"number": "1"}, {"egrid": "CH3"}]) == "CH3"

    def test_empty_gives_none(self):
        assert _first_egrid([]) is None


class TestOerebAt:
    @respx.mock
    async def test_resolves_egrid_and_returns_the_extract(self, monkeypatch):
        """The EGRID is an upstream identifier, not something the caller asked
        for — it must not require a second tool call (ARCH-007)."""
        monkeypatch.setattr(settings, "oereb_cantons", "ZH")
        egrid_route = respx.get(url__startswith=f"{_ZH}/getegrid/json/").mock(
            return_value=httpx.Response(200, json=_EGRID_PAYLOAD)
        )
        extract_route = respx.get(url__startswith=f"{_ZH}/extract/json/").mock(
            return_value=httpx.Response(200, json={"extract": {}})
        )
        out = await oereb_at(OerebAtInput(lat=47.3769, lon=8.5417, canton="ZH"))
        assert out.is_error is False
        assert egrid_route.called and extract_route.called
        # The resolved EGRID must reach the extract call.
        assert "CH807306036483" in str(extract_route.calls[0].request.url)

    @respx.mock
    async def test_no_parcel_is_a_soft_miss_with_a_hint(self, monkeypatch):
        monkeypatch.setattr(settings, "oereb_cantons", "ZH")
        respx.get(url__startswith=f"{_ZH}/getegrid/json/").mock(return_value=httpx.Response(204))
        out = await oereb_at(OerebAtInput(lat=47.3769, lon=8.5417, canton="ZH"))
        assert out.is_error is False
        assert out.match_type == "none"
        assert out.note and "municipality_at" in out.note

    async def test_unsupported_canton_is_reported(self, monkeypatch):
        monkeypatch.setattr(settings, "oereb_cantons", "ZH")
        out = await oereb_at(OerebAtInput(lat=47.3769, lon=8.5417, canton="GR"))
        assert out.is_error is True
        assert "GR" in out.summary

    @respx.mock
    async def test_upstream_failure_is_handled(self, monkeypatch):
        monkeypatch.setattr(settings, "oereb_cantons", "ZH")
        respx.get(url__startswith=f"{_ZH}/getegrid/json/").mock(
            return_value=httpx.Response(500, text="boom")
        )
        out = await oereb_at(OerebAtInput(lat=47.3769, lon=8.5417, canton="ZH"))
        assert out.is_error is True
        assert "boom" not in out.summary

    async def test_accepts_lv95_input(self, monkeypatch):
        monkeypatch.setattr(settings, "oereb_cantons", "ZH")
        m = OerebAtInput(easting=2683531.0, northing=1247914.0, canton="ZH")
        assert m.as_lv95 == (2683531.0, 1247914.0)


# ---------------------------------------------------------------------------
# Live tests (audit OPS-001)
#
# The nightly run had no coverage of this cluster at all, which is the sharpest
# gap it could have had: the cantonal ÖREB endpoints are the only per-canton,
# per-format upstream in this server, they are operated by cantons rather than
# by the Confederation, and their response shape is the thing most likely to
# change without notice. Everything else here talks to api3.geo.admin.ch.
#
# These are deliberately shallow. The job is contract drift — did the endpoint
# move, did the payload stop parsing — not correctness of a particular parcel.
# ---------------------------------------------------------------------------

# Zürich, Bederstrasse area. A point inside canton ZH, which is the one canton
# enabled by default.
ZH_LAT, ZH_LON = 47.360966, 8.525343

# Bern, Bundeshaus. Canton BE runs a different ÖREB implementation on a
# different host, and every format difference this server has had to absorb was
# a ZH/BE difference: the extract envelope is `Extract` on one and `extract` on
# the other, `SubCode` is unset on one and carries three values on the other,
# and `TOPICS` is honoured by one and ignored by the other. All three were found
# by hand, because the live tests ran on ZH alone — BE existed only in fixtures,
# which is to say only in assumptions about BE.
BE_LAT, BE_LON = 46.9480, 7.4474

# (canton, lat, lon) for the probes below. BE is not enabled by default, so the
# tests that use it widen `oereb_cantons` for their duration.
LIVE_CANTONS = [("ZH", ZH_LAT, ZH_LON), ("BE", BE_LAT, BE_LON)]


@pytest.fixture
def both_cantons(monkeypatch):
    """Enable BE alongside ZH. The default is ZH only, so a BE probe would
    otherwise fail on 'Kanton nicht unterstützt' rather than reach upstream."""
    monkeypatch.setattr(settings, "oereb_cantons", "ZH,BE")


@pytest.mark.live
class TestOerebLive:
    @pytest.mark.parametrize("canton,lat,lon", LIVE_CANTONS)
    async def test_each_canton_resolves_a_point_to_an_egrid(self, canton, lat, lon, both_cantons):
        """Same contract, both implementations. `getegrid` is where the 2.0
        envelope first shows up, and BE served it correctly the whole time the
        parser was reading GeoJSON — a BE probe here would have caught that."""
        result = await get_egrid(GetEgridInput(lat=lat, lon=lon, canton=canton))
        assert result.is_error is False, result.summary
        assert result.source == OEREB_SOURCE
        assert result.match_type in {"exact", "none"}
        if result.results:
            egrid = result.results[0].get("egrid")
            assert isinstance(egrid, str) and egrid, "EGRID field shape changed"

    @pytest.mark.parametrize("canton,lat,lon", LIVE_CANTONS)
    async def test_each_canton_parses_its_extract_envelope(self, canton, lat, lon, both_cantons):
        """The envelope key differs per canton (`Extract` vs `extract`), and
        descending into the wrong node reported every parcel as unencumbered.
        Asserting on `match_type` alone would not catch it — an empty extract is
        a legitimate answer — so this also requires the restriction records to
        carry the fields the formatter and the topics filter read."""
        located = await get_egrid(GetEgridInput(lat=lat, lon=lon, canton=canton))
        if not located.results:
            pytest.skip(f"no parcel at the {canton} probe point today")
        egrid = located.results[0]["egrid"]

        result = await get_oereb_extract(GetOerebExtractInput(egrid=egrid, canton=canton))
        assert result.is_error is False, result.summary
        assert result.source == OEREB_SOURCE
        if result.match_type == "exact":
            assert result.results, "match_type 'exact' with no records is drift"
            first = result.results[0]
            for key in ("theme", "theme_code", "legend_text", "lawstatus"):
                assert key in first, f"restriction record lost '{key}'"
            assert first["theme_code"], (
                "no theme code — the topics filter matches on this, so an empty "
                "one makes filtering silently impossible"
            )

    @pytest.mark.parametrize("canton,lat,lon", LIVE_CANTONS)
    async def test_each_canton_answers_the_one_call_aggregate(self, canton, lat, lon, both_cantons):
        result = await oereb_at(OerebAtInput(lat=lat, lon=lon, canton=canton))
        assert result.is_error is False, result.summary
        assert result.source == OEREB_SOURCE
        assert result.license == OEREB_LICENSE
        assert result.match_type in {"exact", "none"}
        if result.match_type == "none":
            assert result.note, "an empty ÖREB answer must carry a next step"

    async def test_get_egrid_resolves_a_zurich_point(self):
        result = await get_egrid(GetEgridInput(lat=ZH_LAT, lon=ZH_LON, canton="ZH"))
        assert result.is_error is False, result.summary
        # An empty answer is legitimate on a parcel boundary, so the contract
        # assertion is on the envelope, not on finding a parcel.
        assert result.source == OEREB_SOURCE
        assert result.match_type in {"exact", "none"}
        if result.results:
            egrid = result.results[0].get("egrid")
            assert isinstance(egrid, str) and egrid, "EGRID field shape changed"

    async def test_oereb_at_returns_one_call_answer(self):
        """The aggregate is the tool a caller should reach for; if the chain it
        collapses breaks upstream, this is where it shows."""
        result = await oereb_at(OerebAtInput(lat=ZH_LAT, lon=ZH_LON, canton="ZH"))
        assert result.is_error is False, result.summary
        assert result.source == OEREB_SOURCE
        assert result.license == OEREB_LICENSE
        assert result.match_type in {"exact", "none"}
        if result.match_type == "none":
            assert result.note, "an empty ÖREB answer must carry a next step"

    async def test_get_oereb_extract_accepts_a_resolved_egrid(self):
        """Chained on purpose: a hardcoded EGRID would rot, and resolving it
        first is also what exercises the pair the aggregate replaced."""
        located = await get_egrid(GetEgridInput(lat=ZH_LAT, lon=ZH_LON, canton="ZH"))
        if not located.results:
            pytest.skip("no parcel at the probe point today")
        egrid = located.results[0]["egrid"]
        result = await get_oereb_extract(GetOerebExtractInput(egrid=egrid, canton="ZH"))
        assert result.is_error is False, result.summary
        assert result.source == OEREB_SOURCE

    async def test_topics_filter_narrows_a_real_extract(self):
        """The filter runs on our side, so only a live extract proves it picks
        the right restrictions out of real cantonal data — and that the theme
        codes it matches on are the ones the service actually sends."""
        located = await get_egrid(GetEgridInput(lat=ZH_LAT, lon=ZH_LON, canton="ZH"))
        if not located.results:
            pytest.skip("no parcel at the probe point today")
        egrid = located.results[0]["egrid"]

        full = await get_oereb_extract(GetOerebExtractInput(egrid=egrid, canton="ZH"))
        if full.match_type != "exact":
            pytest.skip("parcel carries no restrictions today")

        codes = {r["theme_code"] for r in full.results if r["theme_code"]}
        assert codes, "restrictions arrived without a theme code — filter key gone"

        one = sorted(codes)[0]
        narrowed = await get_oereb_extract(
            GetOerebExtractInput(egrid=egrid, canton="ZH", topics=one)
        )
        assert narrowed.is_error is False, narrowed.summary
        assert 0 < narrowed.count <= full.count
        assert {r["theme_code"] for r in narrowed.results} == {one}

    async def test_unknown_topic_reports_the_real_ones(self):
        """A filter that matches nothing must not look like a clean parcel."""
        located = await get_egrid(GetEgridInput(lat=ZH_LAT, lon=ZH_LON, canton="ZH"))
        if not located.results:
            pytest.skip("no parcel at the probe point today")
        result = await get_oereb_extract(
            GetOerebExtractInput(
                egrid=located.results[0]["egrid"],
                canton="ZH",
                topics="ch.GibtEsNicht",
            )
        )
        assert result.is_error is False
        assert result.match_type == "none"
        assert result.note and "ch." in result.note, (
            "an empty filter result must name the themes that do exist"
        )

    async def test_unsupported_canton_fails_cleanly(self):
        """Not an upstream call — but it pins the behaviour a caller hits almost
        everywhere in Switzerland, since only ZH is enabled by default."""
        result = await get_egrid(GetEgridInput(lat=46.95, lon=7.45, canton="XX"))
        assert result.is_error is True
        assert "ZH" in result.summary


# ---------------------------------------------------------------------------
# Endpoint registry cross-check (live)
#
# The canton ZH outage was visible in federal data before it was visible here:
# `oereb.geo.zh.ch` had already stopped being what the Confederation published
# as the ZH service, and the tools only found out when the name stopped
# resolving. The layer `ch.swisstopo-vd.stand-oerebkataster` carries the
# current cantonal ÖREB web service per municipality in `oereb_webservice`.
#
# Comparing `OEREB_ENDPOINTS` against it turns "a canton moved" into a failure
# that names the new URL, instead of a connection error whose cause has to be
# dug out. It is a *different* signal from the other live tests here: those go
# red once the old endpoint dies, this one goes red the day the registry
# starts pointing somewhere else — which is earlier, and actionable.
# ---------------------------------------------------------------------------

_REGISTRY_LAYER = "ch.swisstopo-vd.stand-oerebkataster"

# The registry names each canton in its own official language ('Ticino', not
# 'Tessin'; 'Genève', not 'Genf') and carries no canton-code field to search on
# instead, so the mapping has to be spelled out. All 26 were checked against
# the live layer when this table was written — every one of them resolves to
# exactly one `oereb_webservice`.
CANTON_REGISTRY_NAMES: dict[str, str] = {
    "AG": "Aargau",
    "AI": "Appenzell Innerrhoden",
    "AR": "Appenzell Ausserrhoden",
    "BE": "Bern",
    "BL": "Basel-Landschaft",
    "BS": "Basel-Stadt",
    "FR": "Fribourg",
    "GE": "Genève",
    "GL": "Glarus",
    "GR": "Graubünden",
    "JU": "Jura",
    "LU": "Luzern",
    "NE": "Neuchâtel",
    "NW": "Nidwalden",
    "OW": "Obwalden",
    "SG": "St. Gallen",
    "SH": "Schaffhausen",
    "SO": "Solothurn",
    "SZ": "Schwyz",
    "TG": "Thurgau",
    "TI": "Ticino",
    "UR": "Uri",
    "VD": "Vaud",
    "VS": "Valais",
    "ZG": "Zug",
    "ZH": "Zürich",
}


async def _published_oereb_services(canton_name: str) -> set[str]:
    """The distinct `oereb_webservice` URLs the registry lists for a canton."""
    from swisstopo_mcp.api_client import geo_admin_request

    payload = await geo_admin_request(
        "/rest/services/api/MapServer/find",
        {
            "layer": _REGISTRY_LAYER,
            "searchField": "kanton",
            "searchText": canton_name,
            # Without this, 'Basel-Stadt' also matches 'Basel-Landschaft'.
            "contains": "false",
            "returnGeometry": "false",
        },
    )
    return {
        url
        for result in payload.get("results", [])
        if isinstance(result, dict)
        for url in [result.get("attributes", {}).get("oereb_webservice")]
        if url
    }


def _covers(configured: str, published: str) -> bool:
    """True when `published` is our base URL, or a call sitting below it.

    Not a bare `startswith`: some cantons publish a complete example request
    (`…/oereb/extract/xml?EGRID=…`) rather than the base, which is still the
    same service — but `…/oereb/v20` must not count as a match for
    `…/oereb/v2`, so the next character has to be a separator.
    """
    if published == configured:
        return True
    return published.startswith(configured) and published[len(configured)] in "/?"


class TestCantonRegistryNames:
    """Not a network test — it makes the live one below impossible to skip by
    accident. A canton added to OEREB_ENDPOINTS without a registry name would
    otherwise silently drop out of the cross-check."""

    def test_every_configured_canton_has_a_registry_name(self):
        missing = set(OEREB_ENDPOINTS) - set(CANTON_REGISTRY_NAMES)
        assert not missing, (
            f"Kein Registry-Name für {sorted(missing)}. Der Name ist der der "
            "Kanton im Feld `kanton` von ch.swisstopo-vd.stand-oerebkataster "
            "trägt — in seiner eigenen Amtssprache."
        )

    def test_table_covers_all_twenty_six_cantons(self):
        assert len(CANTON_REGISTRY_NAMES) == 26


@pytest.mark.live
class TestOerebEndpointRegistryLive:
    @pytest.mark.parametrize("canton", sorted(OEREB_ENDPOINTS))
    async def test_endpoint_matches_what_the_confederation_publishes(self, canton):
        published = await _published_oereb_services(CANTON_REGISTRY_NAMES[canton])
        assert published, (
            f"Die Registry liefert für {canton} kein `oereb_webservice`. "
            f"Entweder heisst das Feld in {_REGISTRY_LAYER} nicht mehr so, "
            "oder der Kanton ist dort nicht mehr geführt."
        )

        configured = OEREB_ENDPOINTS[canton].rstrip("/")
        assert any(_covers(configured, url.rstrip("/")) for url in published), (
            f"Kanton {canton} ist umgezogen. Konfiguriert: {configured}. "
            f"Publiziert: {sorted(published)}. OEREB_ENDPOINTS in oereb.py "
            "nachführen — und, falls sich der Host ändert, ALLOWED_HOSTS in "
            "api_client.py, docs/network-egress.md sowie "
            "deploy/smokescreen-acl.yaml (via scripts/render_egress_acl.py)."
        )


# ---------------------------------------------------------------------------
# Other cantonal ÖREB implementations
#
# ZH and BE are the two cantons this server ships, and both are bespoke. The
# other 24 run four further stacks — `pyramid_oereb` (GR, SG, AR, AI, GL),
# `RdppfSVC.svc` (VD, GE, FR), `crdppf` (NE, JU) and further one-offs (AG, ZG,
# …). The parser's tolerance across those was never established, only hoped for.
#
# It was probed against live responses, one canton per family. Four of the five
# parse unmodified; the payloads below are their real answers, trimmed to the
# part that carries the envelope shape. They are here so that adding one of
# those cantons is a registry entry rather than a debugging session.
#
# The fifth is a documented gap — see TestRdppfSvcFamilyIsNotSupported.
# ---------------------------------------------------------------------------

# Trimmed from live `/extract/json/` responses, one canton per parsing family.
_OTHER_CANTON_EXTRACTS = {
    "GR (pyramid_oereb)": {'GetExtractByIdResponse': {'extract': {'RealEstate': {'RestrictionOnLandownership': [{'Theme': {'Code': 'ch.GR.NutzungsplanungZpGgp',
                                                                                                     'Text': [{'Language': 'de',
                                                                                                               'Text': 'Kommunale '
                                                                                                                       'Nutzungsplanung '
                                                                                                                       '- '
                                                                                                                       'Zonenplan '
                                                                                                                       'und '
                                                                                                                       'Genereller '
                                                                                                                       'Gestaltungsplan'}]},
                                                                                           'LegendText': [{'Language': 'de',
                                                                                                           'Text': 'Mühlbach '
                                                                                                                   'überdeckt '
                                                                                                                   'mit '
                                                                                                                   'gestalterischem '
                                                                                                                   'Aufwertungspotential'}],
                                                                                           'Lawstatus': {'Code': 'inForce',
                                                                                                         'Text': [{'Language': 'de',
                                                                                                                   'Text': 'Rechtskräftig'}]},
                                                                                           'ResponsibleOffice': {'Name': [{'Language': 'de',
                                                                                                                           'Text': 'Stadt '
                                                                                                                                   'Chur, '
                                                                                                                                   'Abteilung '
                                                                                                                                   'Stadtentwicklung'}],
                                                                                                                 'OfficeAtWeb': [{'Language': 'de',
                                                                                                                                  'Text': 'https://www.chur.ch'}]},
                                                                                           'LegalProvisions': [{'Title': [{'Language': 'de',
                                                                                                                           'Text': 'Gesamtrevision '
                                                                                                                                   '(3901_B_OPTO_03072007_RB.PDF)'}]}]}]}}}},
    "SG (pyramid_oereb)": {'GetExtractByIdResponse': {'extract': {'RealEstate': {'RestrictionOnLandownership': [{'Theme': {'Code': 'ch.Nutzungsplanung',
                                                                                                     'Text': [{'Language': 'de',
                                                                                                               'Text': 'Nutzungsplanung '
                                                                                                                       'Zonenplan'}]},
                                                                                           'LegendText': [{'Language': 'de',
                                                                                                           'Text': 'BauG '
                                                                                                                   'Bestimmte '
                                                                                                                   'Nutzungsart '
                                                                                                                   'Art '
                                                                                                                   '28oct'}],
                                                                                           'Lawstatus': {'Code': 'inForce',
                                                                                                         'Text': [{'Language': 'de',
                                                                                                                   'Text': 'Rechtskräftig'}]},
                                                                                           'ResponsibleOffice': {'Name': [{'Language': 'de',
                                                                                                                           'Text': 'Stadt '
                                                                                                                                   'St.Gallen'}],
                                                                                                                 'OfficeAtWeb': [{'Language': 'de',
                                                                                                                                  'Text': 'https://www.stadt.sg.ch'}],
                                                                                                                 'Street': 'Rathaus',
                                                                                                                 'Number': 'nan',
                                                                                                                 'PostalCode': '9001',
                                                                                                                 'City': 'St.Gallen'},
                                                                                           'AreaShare': 3850,
                                                                                           'PartInPercent': 94.1,
                                                                                           'LegalProvisions': [{'Title': [{'Language': 'de',
                                                                                                                           'Text': 'Teilzonenplan '
                                                                                                                                   'Nutzungsplan '
                                                                                                                                   'Altstadt '
                                                                                                                                   '- '
                                                                                                                                   'Genehmigung'}]}]}]}}}},
    "NE (crdppf)": {'GetExtractByIdResponse': {'extract': {'RealEstate': {'RestrictionOnLandownership': [{'Theme': {'Code': 'ch.Nutzungsplanung',
                                                                                                     'Text': [{'Language': 'de',
                                                                                                               'Text': 'Nutzungsplanung '
                                                                                                                       '(kantonal/kommunal)'}]},
                                                                                           'LegendText': [{'Language': 'fr',
                                                                                                           'Text': 'Zone '
                                                                                                                   "d'utilité "
                                                                                                                   'publique'}],
                                                                                           'Lawstatus': {'Code': 'inForce',
                                                                                                         'Text': [{'Language': 'de',
                                                                                                                   'Text': 'Rechtskräftig'}]},
                                                                                           'ResponsibleOffice': {'Name': [{'Language': 'fr',
                                                                                                                           'Text': 'Service '
                                                                                                                                   'de '
                                                                                                                                   "l'aménagement "
                                                                                                                                   'du '
                                                                                                                                   'territoire'}],
                                                                                                                 'OfficeAtWeb': [{'Language': 'fr',
                                                                                                                                  'Text': 'https://www.ne.ch/scat'}],
                                                                                                                 'Street': 'Rue '
                                                                                                                           'de '
                                                                                                                           'Tivoli',
                                                                                                                 'Number': '5',
                                                                                                                 'PostalCode': '2002',
                                                                                                                 'City': 'Neuchâtel'},
                                                                                           'AreaShare': 3051,
                                                                                           'PartInPercent': 100.0,
                                                                                           'LegalProvisions': [{'Title': [{'Language': 'fr',
                                                                                                                           'Text': 'Loi '
                                                                                                                                   'cantonale '
                                                                                                                                   'sur '
                                                                                                                                   'la '
                                                                                                                                   'sauvegarde '
                                                                                                                                   'du '
                                                                                                                                   'patrimoine '
                                                                                                                                   'culturel'}]}]}]}}}},
    "AG (Eigenbau)": {'GetExtractByIdResponse': {'extract': {'RealEstate': {'RestrictionOnLandownership': [{'Theme': {'Code': 'ch.Nutzungsplanung',
                                                                                                     'Text': [{'Language': 'de',
                                                                                                               'Text': 'Nutzungsplanung '
                                                                                                                       '(kantonal/kommunal)'}]},
                                                                                           'LegendText': [{'Language': 'de',
                                                                                                           'Text': 'Totalrevision '
                                                                                                                   'Erschliessungspläne '
                                                                                                                   'Plan '
                                                                                                                   'Nr. '
                                                                                                                   '11'}],
                                                                                           'Lawstatus': {'Code': 'inForce',
                                                                                                         'Text': [{'Language': 'de',
                                                                                                                   'Text': 'Rechtskräftig'}]},
                                                                                           'ResponsibleOffice': {'Name': [{'Language': 'de',
                                                                                                                           'Text': 'Aarau'}],
                                                                                                                 'OfficeAtWeb': [{'Language': 'de',
                                                                                                                                  'Text': 'http://www.aarau.ch'}]},
                                                                                           'AreaShare': 112,
                                                                                           'PartInPercent': 100.0,
                                                                                           'LegalProvisions': [{'Title': [{'Language': 'de',
                                                                                                                           'Text': 'Bundesgesetz '
                                                                                                                                   'über '
                                                                                                                                   'die '
                                                                                                                                   'Raumplanung'}]}]}]}}}},
}

# Trimmed from a live `/getegrid/json/` response.
_GR_EGRID_PAYLOAD = {"GetEGRIDResponse": [{'egrid': 'CH716823867719',
     'number': '6914',
     'identDN': 'GR0000003901',
     'type': {'Code': 'RealEstate',
              'Text': [{'Language': 'de', 'Text': 'Liegenschaft'},
                       {'Language': 'it', 'Text': 'Bene immobile'},
                       {'Language': 'rm', 'Text': 'Bain immobigliar'}]}}]}


class TestOtherCantonalImplementationsParse:
    """Four of the five further implementation families need no code change.

    Recorded rather than invented: an invented payload is what let the original
    envelope bug through, and finding out what these services actually send was
    the entire point of the probe.
    """

    @pytest.mark.parametrize("family", sorted(_OTHER_CANTON_EXTRACTS))
    def test_extract_envelope_is_understood(self, family):
        from swisstopo_mcp.oereb import _parse_restrictions, _restriction_record

        restrictions = _parse_restrictions(_OTHER_CANTON_EXTRACTS[family])
        assert restrictions, f"{family}: envelope not recognised"

        record = _restriction_record(restrictions[0])
        assert record["theme_code"], f"{family}: no theme code — filtering impossible"
        assert record["legend_text"] or record["theme"], f"{family}: nothing to show"

    def test_pyramid_oereb_getegrid_is_understood(self):
        from swisstopo_mcp.oereb import _parse_egrid_payload

        records = _parse_egrid_payload(_GR_EGRID_PAYLOAD)
        assert records and records[0]["egrid"].startswith("CH")


class TestRdppfSvcFamilyIsNotSupported:
    """VD, GE and FR run `RdppfSVC.svc`, and it diverges twice.

    Pinned as a *known gap* rather than fixed. Half-support that looks complete
    is worse than none: whoever adds a Romandy canton has to handle both of
    these plus whatever the extract side does — the VD probe answered HTTP 500 —
    and is better served discovering it here than from an empty result in
    production. Adding a canton is a deliberate act anyway (OEREB_ENDPOINTS,
    ALLOWED_HOSTS, the egress ACL, docs/network-egress.md).
    """

    # Trimmed from a live VD `/getegrid/json/` response.
    ITEM_PAYLOAD = {"Item": [{'egrid': 'CH738308453444',
         'number': 'DP 905',
         'identDN': 'VD0132000000',
         'type': {'Code': 0, 'Text': [{'Language': 1, 'Text': 'Bien-fonds'}]},
         'limit': None}]}

    def test_the_item_envelope_is_not_read(self):
        from swisstopo_mcp.oereb import _parse_egrid_payload

        assert _parse_egrid_payload(self.ITEM_PAYLOAD) == [], (
            "the RdppfSVC family now parses — good, but then this test and the "
            "comment above it are stale, and those cantons can be registered"
        )

    def test_the_language_tag_is_numeric_not_a_code(self):
        """The second divergence, and the subtler one: this family tags language
        as an integer, so `_localized_text` can never match a requested `de`/`fr`
        and falls back to the first entry. On a bilingual canton that is a
        mistranslation rather than a missing value."""
        from swisstopo_mcp.oereb import _localized_text

        entry = self.ITEM_PAYLOAD["Item"][0]["type"]
        assert entry["Text"][0]["Language"] == 1
        # Text still comes out — via the fallback, not via a language match.
        assert _localized_text(entry, "de")
