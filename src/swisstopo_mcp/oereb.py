# src/swisstopo_mcp/oereb.py
"""ÖREB Cadastre tools for cantonal ÖREB services."""

from __future__ import annotations

import httpx
from mcp.server.mcpserver import Context
from pydantic import BaseModel, ConfigDict, Field

from swisstopo_mcp.api_client import (
    CANTON_PATTERN,
    LANG_PATTERN,
    handle_api_error,
    request_with_retry,
)
from swisstopo_mcp.config import settings
from swisstopo_mcp.coords import SwissPointInput
from swisstopo_mcp.logging_config import log_tool_call
from swisstopo_mcp.models import OEREB_LICENSE, OEREB_SOURCE, ToolResponse

# ---------------------------------------------------------------------------
# Canton Registry
# ---------------------------------------------------------------------------

# Base URLs of the cantonal ÖREB web services, as published by the Confederation
# in `ch.swisstopo-vd.stand-oerebkataster` (attribute `oereb_webservice`). That
# layer is the registry to re-check when a canton moves: ZH's previous host,
# `oereb.geo.zh.ch`, stopped resolving altogether and took both ÖREB tools down
# with it.
OEREB_ENDPOINTS: dict[str, str] = {
    "ZH": "https://maps.zh.ch/oereb/v2",
    "BE": "https://www.oereb2.apps.be.ch",
}

# Per-attempt timeout for the cantonal hosts, below the retry budget on purpose.
#
# These are the only upstreams here that are neither operated by the
# Confederation nor fronted by a CDN — one canton, one machine — and they are
# the ones that go slow. Until this constant existed, ÖREB was also the only
# upstream that bypassed `request_with_retry` entirely: one attempt, no backoff,
# and a blip came back as a hard tool error.
#
# Retries alone would not have fixed that. `REQUEST_TIMEOUT` is 30s and
# `TOTAL_BUDGET_S` is 25s, so one hanging request exhausts the whole budget and
# the ladder never runs — which is exactly the failure mode a degraded cantonal
# host produces, and exactly what took a BE probe down for 30s at a stretch. A
# per-attempt bound *below* the budget is what makes the retries reachable: two
# attempts and a backoff fit inside 25s. Healthy ZH and BE answer `getegrid` and
# `extract` in 0.6-2.2s, so 10s is roughly five times the worst honest response.
OEREB_ATTEMPT_TIMEOUT = 10.0


def get_active_cantons() -> dict[str, str]:
    """Return ÖREB endpoints filtered by the configured cantons.

    Reads the shared Settings object rather than os.environ directly, so the
    value is validated once at startup and config.py stays the single source
    for every setting, as its own docstring claims (ARCH-004).
    """
    active = settings.oereb_cantons_list
    return {k: v for k, v in OEREB_ENDPOINTS.items() if k in active}


def get_oereb_endpoint(canton: str) -> str | None:
    """Get ÖREB endpoint URL for a canton, or None if not available."""
    return get_active_cantons().get(canton.upper())


# ---------------------------------------------------------------------------
# Input Models
# ---------------------------------------------------------------------------

# `swisstopo_get_oereb_extract` and `swisstopo_oereb_at` take the same themes
# filter. It was spelled out twice, which is exactly how the charset below got
# fixed on one of them and left broken on the other — one definition, two uses.
#
# The dot is not decoration: every ÖREB theme code carries one
# (`ch.Nutzungsplanung`, `ch.BE.Gewaesserschutzbereiche`). Without it the field
# rejected every valid code and accepted only `Nutzungsplanung`, which matches
# no theme — the filter could not work for any canton, and the rejection
# happened before a request was ever made. The space is here for the same
# reason: `_parse_topics` strips it from each entry, so 'a, b' parses fine, and
# a validator stricter than the code behind it buys nothing. The value no
# longer reaches any URL (see `get_oereb_extract`), so it is a pure lookup key;
# `max_length` still bounds it.
TOPICS_PATTERN = r"^[\w.,\- ]+$"
TOPICS_DESCRIPTION = (
    "Themenfilter: ÖREB-Themencode oder -Subcode, kommagetrennt "
    "(z.B. 'ch.Nutzungsplanung'). Wird clientseitig angewendet; ohne Treffer "
    "nennt die Antwort die tatsächlich vorhandenen Themen."
)


