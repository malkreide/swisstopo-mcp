# src/swisstopo_mcp/geodata.py
"""Consolidated geodata facade (Phase-2 Geodaten-Erweiterung).

One façade tool — ``swisstopo_query_geodata`` — fronts three map/layer-style sources to
keep the server well under its 25-tool budget:

* **A** ``strassenverzeichnis`` — amtliches Strassenverzeichnis (api3 MapServer)
* **B** ``geodienste:<topic>:<canton>`` — interkantonale Basisgeodaten via the
  geodienste.ch OGC API Features endpoints (Architecture B: catalogue dump for
  discovery, live OGC API for the actual features)
* **C** ``oereb-verfuegbarkeit`` — bundesweite ÖREB-Kataster-Verfügbarkeit
  (api3 layer ``ch.swisstopo-vd.stand-oerebkataster``)

``swisstopo_list_available_layers`` is the discovery tool that enumerates what can be
passed as ``layer``. See ``docs/geodaten-erweiterung-phase1.md`` for the live
probe that motivated this design.
"""

from __future__ import annotations

import asyncio
import math
import re
import time
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from swisstopo_mcp.api_client import (
    CANTON_PATTERN,
    GEODIENSTE_BASE,
    ID_PATTERN,
    LANG_PATTERN,
    TEXT_PATTERN,
    geo_admin_request,
    handle_api_error,
    lv95_to_wgs84,
    request_with_retry,
    wgs84_to_lv95,
)
from swisstopo_mcp.logging_config import get_logger, log_tool_call
from swisstopo_mcp.models import (
    GEODIENSTE_LICENSE,
    GEODIENSTE_SOURCE,
    OEREB_LICENSE,
    OEREB_SOURCE,
    SWISSTOPO_LICENSE,
    SWISSTOPO_SOURCE,
    ToolResponse,
)

_log = get_logger("swisstopo_mcp.geodata")

STREET_LAYER = "ch.swisstopo.amtliches-strassenverzeichnis"
OEREB_AVAIL_LAYER = "ch.swisstopo-vd.stand-oerebkataster"
GEODIENSTE_CATALOG_URL = f"{GEODIENSTE_BASE}/info/services.json"
GEODIENSTE_PREFIX = "geodienste:"

# Catalogue is a 3.4 MB JSON dump; cache it in-memory (Architecture B).
CATALOG_TTL_SECONDS = 6 * 3600
_MAX_LIMIT = 50

# Collection fan-out (ARCH-007). Waves rather than one-at-a-time or all-at-once:
# see the comment at the loop. The cap bounds a single tool call against a
# cantonal service; when it bites, the response says so rather than presenting a
# partial scan as complete.
_COLLECTION_CONCURRENCY = 4
_MAX_COLLECTIONS_SCANNED = 12

# geodienste.ch rejects an OGC API `items` request that does not name an output
# CRS — with **403 Forbidden** ("Request Query must contain crs=…"), not the 400
# a missing parameter usually earns, which is why this surfaced as "Zugriff
# verweigert" in the live suite (probed 2026-08-10, every free OGC-API dataset).
# EPSG:2056 is the only value the service accepts: CRS84, EPSG:4326 and
# EPSG:3857 are all refused. So features now arrive in LV95 and the `geojson`
# format has to project them back — see `_feature_to_wgs84`.
_OGC_CRS_LV95 = "http://www.opengis.net/def/crs/EPSG/0/2056"
_OGC_CRS_WGS84 = "http://www.opengis.net/def/crs/OGC/1.3/CRS84"

# Static (non-geodienste) façade layers.
# Per-record licences for the layer catalogue. The records use a short source
# key ("swisstopo" / "geodienste"), not the full attribution string, so the
# mapping lives here rather than in models.LICENSE_BY_SOURCE (CH-004).
_LAYER_LICENSES: dict[str, str] = {
    "swisstopo": SWISSTOPO_LICENSE,
    "geodienste": GEODIENSTE_LICENSE,
}

