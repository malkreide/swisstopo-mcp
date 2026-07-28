# src/swisstopo_mcp/oereb.py
"""ÖREB Cadastre tools for cantonal ÖREB services."""
from __future__ import annotations

from mcp.server.fastmcp import Context
from pydantic import BaseModel, ConfigDict, Field

from swisstopo_mcp.api_client import (
    CANTON_PATTERN,
    LANG_PATTERN,
    _get_client,
    assert_host_allowed,
    handle_api_error,
)
from swisstopo_mcp.config import settings
from swisstopo_mcp.coords import SwissPointInput
from swisstopo_mcp.logging_config import log_tool_call
from swisstopo_mcp.models import OEREB_LICENSE, OEREB_SOURCE, ToolResponse

# ---------------------------------------------------------------------------
# Canton Registry
# ---------------------------------------------------------------------------

OEREB_ENDPOINTS: dict[str, str] = {
    "ZH": "https://oereb.geo.zh.ch",
    "BE": "https://www.oereb2.apps.be.ch",
}


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
        ..., min_length=5, max_length=30, pattern=r"^[A-Za-z0-9]+$",
        description="EGRID (z.B. 'CH767982496078')",
    )
    canton: str = Field(
        ..., min_length=2, max_length=2, pattern=CANTON_PATTERN, description="Kantonskürzel"
    )
    topics: str | None = Field(
        default=None, max_length=200, pattern=r"^[\w,\-]+$", description="Themenfilter (kommagetrennt)"
    )
    lang: str = Field(default="de", pattern=LANG_PATTERN, description="Sprache")


# ---------------------------------------------------------------------------
# Async Handler Functions
# ---------------------------------------------------------------------------


async def _fetch_egrid_features(base: str, easting: float, northing: float) -> list[dict]:
    """Resolve an LV95 point to its parcel feature(s) at a cantonal ÖREB endpoint.

    Shared by `swisstopo_get_egrid` and `swisstopo_oereb_at` so the one-call
    aggregate does not re-enter the tool layer to reach it (ARCH-007).
    """
    url = f"{base}/getegrid/json/?EN={easting},{northing}"
    assert_host_allowed(url)
    async with await _get_client() as client:
        response = await client.get(url)
        response.raise_for_status()
        data = response.json()
    features = data.get("features", [])
    return features if isinstance(features, list) else []