class GetEgridInput(SwissPointInput):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid", strict=True)

    canton: str = Field(
        ...,
        min_length=2,
        max_length=2,
        pattern=CANTON_PATTERN,
        description="Kantonskürzel (z.B. 'ZH', 'BE')",
    )


class GetOerebExtractInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid", strict=True)

    egrid: str = Field(
        ...,
        min_length=5,
        max_length=30,
        pattern=r"^[A-Za-z0-9]+$",
        description="EGRID (z.B. 'CH767982496078')",
    )
    canton: str = Field(
        ...,
        min_length=2,
        max_length=2,
        pattern=CANTON_PATTERN,
        description="Kantonskürzel (z.B. 'ZH', 'BE')",
    )
    topics: str | None = Field(
        default=None, max_length=200, pattern=TOPICS_PATTERN, description=TOPICS_DESCRIPTION
    )
    lang: str = Field(default="de", pattern=LANG_PATTERN, description="Sprache: de, fr, it, en")


# ---------------------------------------------------------------------------
# Async Handler Functions
# ---------------------------------------------------------------------------


def _localized_text(value: object, lang: str = "de") -> str:
    """Pull a plain string out of an ÖREB multilingual value.

    The data-extract schema wraps almost every human-readable field as a list of
    `{"Language": ..., "Text": ...}` pairs, but cantons emit the same field as a
    bare dict or a bare string often enough that only reading the list shape
    loses text. Prefer the requested language; fall back to whatever is there.
    """
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return _localized_text(value.get("Text"), lang) if "Text" in value else ""
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict) and item.get("Language") == lang and item.get("Text"):
                return str(item["Text"])
        for item in value:
            if isinstance(item, str):
                return item
            if isinstance(item, dict) and item.get("Text"):
                return str(item["Text"])
    return ""


def _egrid_record(entry: dict) -> dict | None:
    """Normalise one parcel entry to `{egrid, number, identDN, municipality}`."""
    egrid = entry.get("egrid") or entry.get("EGRID")
    if not egrid:
        return None
    record: dict = {"egrid": str(egrid)}
    number = entry.get("number") or entry.get("Number")
    if number:
        record["number"] = str(number)
    ident = entry.get("identDN") or entry.get("IdentDN")
    if ident:
        record["identDN"] = str(ident)
    municipality = (
        entry.get("gemeindename") or entry.get("municipality") or entry.get("MunicipalityName")
    )
    if municipality:
        record["municipality"] = str(municipality)
    return record


def _parse_egrid_payload(data: object) -> list[dict]:
    """Flatten a getegrid answer into parcel records.

    Two shapes reach this. `GetEGRIDResponse` is what both live cantonal
    services return today — it is the shape the ÖREB data-extract 2.0 spec
    defines. The GeoJSON `features` list is what ZH served before it moved to
    `/oereb/v2`; reading it costs three lines and is the difference between a
    canton that lags the migration working and returning nothing at all.
    """
    if not isinstance(data, dict):
        return []
    entries = data.get("GetEGRIDResponse")
    if isinstance(entries, list):
        candidates = [e for e in entries if isinstance(e, dict)]
    else:
        features = data.get("features")
        candidates = [
            f.get("properties", {})
            for f in (features if isinstance(features, list) else [])
            if isinstance(f, dict) and isinstance(f.get("properties"), dict)
        ]
    return [r for r in (_egrid_record(c) for c in candidates) if r]


