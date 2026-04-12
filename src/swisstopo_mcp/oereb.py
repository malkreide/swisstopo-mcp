# src/swisstopo_mcp/oereb.py
"""ÖREB Cadastre tools for cantonal ÖREB services."""
from __future__ import annotations

import os

from pydantic import BaseModel, ConfigDict, Field

from swisstopo_mcp.api_client import _get_client, handle_api_error, wgs84_to_lv95

# ---------------------------------------------------------------------------
# Canton Registry
# ---------------------------------------------------------------------------

OEREB_ENDPOINTS: dict[str, str] = {
    "ZH": "https://oereb.geo.zh.ch",
    "BE": "https://www.oereb2.apps.be.ch",
}


def get_active_cantons() -> dict[str, str]:
    """Return ÖREB endpoints filtered by SWISSTOPO_OEREB_CANTONS env var."""
    cantons_env = os.environ.get("SWISSTOPO_OEREB_CANTONS", "ZH")
    active = [c.strip().upper() for c in cantons_env.split(",")]
    return {k: v for k, v in OEREB_ENDPOINTS.items() if k in active}


def get_oereb_endpoint(canton: str) -> str | None:
    """Get ÖREB endpoint URL for a canton, or None if not available."""
    return get_active_cantons().get(canton.upper())


# ---------------------------------------------------------------------------
# Input Models
# ---------------------------------------------------------------------------


class GetEgridInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    lat: float = Field(..., ge=45.8, le=47.9, description="Breitengrad (WGS84)")
    lon: float = Field(..., ge=5.9, le=10.5, description="Längengrad (WGS84)")
    canton: str = Field(
        ..., min_length=2, max_length=2, description="Kantonskürzel (z.B. 'ZH', 'BE')"
    )


class GetOerebExtractInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    egrid: str = Field(..., min_length=5, description="EGRID (z.B. 'CH767982496078')")
    canton: str = Field(..., min_length=2, max_length=2, description="Kantonskürzel")
    topics: str | None = Field(default=None, description="Themenfilter (kommagetrennt)")
    lang: str = Field(default="de", description="Sprache")


# ---------------------------------------------------------------------------
# Async Handler Functions
# ---------------------------------------------------------------------------


async def get_egrid(params: GetEgridInput) -> str:
    """Return the EGRID (parcel identifier) for a WGS84 coordinate in a given canton."""
    canton = params.canton.upper()
    base = get_oereb_endpoint(canton)
    if base is None:
        available = list(get_active_cantons().keys())
        return (
            f"⚠️ Kanton {canton} wird nicht unterstützt. "
            f"Verfügbar: {available}. "
            f"Manueller Auszug: https://oereb.cadastre.ch"
        )

    try:
        e, n = wgs84_to_lv95(params.lat, params.lon)
        url = f"{base}/getegrid/json/?EN={e},{n}"
        async with await _get_client() as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()

        # Parse EGRID(s) from response
        features = data.get("features", [])
        if not features:
            return (
                f"Kein EGRID gefunden für Koordinaten "
                f"({params.lat}, {params.lon}) in Kanton {canton}."
            )

        results = []
        for feature in features:
            props = feature.get("properties", {})
            egrid = props.get("egrid", props.get("EGRID", "?"))
            municipality = props.get(
                "gemeindename", props.get("municipality", props.get("Gemeinde", "?"))
            )
            results.append(f"EGRID: {egrid} (Gemeinde: {municipality})")

        return "\n".join(results)

    except Exception as e:
        return handle_api_error(e, f"EGRID-Abfrage Kanton {canton}")


async def get_oereb_extract(params: GetOerebExtractInput) -> str:
    """Return ÖREB restrictions for a parcel identified by EGRID."""
    canton = params.canton.upper()
    base = get_oereb_endpoint(canton)
    if base is None:
        available = list(get_active_cantons().keys())
        return (
            f"⚠️ Kanton {canton} wird nicht unterstützt. "
            f"Verfügbar: {available}. "
            f"Manueller Auszug: https://oereb.cadastre.ch"
        )

    try:
        url = f"{base}/extract/json/?EGRID={params.egrid}&GEOMETRY=false&LANG={params.lang}"
        if params.topics:
            url += f"&TOPICS={params.topics}"

        async with await _get_client() as client:
            response = await client.get(url)
            if response.status_code == 404:
                return f"EGRID '{params.egrid}' nicht gefunden in Kanton {canton}."
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
            return f"## ÖREB-Auszug für {params.egrid}\n\nKeine Eigentumsbeschränkungen gefunden."

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
                        description = first_info.get("Text", first_info.get("text", ""))
                elif isinstance(information, str):
                    description = information

                authority_obj = r.get("ResponsibleOffice", r.get("authority", {}))
                authority = ""
                if isinstance(authority_obj, dict):
                    authority_names = authority_obj.get("Name", authority_obj.get("name", []))
                    if isinstance(authority_names, list) and authority_names:
                        first_name = authority_names[0]
                        if isinstance(first_name, dict):
                            authority = first_name.get("Text", first_name.get("text", ""))
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
                                legal_text = first_title.get("Text", first_title.get("text", ""))
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

        return "\n".join(lines).rstrip()

    except Exception as e:
        return handle_api_error(e, f"ÖREB-Auszug Kanton {canton}")