def _first_egrid(features: list[dict]) -> str | None:
    """Pull the EGRID out of the first feature, tolerating key-case variation."""
    for feature in features:
        props = feature.get("properties", {})
        egrid = props.get("egrid") or props.get("EGRID")
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
        features = await _fetch_egrid_features(base, *params.as_lv95)
        if not features:
            return ToolResponse.ok(
                f"Kein EGRID gefunden für Koordinaten "
                f"({lat}, {lon}) in Kanton {canton}.",
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
        records = []
        for feature in features:
            props = feature.get("properties", {})
            egrid = props.get("egrid", props.get("EGRID", "?"))
            municipality = props.get(
                "gemeindename", props.get("municipality", props.get("Gemeinde", "?"))
            )
            lines.append(f"EGRID: {egrid} (Gemeinde: {municipality})")
            records.append({"egrid": egrid, "municipality": municipality})

        return ToolResponse.ok(
            "\n".join(lines),
            records,
            match_type="exact",
            source=OEREB_SOURCE,
            license=OEREB_LICENSE,
        )

    except Exception as e:
        return ToolResponse.error(handle_api_error(e, f"EGRID-Abfrage Kanton {canton}"), source=OEREB_SOURCE)


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
        url = f"{base}/extract/json/?EGRID={params.egrid}&GEOMETRY=false&LANG={params.lang}"
        if params.topics:
            url += f"&TOPICS={params.topics}"

        assert_host_allowed(url)
        async with await _get_client() as client:
            response = await client.get(url)
            if response.status_code == 404:
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
            response.raise_for_status()
            data = response.json()

        # Parse restriction topics from response
        extract = data.get("GetExtractByIdResponse", data.get("extract", data))
        if isinstance(extract, dict):
            real_state = extract.get("RealEstate", extract)
            restriction_measures = real_state.get("RestrictionOnLandownership", [])
        else:
            restriction_measures = []

        if not restriction_measures:
            return ToolResponse.ok(
                f"## ÖREB-Auszug für {params.egrid}\n\nKeine Eigentumsbeschränkungen gefunden.",
                [],
                match_type="none",
                note=(
                    "Kein Treffer heisst hier: für dieses Grundstück sind in den "
                    "abgefragten Themen keine Beschränkungen eingetragen. Ohne "
                    "topics-Filter erneut abfragen, um alle Themen abzudecken."
                ),
                source=OEREB_SOURCE,
                license=OEREB_LICENSE,
            )

        # Group by topic
        topics_grouped: dict[str, list[dict]] = {}
        for restriction in restriction_measures:
            topic = restriction.get("Topic", restriction.get("theme", "Unbekannt"))
            if isinstance(topic, dict):
                topic = topic.get("Text", topic.get("text", "Unbekannt"))
            topics_grouped.setdefault(topic, []).append(restriction)

        lines = [f"## ÖREB-Auszug für {params.egrid}", ""]
        for topic_name, restrictions in topics_grouped.items():
            lines.append(f"### {topic_name}")
            for r in restrictions:
                information = r.get("Information", r.get("information", []))
                description = ""
                if isinstance(information, list) and information:
                    first_info = information[0]
                    if isinstance(first_info, dict):
                        description = str(first_info.get("Text") or first_info.get("text") or "")
                elif isinstance(information, str):
                    description = information

                authority_obj = r.get("ResponsibleOffice", r.get("authority", {}))
                authority = ""
                if isinstance(authority_obj, dict):
                    authority_names = authority_obj.get("Name", authority_obj.get("name", []))
                    if isinstance(authority_names, list) and authority_names:
                        first_name = authority_names[0]
                        if isinstance(first_name, dict):
                            authority = str(first_name.get("Text") or first_name.get("text") or "")
                        else:
                            authority = str(first_name)
                    elif isinstance(authority_names, str):
                        authority = authority_names

                legal_provisions = r.get("LegalProvisions", r.get("legalProvisions", []))
                legal_text = ""
                if isinstance(legal_provisions, list) and legal_provisions:
                    first_lp = legal_provisions[0]
                    if isinstance(first_lp, dict):
                        lp_titles = first_lp.get("Title", first_lp.get("title", []))
                        if isinstance(lp_titles, list) and lp_titles:
                            first_title = lp_titles[0]
                            if isinstance(first_title, dict):
                                legal_text = str(first_title.get("Text") or first_title.get("text") or "")
                            else:
                                legal_text = str(first_title)
                        elif isinstance(lp_titles, str):
                            legal_text = lp_titles

                if description:
                    lines.append(f"- **Beschreibung:** {description}")
                if authority:
                    lines.append(f"- **Zuständige Stelle:** {authority}")
                if legal_text:
                    lines.append(f"- **Rechtliche Grundlage:** {legal_text}")
            lines.append("")

        return ToolResponse.ok(
            "\n".join(lines).rstrip(),
            list(restriction_measures),
            match_type="exact",
            source=OEREB_SOURCE,
            license=OEREB_LICENSE,
        )

    except Exception as e:
        return ToolResponse.error(handle_api_error(e, f"ÖREB-Auszug Kanton {canton}"), source=OEREB_SOURCE)


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
        default=None,
        max_length=200,
        pattern=r"^[\w,\-]+$",
        description="Themenfilter (kommagetrennt)",
    )
    lang: str = Field(default="de", pattern=LANG_PATTERN, description="Sprache")


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
        features = await _fetch_egrid_features(base, *params.as_lv95)
        egrid = _first_egrid(features)
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
        GetOerebExtractInput(
            egrid=egrid, canton=canton, topics=params.topics, lang=params.lang
        ),
        ctx=ctx,
    )