async def _fetch_egrid_records(
    base: str, easting: float, northing: float, ctx: Context | None = None
) -> list[dict]:
    """Resolve an LV95 point to its parcel record(s) at a cantonal ÖREB endpoint.

    Shared by `swisstopo_get_egrid` and `swisstopo_oereb_at` so the one-call
    aggregate does not re-enter the tool layer to reach it (ARCH-007).
    """
    url = f"{base}/getegrid/json/?EN={easting},{northing}"
    response = await request_with_retry("GET", url, timeout=OEREB_ATTEMPT_TIMEOUT, ctx=ctx)
    # A point with no parcel under it answers `204 No Content` with an empty
    # body rather than a 200 carrying an empty list — and an empty body is
    # not JSON, so parsing it would turn a legitimate miss into an error.
    if response.status_code == 204 or not response.content.strip():
        return []
    return _parse_egrid_payload(response.json())


def _first_egrid(records: list[dict]) -> str | None:
    """Pull the EGRID out of the first record that carries one."""
    for record in records:
        egrid = record.get("egrid")
        if egrid:
            return str(egrid)
    return None


@log_tool_call("swisstopo_get_egrid")
async def get_egrid(params: GetEgridInput) -> ToolResponse:
    """Return the EGRID (parcel identifier) for a WGS84 coordinate in a given canton."""
    canton = params.canton.upper()
    base = get_oereb_endpoint(canton)
    if base is None:
        available = list(get_active_cantons().keys())
        return ToolResponse.error(
            f"⚠️ Kanton {canton} wird nicht unterstützt. "
            f"Verfügbar: {available}. "
            f"Manueller Auszug: https://oereb.cadastre.ch",
            source=OEREB_SOURCE,
        )

    try:
        lat, lon = params.as_wgs84
        records = await _fetch_egrid_records(base, *params.as_lv95)
        if not records:
            return ToolResponse.ok(
                f"Kein EGRID gefunden für Koordinaten ({lat}, {lon}) in Kanton {canton}.",
                [],
                match_type="none",
                note=(
                    "Die Koordinate liegt womöglich ausserhalb des Kantons oder auf "
                    "einer Parzellengrenze. Kanton via swisstopo_municipality_at "
                    "prüfen, oder den Punkt leicht verschieben."
                ),
                source=OEREB_SOURCE,
                license=OEREB_LICENSE,
            )

        lines = []
        for record in records:
            # getegrid identifies the parcel, not its municipality: the 2.0
            # answer carries the parcel number and the land-registry district
            # and no municipality name at all. Report what is actually there
            # instead of the "Gemeinde: ?" the old formatter printed.
            detail = ", ".join(
                part
                for part in (
                    f"Parzelle {record['number']}" if record.get("number") else "",
                    f"Gemeinde: {record['municipality']}" if record.get("municipality") else "",
                )
                if part
            )
            lines.append(f"EGRID: {record['egrid']}" + (f" ({detail})" if detail else ""))

        return ToolResponse.ok(
            "\n".join(lines),
            records,
            match_type="exact",
            source=OEREB_SOURCE,
            license=OEREB_LICENSE,
        )

    except Exception as e:
        return ToolResponse.error(
            handle_api_error(e, f"EGRID-Abfrage Kanton {canton}"), source=OEREB_SOURCE
        )


def _parse_restrictions(data: object) -> list[dict]:
    """Reach `RestrictionOnLandownership` inside a data-extract answer.

    The envelope is nested three deep and the middle key is not spelled the same
    everywhere: ZH answers `GetExtractByIdResponse.Extract`, BE answers
    `GetExtractByIdResponse.extract`. A `.get("RealEstate", extract)` fallback
    silently descended into the wrong node and reported every parcel in
    Switzerland as unencumbered, so each level is matched explicitly here.
    """
    if not isinstance(data, dict):
        return []
    node = data.get("GetExtractByIdResponse", data)
    if not isinstance(node, dict):
        return []
    for key in ("Extract", "extract"):
        inner = node.get(key)
        if isinstance(inner, dict):
            node = inner
            break
    real_estate = node.get("RealEstate")
    if not isinstance(real_estate, dict):
        return []
    restrictions = real_estate.get("RestrictionOnLandownership")
    return restrictions if isinstance(restrictions, list) else []


