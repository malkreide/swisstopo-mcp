# src/swisstopo_mcp/overpass.py
"""OpenStreetMap POI queries via the Overpass API (Swiss instance).

Kept as a *separate* tool (not folded into ``query_geodata``) because Overpass
has fundamentally different failure semantics from the geo.admin.ch / geodienste
sources — see ``docs/geodaten-erweiterung-phase1.md``:

* Errors come back as **XML/HTML even for ``[out:json]``** requests.
* A server-side timeout returns **HTTP 200 with an embedded ``remark``**, not a
  clean HTTP error.
* The ``overpass.osm.ch`` instance exposes **no ``/api/status``**, so we rate-limit
  ourselves with a hard client timeout and result cap rather than trusting the
  server. ``overpass-api.de`` returns 406 through some egress proxies.
* Licence is ODbL (© OpenStreetMap contributors), not swisstopo OGD.
"""
from __future__ import annotations

import json
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from swisstopo_mcp.api_client import (
    OVERPASS_BASE,
    TEXT_PATTERN,
    geo_admin_request,
    handle_api_error,
    request_with_retry,
)
from swisstopo_mcp.logging_config import get_logger, log_tool_call
from swisstopo_mcp.models import OSM_LICENSE, OSM_SOURCE, ToolResponse

_log = get_logger("swisstopo_mcp.overpass")

OVERPASS_INTERPRETER = f"{OVERPASS_BASE}/api/interpreter"

# Hard client-side guards (do NOT trust the server to enforce these).
OVERPASS_SERVER_TIMEOUT = 25  # the [timeout:N] hint sent to Overpass
OVERPASS_CLIENT_TIMEOUT = 30.0  # httpx read timeout — always > server timeout
OVERPASS_MAX_RESULTS = 100  # hard cap on returned elements
OVERPASS_MAX_RADIUS = 5000  # metres

# Curated feature_type → OSM tag map (safe, no injection: values are fixed).
FEATURE_TAGS: dict[str, str] = {
    "school": '"amenity"="school"',
    "kindergarten": '"amenity"="kindergarten"',
    "university": '"amenity"="university"',
    "playground": '"leisure"="playground"',
    "park": '"leisure"="park"',
    "hospital": '"amenity"="hospital"',
    "pharmacy": '"amenity"="pharmacy"',
    "doctor": '"amenity"="doctors"',
    "restaurant": '"amenity"="restaurant"',
    "cafe": '"amenity"="cafe"',
    "supermarket": '"shop"="supermarket"',
    "bank": '"amenity"="bank"',
    "atm": '"amenity"="atm"',
    "parking": '"amenity"="parking"',
    "bus_stop": '"highway"="bus_stop"',
    "train_station": '"railway"="station"',
    "library": '"amenity"="library"',
    "sports_centre": '"leisure"="sports_centre"',
    "swimming_pool": '"leisure"="swimming_pool"',
    "toilets": '"amenity"="toilets"',
    "fuel": '"amenity"="fuel"',
}

FeatureType = Literal[
    "school", "kindergarten", "university", "playground", "park", "hospital",
    "pharmacy", "doctor", "restaurant", "cafe", "supermarket", "bank", "atm",
    "parking", "bus_stop", "train_station", "library", "sports_centre",
    "swimming_pool", "toilets", "fuel",
]


class QueryOsmFeaturesInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid", strict=True)

    feature_type: FeatureType = Field(
        ..., description="POI-Kategorie (z.B. 'school', 'playground', 'pharmacy')."
    )
    area: str = Field(
        ...,
        min_length=2,
        max_length=100,
        pattern=TEXT_PATTERN,
        description="Zentrum: 'lat,lon' (WGS84) oder ein Orts-/Adressname (wird geokodiert).",
    )
    radius_m: int = Field(
        default=500, ge=10, le=OVERPASS_MAX_RADIUS, description="Suchradius in Metern."
    )
    limit: int = Field(
        default=50, ge=1, le=OVERPASS_MAX_RESULTS, description="Max. Ergebnisanzahl."
    )


def _looks_like_point(area: str) -> bool:
    parts = area.split(",")
    if len(parts) != 2:
        return False
    try:
        float(parts[0])
        float(parts[1])
        return True
    except ValueError:
        return False


async def _resolve_area(area: str) -> tuple[float, float]:
    """Return (lat, lon) for a 'lat,lon' string or a geocoded place name."""
    if _looks_like_point(area):
        lat, lon = (float(p) for p in area.split(","))
        if not (45.8 <= lat <= 47.9 and 5.9 <= lon <= 10.5):
            raise ValueError(f"Punkt ausserhalb der Schweiz: {lat},{lon}.")
        return lat, lon
    data = await geo_admin_request(
        "/rest/services/api/SearchServer",
        {"type": "locations", "searchText": area, "limit": 1, "sr": 4326},
    )
    results = data.get("results", [])
    if not results:
        raise ValueError(f"Ort '{area}' konnte nicht geokodiert werden.")
    attrs = results[0].get("attrs", {})
    return float(attrs["lat"]), float(attrs["lon"])