STATIC_LAYERS: dict[str, dict[str, str]] = {
    "strassenverzeichnis": {
        "title": "Amtliches Strassenverzeichnis",
        "source": "swisstopo",
        "location": "point",
        "description": "Strassen (Name, Gemeinde, Status) rund um einen Punkt.",
    },
    "oereb-verfuegbarkeit": {
        "title": "ÖREB-Kataster — Verfügbarkeit / Zuständigkeit",
        "source": "swisstopo",
        "location": "point",
        "description": (
            "Bundesweite Verfügbarkeit des ÖREB-Katasters an einem Punkt "
            "(Status + zuständige Stelle). Kein Grundstücksauszug."
        ),
    },
}


# ---------------------------------------------------------------------------
# geodienste.ch catalogue (cached dump)
# ---------------------------------------------------------------------------

_catalog: list[dict[str, Any]] | None = None
_catalog_ts: float = 0.0


def _is_free(entry: dict[str, Any], kind: str = "wms") -> bool:
    """True if a catalogue entry is usable without a contract and under an open
    licence. ``opendata_terms_*`` is free text (not a bool) — a live-probe
    fundstück — so we check the contract flag *and* the terms prefix."""
    contract = entry.get(f"contract_required_{kind}")
    terms = entry.get(f"opendata_terms_{kind}") or ""
    return contract is False and terms.startswith("Freie Nutzung")


def _has_ogc_api(entry: dict[str, Any]) -> str | None:
    """Return the entry's OGC API Features base URL, or None."""
    urls = entry.get("ogc_api_features")
    if isinstance(urls, list) and urls:
        first = urls[0]
        return str(first) if first else None
    if isinstance(urls, str) and urls:
        return urls
    return None


async def load_geodienste_catalog(force: bool = False) -> list[dict[str, Any]]:
    """Fetch and cache the geodienste.ch services catalogue (Architecture B)."""
    global _catalog, _catalog_ts
    now = time.monotonic()
    if not force and _catalog is not None and (now - _catalog_ts) < CATALOG_TTL_SECONDS:
        return _catalog
    response = await request_with_retry("GET", GEODIENSTE_CATALOG_URL)
    data = response.json()
    services = data.get("services", []) if isinstance(data, dict) else []
    _catalog = services
    _catalog_ts = now
    _log.debug("geodienste_catalog_loaded", entries=len(services))
    return services


def _find_geodienste_entry(
    catalog: list[dict[str, Any]], topic: str, canton: str
) -> dict[str, Any] | None:
    """Match a catalogue entry by base_topic (or topic) and canton."""
    canton = canton.upper()
    for entry in catalog:
        if entry.get("canton", "").upper() != canton:
            continue
        if entry.get("base_topic") == topic or entry.get("topic") == topic:
            return entry
    return None


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------


def _bbox_from_point(lat: float, lon: float, radius_m: float) -> tuple[float, float, float, float]:
    """WGS84 bounding box (minLon, minLat, maxLon, maxLat) around a point."""
    dlat = radius_m / 111_320.0
    dlon = radius_m / (111_320.0 * max(math.cos(math.radians(lat)), 0.01))
    return (lon - dlon, lat - dlat, lon + dlon, lat + dlat)


def _coords_to_wgs84(coords: Any) -> Any:
    """Project a GeoJSON coordinate structure from LV95 to WGS84, in place of
    the shape it came in — a position, or any nesting of them."""
    if not isinstance(coords, list):
        return coords
    if len(coords) >= 2 and all(
        isinstance(v, int | float) and not isinstance(v, bool) for v in coords[:2]
    ):
        lat, lon = lv95_to_wgs84(float(coords[0]), float(coords[1]))
        # GeoJSON positions are [lon, lat]; anything past them (height, m) rides
        # along untouched — the polynomial only speaks planimetry.
        return [lon, lat, *coords[2:]]
    return [_coords_to_wgs84(c) for c in coords]


def _feature_to_wgs84(feature: dict[str, Any]) -> dict[str, Any]:
    """Return the feature with its geometry projected LV95 → WGS84.

    geodienste only serves LV95 now (see ``_OGC_CRS_LV95``), but a
    ``FeatureCollection`` is read as WGS84 by default (RFC 7946), so handing the
    Swiss coordinates straight through would put every feature in the Indian
    Ocean without saying so. The conversion uses the same ~1 m polynomial the
    rest of this server uses for point queries.
    """
    geometry = feature.get("geometry")
    if not isinstance(geometry, dict):
        return feature
    return {**feature, "geometry": _geometry_to_wgs84(geometry)}