def _parse_topics(raw: str | None) -> set[str]:
    """Split the comma-separated topics filter into normalised theme codes."""
    if not raw:
        return set()
    return {part.strip().lower() for part in raw.split(",") if part.strip()}


def _matches_topics(record: dict, wanted: set[str]) -> bool:
    """True when a restriction belongs to one of the requested themes.

    Matched against both the theme code and its sub-code, because cantons
    disagree on which level carries the distinction: ZH leaves `SubCode` unset
    entirely, while BE files three different sub-codes under the single code
    `ch.Nutzungsplanung`. Filtering on the code alone would make the sub-codes
    unreachable; filtering on the sub-code alone would break ZH outright.
    """
    candidates = {
        value.lower() for value in (record.get("theme_code"), record.get("theme_subcode")) if value
    }
    return bool(candidates & wanted)


def _restriction_record(restriction: dict, lang: str = "de") -> dict:
    """Reduce one restriction to the fields a caller can act on.

    Deliberately not the raw object: a single ZH restriction carries a
    fully URL-encoded WMS GetMap request plus the complete legend of its theme,
    and eighteen of those would fill the answer with markup nobody reads.
    """
    theme = restriction.get("Theme")
    theme_text = _localized_text(theme, lang)
    theme_code = ""
    theme_subcode = ""
    if isinstance(theme, dict):
        # `Code` in the spec, `code` as ZH serves it.
        theme_code = str(theme.get("Code") or theme.get("code") or "")
        theme_subcode = str(theme.get("SubCode") or theme.get("subCode") or "")

    office = restriction.get("ResponsibleOffice")
    office_name = _localized_text(office.get("Name"), lang) if isinstance(office, dict) else ""

    provisions = restriction.get("LegalProvisions")
    titles = [
        title
        for p in (provisions if isinstance(provisions, list) else [])
        if isinstance(p, dict)
        for title in [_localized_text(p.get("Title"), lang)]
        if title
    ]

    return {
        "theme": theme_text or theme_code or "Unbekannt",
        "theme_code": theme_code,
        "theme_subcode": theme_subcode,
        "legend_text": _localized_text(
            restriction.get("LegendText") or restriction.get("Information"), lang
        ),
        "lawstatus": _localized_text(restriction.get("Lawstatus"), lang),
        "responsible_office": office_name,
        "legal_provisions": titles,
        "area_share_m2": restriction.get("AreaShare"),
        "part_in_percent": restriction.get("PartInPercent"),
    }


