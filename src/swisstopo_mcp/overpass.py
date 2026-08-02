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

from mcp.server.mcpserver import Context
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
    "school",
    "kindergarten",
    "university",
    "playground",
    "park",
    "hospital",
    "pharmacy",
    "doctor",
    "restaurant",
    "cafe",
    "supermarket",
    "bank",
    "atm",
    "parking",
    "bus_stop",
    "train_station",
    "library",
    "sports_centre",
    "swimming_pool",
    "toilets",
    "fuel",
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


async def _say(ctx: Context | None, message: str) -> None:
    """Best-effort status line — reporting must never fail a request."""
    if ctx is None:
        return
    try:
        await ctx.info(message)
    except Exception:  # noqa: BLE001 - progress reporting is best-effort
        pass


async def _resolve_area(area: str, ctx: Context | None = None) -> tuple[float, float]:
    """Return (lat, lon) for a 'lat,lon' string or a geocoded place name."""
    if _looks_like_point(area):
        lat, lon = (float(p) for p in area.split(","))
        if not (45.8 <= lat <= 47.9 and 5.9 <= lon <= 10.5):
            raise ValueError(f"Punkt ausserhalb der Schweiz: {lat},{lon}.")
        return lat, lon
    await _say(ctx, f"Geocodiere «{area}» …")
    data = await geo_admin_request(
        "/rest/services/api/SearchServer",
        {"type": "locations", "searchText": area, "limit": 1, "sr": 4326},
        ctx=ctx,
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


# Fixed, user-facing classifications of an Overpass error page (audit OBS-002).
#
# The upstream text is never forwarded. A real Overpass error page echoes the
# submitted query and can name server-side paths — `open64: 2 No such file or
# directory /opt/osm/db/overpass_db/...` is a message the public instance
# genuinely returns. Passing that to the model disclosed infrastructure and gave
# a third party a channel into the context window. The body goes to stderr
# instead, where an operator can read it and the model cannot.
_ERROR_SIGNATURES: tuple[tuple[str, str], ...] = (
    (
        "timed out",
        "Overpass hat das Zeitlimit überschritten. Kleinerer Radius oder "
        "niedrigeres limit hilft meist.",
    ),
    (
        "out of memory",
        "Die Abfrage war für Overpass zu gross. Radius oder limit reduzieren.",
    ),
    (
        "too many requests",
        "Overpass hat die Anfrage wegen Rate-Limiting abgewiesen.",
    ),
    (
        "rate_limited",
        "Overpass hat die Anfrage wegen Rate-Limiting abgewiesen.",
    ),
    (
        "parse error",
        "Overpass konnte die Abfrage nicht verarbeiten (interner Abfragefehler).",
    ),
)
_ERROR_GENERIC = "Overpass meldete einen Fehler."


def _classify_error(text: str) -> str | None:
    """Return a fixed message when the body is an Overpass error page.

    Returns None when the body is not an error page. The return value never
    contains upstream text — see the note on `_ERROR_SIGNATURES`.
    """
    lowered = text.lstrip().lower()
    if lowered.startswith("{"):
        return None  # looks like JSON, not an error page

    is_error = "error" in lowered or bool(
        re.search(r"<strong[^>]*>\s*Error\s*</strong>", text, re.IGNORECASE)
    )
    if not is_error:
        return None

    _log.warning("overpass_error_page", body=text.strip()[:1000])
    return _match_signature(lowered)


def _match_signature(lowered: str) -> str:
    for signature, message in _ERROR_SIGNATURES:
        if signature in lowered:
            return message
    return _ERROR_GENERIC


def _classify_remark(remark: str) -> str:
    """Same treatment for the HTTP-200 `remark` path."""
    return _match_signature(remark.lower())


@log_tool_call("swisstopo_query_osm_features")
async def query_osm_features(
    params: QueryOsmFeaturesInput, ctx: Context | None = None
) -> ToolResponse:
    """Query OpenStreetMap POIs around a point via Overpass (ODbL)."""
    try:
        tag = FEATURE_TAGS[params.feature_type]
        lat, lon = await _resolve_area(params.area, ctx)
        query = _build_query(tag, lat, lon, params.radius_m, params.limit)

        # The slowest tool in the surface: a 25 s server timeout behind a 30 s
        # client timeout, plus up to 14 s of retry backoff. Announcing the wait
        # before it starts is the difference between "slow" and "hung" from the
        # client's side (audit SDK-003).
        await _say(ctx, f"Overpass-Abfrage läuft (bis zu {OVERPASS_SERVER_TIMEOUT} s) …")
        try:
            response = await request_with_retry(
                "POST",
                OVERPASS_INTERPRETER,
                content=f"data={query}",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=OVERPASS_CLIENT_TIMEOUT,
                ctx=ctx,
            )
        except Exception as exc:  # noqa: BLE001 — degrade gracefully
            return ToolResponse.error(
                _degraded(handle_api_error(exc, "Overpass-Abfrage")),
                source=OSM_SOURCE,
                license=OSM_LICENSE,
            )

        text = response.text
        err = _classify_error(text)
        if err is not None:
            return ToolResponse.error(_degraded(err), source=OSM_SOURCE, license=OSM_LICENSE)
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return ToolResponse.error(
                _degraded("Overpass lieferte keine gültige JSON-Antwort."),
                source=OSM_SOURCE,
                license=OSM_LICENSE,
            )

        # A server-side timeout returns HTTP 200 + an embedded 'remark'. The
        # remark is upstream text like every other error string here, so it is
        # classified rather than forwarded (OBS-002).
        remark = data.get("remark", "")
        if remark and ("timed out" in remark.lower() or "runtime error" in remark.lower()):
            _log.warning("overpass_remark", remark=remark.strip()[:1000])
            return ToolResponse.error(
                _degraded(_classify_remark(remark)), source=OSM_SOURCE, license=OSM_LICENSE
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
            summary,
            records,
            match_type="exact" if records else "none",
            note=(
                None
                if records
                else f"Keine '{params.feature_type}' im Umkreis von "
                f"{params.radius_m} m. radius_m erhöhen (max. 5000), oder eine "
                "andere feature_type-Kategorie wählen. OSM-Daten sind "
                "community-gepflegt und je nach Region unvollständig."
            ),
            source=OSM_SOURCE,
            license=OSM_LICENSE,
        )
    except Exception as e:  # noqa: BLE001
        return ToolResponse.error(
            handle_api_error(e, "query_osm_features"),
            source=OSM_SOURCE,
            license=OSM_LICENSE,
        )


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