def _build_query(tag: str, lat: float, lon: float, radius_m: int, limit: int) -> str:
    around = f"(around:{radius_m},{lat},{lon})"
    return (
        f"[out:json][timeout:{OVERPASS_SERVER_TIMEOUT}];"
        f"(node[{tag}]{around};way[{tag}]{around};relation[{tag}]{around};);"
        f"out center tags {limit};"
    )


def _extract_error(text: str) -> str | None:
    """Overpass returns errors as XML/HTML even for [out:json]. Pull the message."""
    lowered = text.lstrip().lower()
    if lowered.startswith("{"):
        return None  # looks like JSON, not an error page
    matches = re.findall(r"<strong[^>]*>\s*Error\s*</strong>\s*:?\s*([^<]+)", text)
    if matches:
        return "; ".join(m.strip() for m in matches)
    if "error" in lowered:
        return text.strip()[:300]
    return None


@log_tool_call("query_osm_features")
async def query_osm_features(params: QueryOsmFeaturesInput) -> ToolResponse:
    """Query OpenStreetMap POIs around a point via Overpass (ODbL)."""
    try:
        tag = FEATURE_TAGS[params.feature_type]
        lat, lon = await _resolve_area(params.area)
        query = _build_query(tag, lat, lon, params.radius_m, params.limit)

        try:
            response = await request_with_retry(
                "POST",
                OVERPASS_INTERPRETER,
                content=f"data={query}",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=OVERPASS_CLIENT_TIMEOUT,
            )
        except Exception as exc:  # noqa: BLE001 — degrade gracefully
            return ToolResponse.error(
                _degraded(handle_api_error(exc, "Overpass-Abfrage")),
                source=OSM_SOURCE,
            )

        text = response.text
        err = _extract_error(text)
        if err is not None:
            return ToolResponse.error(
                _degraded(f"Overpass-Fehler: {err}"), source=OSM_SOURCE
            )
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return ToolResponse.error(
                _degraded("Overpass lieferte keine gültige JSON-Antwort."), source=OSM_SOURCE
            )

        # A server-side timeout returns HTTP 200 + an embedded 'remark'.
        remark = data.get("remark", "")
        if remark and ("timed out" in remark.lower() or "runtime error" in remark.lower()):
            return ToolResponse.error(
                _degraded(f"Overpass-Laufzeitfehler: {remark.strip()}"), source=OSM_SOURCE
            )

        elements = data.get("elements", [])[: params.limit]
        records = []
        for el in elements:
            tags = el.get("tags", {})
            center = el.get("center") or {}
            records.append(
                {
                    "osm_type": el.get("type"),
                    "osm_id": el.get("id"),
                    "name": tags.get("name") or "(ohne Name)",
                    "lat": el.get("lat") or center.get("lat"),
                    "lon": el.get("lon") or center.get("lon"),
                    "tags": tags,
                }
            )

        summary = _format(params, lat, lon, records, remark)
        return ToolResponse.ok(
            summary, records, match_type="exact" if records else "none",
            source=OSM_SOURCE, license=OSM_LICENSE,
        )
    except Exception as e:  # noqa: BLE001
        return ToolResponse.error(handle_api_error(e, "query_osm_features"), source=OSM_SOURCE)


def _degraded(detail: str) -> str:
    return (
        f"{detail}\n\n"
        "Overpass ist die fragilste Quelle (Rate-Limits/Timeouts). "
        "Bitte in ~1 Minute mit kleinerem Radius erneut versuchen."
    )


def _format(
    params: QueryOsmFeaturesInput,
    lat: float,
    lon: float,
    records: list[dict],
    remark: str,
) -> str:
    if not records:
        return (
            f"Keine '{params.feature_type}' im Umkreis von {params.radius_m} m "
            f"um {lat:.5f},{lon:.5f} gefunden."
        )
    lines = [
        f"**{len(records)} × {params.feature_type}** im Umkreis von "
        f"{params.radius_m} m um {lat:.5f},{lon:.5f}:",
        "",
    ]
    for r in records:
        pos = f"{r['lat']:.5f},{r['lon']:.5f}" if r.get("lat") and r.get("lon") else "?"
        lines.append(f"- **{r['name']}** ({r['osm_type']} {r['osm_id']}) — {pos}")
    if remark:
        lines.append("")
        lines.append(f"_Hinweis: {remark.strip()}_")
    return "\n".join(lines)