@log_tool_call("swisstopo_get_oereb_extract")
async def get_oereb_extract(
    params: GetOerebExtractInput, ctx: Context | None = None
) -> ToolResponse:
    """Return ÖREB restrictions for a parcel identified by EGRID."""
    canton = params.canton.upper()
    if ctx is not None:
        await ctx.info(f"Rufe ÖREB-Auszug für {params.egrid} (Kanton {canton}) ab …")
    base = get_oereb_endpoint(canton)
    if base is None:
        available = list(get_active_cantons().keys())
        return ToolResponse.error(
            f"⚠️ Kanton {canton} wird nicht unterstützt. "
            f"Verfügbar: {available}. "
            f"Manueller Auszug: https://oereb.cadastre.ch",
            source=OEREB_SOURCE,
        )

    try:
        # No TOPICS on the wire, on purpose. The parameter is honoured by some
        # cantons and ignored by others — BE filters on it, ZH returns the same
        # eighteen restrictions whatever is passed, including a nonsense value.
        # Sending it would make the filter's behaviour depend on which canton
        # the caller happens to ask about, and would leave the "your filter
        # matched nothing" case indistinguishable from "this parcel carries no
        # restrictions" wherever it *did* work. Fetching everything and
        # filtering below is uniform and keeps the full theme list in hand to
        # report back. The extra payload is ~90-210 KB, already the size of an
        # unfiltered extract.
        url = f"{base}/extract/json/?EGRID={params.egrid}&GEOMETRY=false&LANG={params.lang}"

        # An unknown EGRID is a 204 with an empty body on ZH and a 404
        # elsewhere. Both mean "no such parcel here", and neither is JSON.
        # `request_with_retry` raises on a 404 rather than returning it — that is
        # right for every other caller and wrong for this one, where the 404 is
        # an answer, so it is caught back into the same reply the 204 produces.
        try:
            response = await request_with_retry("GET", url, timeout=OEREB_ATTEMPT_TIMEOUT, ctx=ctx)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 404:
                raise
            response = exc.response
        if response.status_code in (204, 404) or not response.content.strip():
            return ToolResponse.ok(
                f"EGRID '{params.egrid}' nicht gefunden in Kanton {canton}.",
                [],
                match_type="none",
                note=(
                    f"Der EGRID {params.egrid} ist im Kanton {canton} unbekannt. "
                    "Kanton prüfen — EGRIDs sind kantonal geführt — oder den "
                    "EGRID via swisstopo_get_egrid neu ermitteln."
                ),
                source=OEREB_SOURCE,
                license=OEREB_LICENSE,
            )

        restriction_measures = _parse_restrictions(response.json())

        if not restriction_measures:
            return ToolResponse.ok(
                f"## ÖREB-Auszug für {params.egrid}\n\nKeine Eigentumsbeschränkungen gefunden.",
                [],
                match_type="none",
                note=(
                    "Kein Treffer heisst hier: für dieses Grundstück sind gar "
                    "keine Beschränkungen eingetragen — der Auszug ist leer, "
                    "unabhängig von einem Themenfilter."
                ),
                source=OEREB_SOURCE,
                license=OEREB_LICENSE,
            )

        records = [
            _restriction_record(r, params.lang) for r in restriction_measures if isinstance(r, dict)
        ]

        wanted = _parse_topics(params.topics)
        if wanted:
            matched = [r for r in records if _matches_topics(r, wanted)]
            if not matched:
                # An empty filter result must not read like an unencumbered
                # parcel — that is the same silent-wrong-answer the envelope
                # parsing produced. Name the codes that are actually on this
                # extract so the next call can be right.
                offered = sorted({code for r in records for code in (r["theme_code"],) if code})
                return ToolResponse.ok(
                    f"## ÖREB-Auszug für {params.egrid}\n\n"
                    f"Keine Beschränkung im Thema '{params.topics}'. "
                    f"Das Grundstück trägt {len(records)} Beschränkung(en) in "
                    "anderen Themen.",
                    [],
                    match_type="none",
                    note=(
                        f"Verfügbare Themen für diesen EGRID: {offered}. "
                        "Der Filter vergleicht Themencode und Subcode exakt "
                        "(Gross-/Kleinschreibung egal) — ohne `topics` erneut "
                        "abfragen, um alles zu sehen."
                    ),
                    source=OEREB_SOURCE,
                    license=OEREB_LICENSE,
                )
            records = matched

        topics_grouped: dict[str, list[dict]] = {}
        for record in records:
            topics_grouped.setdefault(record["theme"], []).append(record)

        lines = [f"## ÖREB-Auszug für {params.egrid}", ""]
        for topic_name, grouped in topics_grouped.items():
            lines.append(f"### {topic_name}")
            for r in grouped:
                # One bullet per restriction, its own attributes nested under
                # it. A theme routinely carries five or more restrictions, and
                # a flat list of `Beschreibung/Rechtsstatus/…` lines leaves no
                # way to tell which authority goes with which zone.
                head = r["legend_text"] or topic_name
                if r["lawstatus"]:
                    head += f" — {r['lawstatus']}"
                lines.append(f"- **{head}**")
                if r["area_share_m2"] is not None:
                    share = f"  - Fläche: {r['area_share_m2']} m²"
                    # Only when it carries information: cantons that do not
                    # compute the share still send the field, as a zero.
                    if r["part_in_percent"]:
                        share += f" ({r['part_in_percent']} % der Parzelle)"
                    lines.append(share)
                if r["responsible_office"]:
                    lines.append(f"  - Zuständige Stelle: {r['responsible_office']}")
                provisions = r["legal_provisions"]
                for provision in provisions[:3]:
                    lines.append(f"  - Rechtliche Grundlage: {provision}")
                # The summary shows the first three; `results` carries them all.
                # Say so rather than let the shortened list read as complete.
                if len(provisions) > 3:
                    lines.append(
                        f"  - … {len(provisions) - 3} weitere Rechtsgrundlagen "
                        "(vollständig in `results`)"
                    )
            lines.append("")

        return ToolResponse.ok(
            "\n".join(lines).rstrip(),
            records,
            match_type="exact",
            source=OEREB_SOURCE,
            license=OEREB_LICENSE,
        )

    except Exception as e:
        return ToolResponse.error(
            handle_api_error(e, f"ÖREB-Auszug Kanton {canton}"), source=OEREB_SOURCE
        )