def _geometry_to_wgs84(geometry: dict[str, Any]) -> dict[str, Any]:
    if "geometries" in geometry:  # GeometryCollection
        return {
            **geometry,
            "geometries": [
                _geometry_to_wgs84(g) if isinstance(g, dict) else g
                for g in geometry.get("geometries") or []
            ],
        }
    if "coordinates" in geometry:
        return {**geometry, "coordinates": _coords_to_wgs84(geometry.get("coordinates"))}
    return geometry


# ---------------------------------------------------------------------------
# Input models
# ---------------------------------------------------------------------------

LocationFormat = Literal["summary", "records", "geojson"]


class QueryGeodataInput(BaseModel):
    """Façade query: pick a ``layer`` (from swisstopo_list_available_layers) and exactly
    one location (``point``, ``bbox`` or ``commune``)."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid", strict=True)

    layer: str = Field(
        ...,
        min_length=2,
        max_length=120,
        pattern=r"^[\w.:\-]+$",
        description=(
            "Layer-Kennung aus swisstopo_list_available_layers: 'strassenverzeichnis', "
            "'oereb-verfuegbarkeit' oder 'geodienste:<topic>:<KANTON>'."
        ),
    )
    point: str | None = Field(
        default=None,
        max_length=60,
        # The space after the comma is the way a coordinate pair is normally
        # written, `float()` strips it anyway, and the two sibling fields here
        # already accept it — `bbox` admits `\s` and strips each part, and so
        # does `coordinates` on the elevation profile. `point` was the only one
        # that turned '47.36, 8.52' into a regex error.
        pattern=r"^[\d.\-]+,\s*[\d.\-]+$",
        description="WGS84-Punkt 'lat,lon' (z.B. '47.360966,8.525343').",
    )
    bbox: str | None = Field(
        default=None,
        max_length=120,
        pattern=r"^[\d.,\-\s]+$",
        description="WGS84-Bounding-Box 'minLon,minLat,maxLon,maxLat'.",
    )
    commune: str | None = Field(
        default=None,
        max_length=100,
        pattern=TEXT_PATTERN,
        description="Gemeindename (nur für 'strassenverzeichnis').",
    )
    radius_m: int = Field(
        default=150, ge=10, le=5000, description="Suchradius in Metern für Punkt-Abfragen."
    )
    limit: int = Field(default=20, ge=1, le=_MAX_LIMIT, description="Max. Ergebnisanzahl.")
    format: LocationFormat = Field(default="summary", description="summary | records | geojson.")
    lang: str = Field(default="de", pattern=LANG_PATTERN, description="Sprache: de, fr, it, en.")


class ListLayersInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid", strict=True)

    source: str | None = Field(
        default=None,
        pattern=r"^(swisstopo|geodienste|oereb)$",
        description="Filter: swisstopo | geodienste | oereb.",
    )
    canton: str | None = Field(
        default=None,
        min_length=2,
        max_length=2,
        pattern=CANTON_PATTERN,
        description="Kantonskürzel für geodienste-Layer (z.B. 'ZH').",
    )
    free_only: bool = Field(
        default=True, description="Nur ohne Vertrag/Login frei nutzbare geodienste-Layer."
    )
    topic: str | None = Field(
        default=None, max_length=80, pattern=ID_PATTERN, description="geodienste-Topic-Filter."
    )


# ---------------------------------------------------------------------------
# Dispatch: swisstopo_query_geodata
# ---------------------------------------------------------------------------


def _parse_point(point: str) -> tuple[float, float]:
    lat_s, lon_s = point.split(",", 1)
    lat, lon = float(lat_s), float(lon_s)
    if not (45.8 <= lat <= 47.9 and 5.9 <= lon <= 10.5):
        raise ValueError(f"Punkt ausserhalb der Schweiz: {lat},{lon}.")
    return lat, lon


@log_tool_call("swisstopo_query_geodata")
async def query_geodata(params: QueryGeodataInput) -> ToolResponse:
    """Route a façade query to the correct source based on ``layer``."""
    try:
        layer = params.layer
        if layer == "strassenverzeichnis":
            return await _query_streets(params)
        if layer == "oereb-verfuegbarkeit":
            return await _query_oereb_availability(params)
        if layer.startswith(GEODIENSTE_PREFIX):
            return await _query_geodienste(params)
        return ToolResponse.error(
            f"Unbekannter Layer '{layer}'. Nutze swisstopo_list_available_layers "
            f"für gültige Kennungen (z.B. 'strassenverzeichnis', "
            f"'geodienste:<topic>:<KANTON>')."
        )
    except Exception as e:  # noqa: BLE001 — handle_api_error classifies
        return ToolResponse.error(handle_api_error(e, f"swisstopo_query_geodata({params.layer})"))


async def _query_streets(params: QueryGeodataInput) -> ToolResponse:
    """A — amtliches Strassenverzeichnis via api3 MapServer identify / featuresearch."""
    if params.commune and not params.point and not params.bbox:
        # Search by street/commune name (featuresearch).
        data = await geo_admin_request(
            "/rest/services/api/SearchServer",
            {
                "type": "featuresearch",
                "searchText": params.commune,
                "features": STREET_LAYER,
                "limit": params.limit,
                "lang": params.lang,
            },
        )
        results = data.get("results", [])
        name_hits: list[dict[str, Any]] = [
            {
                "label": _strip_html(r.get("attrs", {}).get("label", "")),
                "feature_id": r.get("attrs", {}).get("featureId") or r.get("id"),
            }
            for r in results
        ]
        summary = _format_records(
            f"Strassenverzeichnis — Treffer für '{params.commune}'", name_hits, params.format
        )
        return ToolResponse.ok(
            summary,
            name_hits,
            match_type="exact" if name_hits else "none",
            note=(
                None
                if name_hits
                else f"Keine Strasse in '{params.commune}' gefunden. Gemeindename mit "
                "swisstopo_find_commune in amtlicher Schreibweise ermitteln, oder "
                "den Strassennamen weglassen, um alle Strassen der Gemeinde zu sehen."
            ),
            source=SWISSTOPO_SOURCE,
            license=SWISSTOPO_LICENSE,
        )

    if not params.point:
        return ToolResponse.error(
            "Für 'strassenverzeichnis' bitte 'point' (lat,lon) oder 'commune' angeben."
        )

    lat, lon = _parse_point(params.point)
    e, n = wgs84_to_lv95(lat, lon)
    # 2000 m map extent at 200 px = 10 m/px; tolerance in px ≈ radius_m / 10.
    half = 1000.0
    tol_px = max(1, min(200, round(params.radius_m / (2 * half / 200))))
    data = await geo_admin_request(
        "/rest/services/api/MapServer/identify",
        {
            "geometryType": "esriGeometryPoint",
            "geometry": f"{e:.1f},{n:.1f}",
            "sr": 2056,
            "tolerance": tol_px,
            "layers": f"all:{STREET_LAYER}",
            "mapExtent": f"{e - half:.1f},{n - half:.1f},{e + half:.1f},{n + half:.1f}",
            "imageDisplay": "200,200,96",
            "returnGeometry": params.format == "geojson",
            "lang": params.lang,
        },
    )
    results = data.get("results", [])
    seen: set[str] = set()
    records: list[dict[str, Any]] = []
    for r in results:
        attrs = r.get("attributes", {})
        name = attrs.get("stn_label") or attrs.get("label")
        if not name or name in seen:
            continue
        seen.add(name)
        rec = {
            "street": name,
            "zip_label": attrs.get("zip_label"),
            "commune": attrs.get("com_name"),
            "status": attrs.get("str_status"),
            "feature_id": r.get("featureId"),
        }
        if params.format == "geojson" and r.get("geometry"):
            rec["geometry"] = r["geometry"]
        records.append(rec)
    records = records[: params.limit]
    summary = _format_records(
        f"Strassen im Umkreis von {params.radius_m} m um {lat:.5f},{lon:.5f}",
        records,
        params.format,
    )
    return ToolResponse.ok(
        summary,
        records,
        match_type="exact" if records else "none",
        note=(
            None
            if records
            else "Keine Strasse im Umkreis. radius_m erhöhen, oder mit "
            "swisstopo_municipality_at prüfen, ob der Punkt in der Schweiz liegt."
        ),
        source=SWISSTOPO_SOURCE,
        license=SWISSTOPO_LICENSE,
    )


async def _query_oereb_availability(params: QueryGeodataInput) -> ToolResponse:
    """C — bundesweite ÖREB-Verfügbarkeit (api3 identify, kein Extract)."""
    if not params.point:
        return ToolResponse.error("Für 'oereb-verfuegbarkeit' bitte 'point' (lat,lon) angeben.")
    lat, lon = _parse_point(params.point)
    e, n = wgs84_to_lv95(lat, lon)
    data = await geo_admin_request(
        "/rest/services/all/MapServer/identify",
        {
            "geometryType": "esriGeometryPoint",
            "geometry": f"{e:.1f},{n:.1f}",
            "sr": 2056,
            "tolerance": 0,
            "layers": f"all:{OEREB_AVAIL_LAYER}",
            "mapExtent": f"{e - 50:.1f},{n - 50:.1f},{e + 50:.1f},{n + 50:.1f}",
            "imageDisplay": "100,100,96",
            "returnGeometry": False,
            "lang": params.lang,
        },
    )
    results = data.get("results", [])
    records: list[dict[str, Any]] = []
    seen: set[tuple[Any, Any]] = set()
    for r in results:
        a = r.get("attributes", {})
        key = (a.get("bfs_nr"), a.get("firmenname"))
        if key in seen:
            continue
        seen.add(key)
        records.append(
            {
                "commune": a.get("gemeindename"),
                "canton": a.get("kanton"),
                "bfs_nr": a.get("bfs_nr"),
                "oereb_status": a.get(f"oereb_status_{params.lang}") or a.get("oereb_status_de"),
                "authority": a.get("firmenname"),
                "authority_email": a.get("email"),
                "authority_phone": a.get("telefon"),
            }
        )
    if not records:
        return ToolResponse.ok(
            f"Keine ÖREB-Verfügbarkeitsinformation für {lat:.5f},{lon:.5f}.",
            [],
            match_type="none",
            note=(
                "Der Bundesdienst kennt für diesen Punkt keinen Eintrag — er liegt "
                "womöglich ausserhalb der Schweiz. swisstopo_municipality_at nennt "
                "die Gemeinde, swisstopo_oereb_at liefert den Auszug direkt, wo "
                "der Kanton unterstützt wird."
            ),
            source=OEREB_SOURCE,
            license=OEREB_LICENSE,
        )
    lines = [f"**ÖREB-Kataster-Verfügbarkeit** ({lat:.5f},{lon:.5f})", ""]
    for rec in records:
        lines.append(
            f"- **{rec['commune']}** ({rec['canton']}, BFS {rec['bfs_nr']}): {rec['oereb_status']}"
        )
        if rec.get("authority"):
            lines.append(f"  - Zuständig: {rec['authority']} ({rec.get('authority_email') or '—'})")
    lines.append("")
    lines.append(
        "ℹ️ Grundstücksbezogener ÖREB-Auszug ist kantonal fragmentiert — siehe "
        "swisstopo_get_egrid / swisstopo_get_oereb_extract (ZH/BE)."
    )
    return ToolResponse.ok(
        "\n".join(lines),
        records,
        match_type="exact",
        source=OEREB_SOURCE,
        license=OEREB_LICENSE,
    )


async def _query_geodienste(params: QueryGeodataInput) -> ToolResponse:
    """B — interkantonale Basisgeodaten via geodienste.ch OGC API Features."""
    parts = params.layer.split(":")
    if len(parts) != 3 or not parts[1] or not parts[2]:
        return ToolResponse.error(
            "geodienste-Layer erwartet Format 'geodienste:<topic>:<KANTON>' "
            "(z.B. 'geodienste:kataster_belasteter_standorte:ZH'). "
            "Nutze swisstopo_list_available_layers(source='geodienste', canton='ZH')."
        )
    _, topic, canton = parts
    catalog = await load_geodienste_catalog()
    entry = _find_geodienste_entry(catalog, topic, canton)
    if entry is None:
        return ToolResponse.error(
            f"Kein geodienste-Datensatz '{topic}' für Kanton {canton.upper()} gefunden."
        )
    if not _is_free(entry, "wms"):
        return ToolResponse.error(
            f"Datensatz '{topic}' ({canton.upper()}) ist nicht ohne Vertrag/Login frei "
            f"nutzbar (opendata_terms: {entry.get('opendata_terms_wms') or 'keine Angabe'})."
        )
    ogc_base = _has_ogc_api(entry)
    if not ogc_base:
        wfs = entry.get("getcapabilities_wfs")
        return ToolResponse.error(
            f"Datensatz '{topic}' ({canton.upper()}) bietet keine OGC API Features. "
            f"WFS-Capabilities: {wfs[0] if isinstance(wfs, list) and wfs else '—'}."
        )

    # Determine bbox (WGS84).
    if params.bbox:
        bbox_vals = [p.strip() for p in params.bbox.split(",")]
        if len(bbox_vals) != 4:
            return ToolResponse.error("bbox erwartet 'minLon,minLat,maxLon,maxLat'.")
        bbox = ",".join(bbox_vals)
    elif params.point:
        lat, lon = _parse_point(params.point)
        bbox = ",".join(f"{v:.6f}" for v in _bbox_from_point(lat, lon, params.radius_m))
    else:
        return ToolResponse.error(
            "Für geodienste-Layer bitte 'bbox' oder 'point' (mit radius_m) angeben."
        )

    # Discover collections, query the first one's items within the bbox.
    coll_url = f"{ogc_base.rstrip('/')}/collections"
    coll_resp = await request_with_retry("GET", coll_url, params={"f": "json"})
    collections = coll_resp.json().get("collections", [])
    if not collections:
        return ToolResponse.ok(
            f"Datensatz '{topic}' ({canton.upper()}) enthält keine Collections.",
            [],
            match_type="none",
            note=(
                f"Der Kanton {canton.upper()} publiziert für '{topic}' keine "
                "abfragbaren Collections. swisstopo_list_available_layers zeigt, "
                "welche Kantone das Thema mit OGC-API frei anbieten."
            ),
            source=GEODIENSTE_SOURCE,
            license=GEODIENSTE_LICENSE,
        )
    all_records: list[dict[str, Any]] = []
    features_out: list[dict[str, Any]] = []
    total_matched = 0

    # Fan out in waves rather than one collection at a time (ARCH-007). The old
    # loop was strictly sequential, which is the check's named anti-pattern for
    # an aggregation tool — but it had a real virtue: it stopped as soon as it
    # had `limit` records, often after one request.
    #
    # Querying all collections at once would throw that away. A single
    # geodienste dataset can hold 24 collections (measured: av_0), so a naive
    # gather would mean 24 requests against a cantonal service every time, to
    # save latency only when the early ones come back empty. Waves keep the
    # early exit and still cut the worst case by the wave size.
    ids = [c.get("id") for c in collections if c.get("id")]
    scanned = ids[:_MAX_COLLECTIONS_SCANNED]

    async def _fetch(cid: str) -> tuple[str, dict[str, Any]]:
        items_url = f"{ogc_base.rstrip('/')}/collections/{cid}/items"
        response = await request_with_retry(
            "GET",
            items_url,
            params={
                "f": "json",
                "bbox": bbox,
                "limit": params.limit,
                # Mandatory upstream (403 without it). `bbox-crs` is CRS84 by
                # default, but naming it keeps our WGS84 bbox correct even if
                # geodienste tightens that default the way it tightened `crs`.
                "crs": _OGC_CRS_LV95,
                "bbox-crs": _OGC_CRS_WGS84,
            },
        )
        return cid, response.json()

    stopped_early = False
    for start in range(0, len(scanned), _COLLECTION_CONCURRENCY):
        wave = scanned[start : start + _COLLECTION_CONCURRENCY]
        # gather preserves order, so results stay deterministic regardless of
        # which upstream answers first.
        for cid, payload in await asyncio.gather(*(_fetch(c) for c in wave)):
            feats = payload.get("features", [])
            total_matched += payload.get("numberMatched", len(feats)) or 0
            for f in feats:
                props = f.get("properties", {})
                all_records.append({"collection": cid, **props})
                if params.format == "geojson":
                    features_out.append(_feature_to_wgs84(f))
        if len(all_records) >= params.limit:
            stopped_early = True
            break

    all_records = all_records[: params.limit]
    # Only a cap that actually bit is worth reporting: if we stopped early we
    # had enough data, and if we scanned every collection nothing was left out.
    truncated_note = None
    if not stopped_early and len(ids) > len(scanned):
        # Never silently: a cap that is invisible reads as "this is everything".
        truncated_note = (
            f"Nur die ersten {len(scanned)} von {len(ids)} Collections dieses "
            "Datensatzes wurden abgefragt. Mit einer engeren bbox erneut suchen, "
            "wenn ein bestimmtes Objekt fehlt."
        )
    title = f"{entry.get('topic_title', topic)} ({canton.upper()})"
    if params.format == "geojson":
        summary = f"**{title}** — {len(features_out)} Feature(s), numberMatched≈{total_matched}."
        payload_records: list[dict[str, Any]] = features_out[: params.limit]
        # The upstream only serves LV95; say that the coordinates handed back
        # were converted rather than measured (~1 m polynomial).
        if features_out:
            crs_note = (
                "Geometrien aus LV95 (EPSG:2056) nach WGS84 umgerechnet "
                "(Näherungspolynom, ~1 m). Für amtliche Genauigkeit "
                "swisstopo_convert_coordinates (REFRAME) verwenden."
            )
            truncated_note = f"{truncated_note} {crs_note}" if truncated_note else crs_note
    else:
        summary = _format_records(
            f"{title} — numberMatched≈{total_matched}", all_records, params.format
        )
        payload_records = all_records
    if all_records:
        note = truncated_note
    else:
        note = (
            "Keine Features im abgefragten Bereich. bbox vergrössern oder einen "
            "anderen Punkt wählen; swisstopo_list_available_layers zeigt, ob der "
            "Datensatz für diesen Kanton überhaupt Daten führt."
        )
        if truncated_note:
            note = f"{note} {truncated_note}"
    return ToolResponse.ok(
        summary,
        payload_records,
        match_type="exact" if all_records else "none",
        note=note,
        source=f"{GEODIENSTE_SOURCE} / {entry.get('canton', canton.upper())}",
        license=GEODIENSTE_LICENSE,
    )


# ---------------------------------------------------------------------------
# Discovery: swisstopo_list_available_layers
# ---------------------------------------------------------------------------


@log_tool_call("swisstopo_list_available_layers")
async def list_available_layers(params: ListLayersInput) -> ToolResponse:
    """Enumerate façade layers usable with swisstopo_query_geodata."""
    try:
        records: list[dict[str, Any]] = []

        if params.source in (None, "swisstopo", "oereb"):
            for key, meta in STATIC_LAYERS.items():
                if params.source == "oereb" and key != "oereb-verfuegbarkeit":
                    continue
                if params.source == "swisstopo" and meta["source"] != "swisstopo":
                    continue
                records.append(
                    {
                        "layer": key,
                        "source": meta["source"],
                        "location": meta["location"],
                        "title": meta["title"],
                        "free": True,
                    }
                )

        if params.source in (None, "geodienste"):
            catalog = await load_geodienste_catalog()
            geodienste_records = _geodienste_layer_records(catalog, params)
            records.extend(geodienste_records)
            summary = _format_layer_catalog(records, params, catalog)
        else:
            summary = _format_layer_catalog(records, params, None)

        # The envelope licence is necessarily composite here, so each record
        # carries its own — otherwise "gemischt — siehe je Layer" points at
        # nothing the caller can actually read (audit CH-004).
        for record in records:
            record["license"] = _LAYER_LICENSES.get(record.get("source", ""), SWISSTOPO_LICENSE)

        return ToolResponse.ok(
            summary,
            records,
            match_type="exact" if records else "none",
            note=(
                None
                if records
                else "Keine Layer für diesen Filter. source/topic/canton weglassen, um "
                "den vollständigen Katalog zu sehen, oder free_only abschalten."
            ),
            source=f"{SWISSTOPO_SOURCE} + {GEODIENSTE_SOURCE}",
            license="gemischt — siehe je Layer (Feld `license` pro Record)",
            provenance="cached",
        )
    except Exception as e:  # noqa: BLE001
        return ToolResponse.error(handle_api_error(e, "swisstopo_list_available_layers"))


def _geodienste_layer_records(
    catalog: list[dict[str, Any]], params: ListLayersInput
) -> list[dict[str, Any]]:
    """Build geodienste layer rows. Without a canton filter, return the topic
    overview (bounded, ~45 rows); with a canton, return concrete queryable
    layer ids."""
    if params.canton is None:
        # Topic overview: how many cantons offer each topic free with OGC API.
        by_topic: dict[str, dict[str, Any]] = {}
        for e in catalog:
            t = e.get("base_topic")
            if not t or (params.topic and params.topic not in t):
                continue
            slot = by_topic.setdefault(
                t, {"topic": t, "title": e.get("topic_title", t), "free_cantons": 0, "cantons": 0}
            )
            slot["cantons"] += 1
            if _is_free(e, "wms") and _has_ogc_api(e):
                slot["free_cantons"] += 1
        rows = [
            {
                "layer": f"{GEODIENSTE_PREFIX}{v['topic']}:<KANTON>",
                "source": "geodienste",
                "location": "bbox|point",
                "title": v["title"],
                "free_cantons": v["free_cantons"],
                "cantons": v["cantons"],
            }
            for v in by_topic.values()
        ]
        if params.free_only:
            rows = [r for r in rows if r["free_cantons"] > 0]
        return sorted(rows, key=lambda r: -r["free_cantons"])

    # Concrete layers for one canton.
    canton = params.canton.upper()
    rows = []
    for e in catalog:
        if e.get("canton", "").upper() != canton:
            continue
        topic = e.get("base_topic")
        if not topic or (params.topic and params.topic not in topic):
            continue
        free = _is_free(e, "wms")
        ogc = _has_ogc_api(e)
        if params.free_only and not (free and ogc):
            continue
        rows.append(
            {
                "layer": f"{GEODIENSTE_PREFIX}{topic}:{canton}",
                "source": "geodienste",
                "location": "bbox|point",
                "title": e.get("topic_title", topic),
                "free": free,
                "ogc_api": bool(ogc),
                "updated_at": e.get("updated_at"),
            }
        )
    return sorted(rows, key=lambda r: r["layer"])


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

_HTML_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    return _HTML_RE.sub("", text) if text else ""


def _format_records(title: str, records: list[dict[str, Any]], fmt: str) -> str:
    if not records:
        return f"{title}: keine Treffer."
    lines = [f"**{title}** ({len(records)}):", ""]
    for rec in records[:_MAX_LIMIT]:
        primary = (
            rec.get("street")
            or rec.get("label")
            or rec.get("commune")
            or rec.get("collection")
            or "Feature"
        )
        extras = [
            f"{k}={v}"
            for k, v in rec.items()
            if k not in ("geometry", "street", "label") and v not in (None, "")
        ][:6]
        lines.append(f"- **{primary}** — {', '.join(extras)}" if extras else f"- **{primary}**")
    return "\n".join(lines)


def _format_layer_catalog(
    records: list[dict[str, Any]], params: ListLayersInput, catalog: list[dict[str, Any]] | None
) -> str:
    if not records:
        return "Keine Layer gefunden für die angegebenen Filter."
    lines = [f"**{len(records)} verfügbare Layer:**", ""]
    for r in records:
        if r.get("source") == "geodienste" and "free_cantons" in r:
            lines.append(
                f"- `{r['layer']}` — {r['title']} "
                f"(frei in {r['free_cantons']}/{r['cantons']} Kantonen)"
            )
        else:
            free = "frei" if r.get("free", True) else "eingeschränkt"
            lines.append(f"- `{r['layer']}` — {r['title']} [{r.get('source')}, {free}]")
    if params.canton is None and params.source in (None, "geodienste"):
        lines.append("")
        lines.append(
            "ℹ️ Für konkrete geodienste-Layer-Kennungen einen Kanton angeben, z.B. "
            "swisstopo_list_available_layers(source='geodienste', canton='ZH')."
        )
    return "\n".join(lines)