class OerebAtInput(SwissPointInput):
    """Input for `swisstopo_oereb_at` — a point plus the canton."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid", strict=True)

    canton: str = Field(
        ...,
        min_length=2,
        max_length=2,
        pattern=CANTON_PATTERN,
        description="Kantonskürzel (z.B. 'ZH', 'BE')",
    )
    topics: str | None = Field(
        default=None, max_length=200, pattern=TOPICS_PATTERN, description=TOPICS_DESCRIPTION
    )
    lang: str = Field(default="de", pattern=LANG_PATTERN, description="Sprache: de, fr, it, en")


@log_tool_call("swisstopo_oereb_at")
async def oereb_at(params: OerebAtInput, ctx: Context | None = None) -> ToolResponse:
    """Return ÖREB restrictions at a coordinate, resolving the EGRID internally.

    The two-step chain (coordinate → EGRID → extract) was the shape the audit
    flags: the intermediate EGRID is an upstream identifier, not something the
    caller asked for (ARCH-007).
    """
    canton = params.canton.upper()
    base = get_oereb_endpoint(canton)
    if base is None:
        available = list(get_active_cantons().keys())
        return ToolResponse.error(
            f"⚠️ Kanton {canton} wird nicht unterstützt. "
            f"Verfügbar: {available}. "
            f"Manueller Auszug: https://oereb.cadastre.ch",
            source=OEREB_SOURCE,
        )

    try:
        lat, lon = params.as_wgs84
        records = await _fetch_egrid_records(base, *params.as_lv95, ctx=ctx)
        egrid = _first_egrid(records)
    except Exception as e:
        return ToolResponse.error(
            handle_api_error(e, f"ÖREB-Abfrage Kanton {canton}"), source=OEREB_SOURCE
        )

    if egrid is None:
        return ToolResponse.ok(
            f"Kein Grundstück an ({lat}, {lon}) in Kanton {canton} gefunden.",
            [],
            match_type="none",
            source=OEREB_SOURCE,
            license=OEREB_LICENSE,
            note=(
                "Die Koordinate liegt womöglich ausserhalb des Kantons oder auf "
                "einer Parzellengrenze. Kanton via swisstopo_municipality_at "
                "prüfen, oder den Punkt leicht verschieben."
            ),
        )

    return await get_oereb_extract(
        GetOerebExtractInput(egrid=egrid, canton=canton, topics=params.topics, lang=params.lang),
        ctx=ctx,
    )
