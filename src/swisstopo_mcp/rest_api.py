# src/swisstopo_mcp/rest_api.py
"""REST API tools for api3.geo.admin.ch (SearchServer, MapServer)."""
from __future__ import annotations

import html
import re
from typing import Any, Literal

from mcp.server.fastmcp import Context
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from swisstopo_mcp.api_client import (
    CH_LAT_MAX,
    CH_LAT_MIN,
    CH_LON_MAX,
    CH_LON_MIN,
    ID_PATTERN,
    LANG_PATTERN,
    TEXT_PATTERN,
    geo_admin_request,
    geo_admin_request_text,
    handle_api_error,
    validate_sr,
)
from swisstopo_mcp.coords import SwissPointInput, check_deprecated_sr
from swisstopo_mcp.logging_config import get_logger, log_tool_call
from swisstopo_mcp.models import (
    ARE_LICENSE,
    ARE_SOURCE,
    ARE_ZONING_CAVEAT,
    SWISSBOUNDARIES_LICENSE,
    SWISSBOUNDARIES_SOURCE,
    ToolResponse,
)

_log = get_logger("swisstopo_mcp.rest_api")

# --- Named layers backing the convenience lookups ---
# swissBOUNDARIES3D municipality polygons (one per historical year).
MUNICIPALITY_LAYER = "ch.swisstopo.swissboundaries3d-gemeinde-flaeche.fill"
# Harmonised building zones published by ARE.
ZONING_LAYER = "ch.are.bauzonen"

# ---------------------------------------------------------------------------
# Input Models
# ---------------------------------------------------------------------------


class SearchLayersInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid", strict=True)

    query: str = Field(
        ...,
        min_length=1,
        max_length=200,
        pattern=TEXT_PATTERN,
        description="Suchbegriff für Layer-Katalog",
    )
    lang: str = Field(default="de", pattern=LANG_PATTERN, description="Sprache: de, fr, it, en")
    limit: int = Field(default=10, ge=1, le=30)


class IdentifyInput(SwissPointInput):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid", strict=True)

    layers: str = Field(
        ...,
        min_length=2,
        max_length=512,
        pattern=ID_PATTERN,
        description="Layer-IDs, kommagetrennt, z.B. 'ch.bfs.gebaeude_wohnungs_register'",
    )
    tolerance: int = Field(default=0, ge=0, le=200, description="Suchradius in Pixeln")
    sr: int = Field(
        default=4326,
        description="Veraltet — nur noch 4326. Für LV95 easting/northing verwenden.",
    )

    @model_validator(mode="after")
    def _check_sr(self) -> IdentifyInput:
        check_deprecated_sr(self.sr)
        return self


class FindFeaturesInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid", strict=True)

    layer: str = Field(
        ..., min_length=2, max_length=128, pattern=ID_PATTERN, description="Layer-ID"
    )
    search_text: str = Field(..., min_length=1, max_length=200, pattern=TEXT_PATTERN, description="Suchwert")
    search_field: str = Field(
        ..., min_length=1, max_length=128, pattern=ID_PATTERN, description="Attributfeld"
    )
    contains: bool = Field(default=True, description="Teilstring-Suche (True) oder exakt (False)")


class GetFeatureInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid", strict=True)

    layer: str = Field(
        ..., min_length=2, max_length=128, pattern=ID_PATTERN, description="Layer-ID"
    )
    feature_id: str = Field(
        ..., min_length=1, max_length=128, pattern=ID_PATTERN, description="Feature-ID"
    )
    sr: int = Field(default=4326, description="Koordinatensystem der Ausgabegeometrie")

    @field_validator("sr")
    @classmethod
    def _validate_sr(cls, v: int) -> int:
        return validate_sr(v)


class ZoningAtInput(SwissPointInput):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid", strict=True)


class MunicipalityAtInput(SwissPointInput):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid", strict=True)


class LayerInfoInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid", strict=True)

    layer: str = Field(
        ..., min_length=2, max_length=128, pattern=ID_PATTERN, description="Layer-ID"
    )
    lang: str = Field(default="de", pattern=LANG_PATTERN, description="Sprache: de, fr, it, en")


# ---------------------------------------------------------------------------
# The merged api3 surface (audit ARCH-006)
#
# These five operations shipped as five tools, one per REST endpoint, which is
# the 1:1 API mapping the check names. They are now one tool.
#
# The operation names are deliberately *not* the upstream endpoint names.
# `identify` and `find` are ESRI vocabulary: they describe which MapServer route
# is called, not which question is being asked, and a caller who does not
# already know ArcGIS cannot tell them apart. `features_at_point` and
# `features_by_attribute` can be chosen correctly by someone reading nothing but
# the operation list — which is the whole job, since collapsing five tools into
# one moves the choice out of tool selection and into this enum.
# ---------------------------------------------------------------------------

MapQueryOperation = Literal[
    "search_layers",
    "layer_info",
    "features_at_point",
    "features_by_attribute",
    "feature_by_id",
]

# Per operation: (required fields, additionally accepted fields).
#
# Anything outside the union is refused rather than ignored. Silently dropping
# `search_field` from a `features_at_point` call would answer a question nobody
# asked and look like a successful result — the failure mode ARCH-003 is about,
# and the one a merged tool is most exposed to, since every operation's fields
# are visible on every call.
_OPERATION_FIELDS: dict[str, tuple[frozenset[str], frozenset[str]]] = {
    "search_layers": (frozenset({"query"}), frozenset({"lang", "limit"})),
    "layer_info": (frozenset({"layer"}), frozenset({"lang"})),
    "features_at_point": (
        frozenset({"layers"}),
        frozenset({"lat", "lon", "easting", "northing", "tolerance"}),
    ),
    "features_by_attribute": (
        frozenset({"layer", "search_text", "search_field"}),
        frozenset({"contains"}),
    ),
    "feature_by_id": (frozenset({"layer", "feature_id"}), frozenset({"sr"})),
}


class MapQueryInput(BaseModel):
    """One question against the national swisstopo map catalogue.

    `operation` says what is being asked; the remaining fields are that
    operation's arguments. Fields belonging to a different operation are
    rejected with a message naming the ones this operation accepts.
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid", strict=True)

    operation: MapQueryOperation = Field(
        ...,
        description=(
            "search_layers: Layer-IDs zu einem Suchbegriff finden (Einstieg). "
            "layer_info: abfragbare Felder und Legende eines Layers. "
            "features_at_point: Features an einer Koordinate («was liegt hier?»). "
            "features_by_attribute: Features mit einem bestimmten Attributwert. "
            "feature_by_id: ein einzelnes Feature per Layer- und Feature-ID."
        ),
    )

    # --- search_layers ---
    query: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
        pattern=TEXT_PATTERN,
        description="Suchbegriff für den Layer-Katalog (nur search_layers).",
    )

    # --- layer_info | features_by_attribute | feature_by_id ---
    layer: str | None = Field(
        default=None,
        min_length=2,
        max_length=128,
        pattern=ID_PATTERN,
        description=(
            "Eine Layer-ID (layer_info, features_by_attribute, feature_by_id)."
        ),
    )

    # --- features_at_point ---
    layers: str | None = Field(
        default=None,
        min_length=2,
        max_length=512,
        pattern=ID_PATTERN,
        description=(
            "Layer-IDs, kommagetrennt, z.B. 'ch.bfs.gebaeude_wohnungs_register' "
            "(nur features_at_point — Plural, weil hier mehrere Layer auf einmal "
            "abgefragt werden können)."
        ),
    )
    lat: float | None = Field(
        default=None,
        ge=CH_LAT_MIN,
        le=CH_LAT_MAX,
        description="Breitengrad (WGS84), zusammen mit lon. Nur features_at_point.",
    )
    lon: float | None = Field(
        default=None,
        ge=CH_LON_MIN,
        le=CH_LON_MAX,
        description="Längengrad (WGS84), zusammen mit lat. Nur features_at_point.",
    )
    easting: float | None = Field(
        default=None,
        description=(
            "LV95-Ostwert in Metern (EPSG:2056, z.B. 2683531), zusammen mit "
            "northing. Nur features_at_point."
        ),
    )
    northing: float | None = Field(
        default=None,
        description=(
            "LV95-Nordwert in Metern (EPSG:2056, z.B. 1247914), zusammen mit "
            "easting. Nur features_at_point."
        ),
    )
    tolerance: int = Field(
        default=0, ge=0, le=200, description="Suchradius in Pixeln (nur features_at_point)."
    )

    # --- features_by_attribute ---
    search_text: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
        pattern=TEXT_PATTERN,
        description="Gesuchter Attributwert (nur features_by_attribute).",
    )
    search_field: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        pattern=ID_PATTERN,
        description=(
            "Attributfeld, in dem gesucht wird (nur features_by_attribute). "
            "Zulässige Feldnamen liefert operation='layer_info'."
        ),
    )
    contains: bool = Field(
        default=True,
        description="Teilstring-Suche (True) oder exakt (False). Nur features_by_attribute.",
    )

    # --- feature_by_id ---
    feature_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        pattern=ID_PATTERN,
        description="Feature-ID innerhalb des Layers (nur feature_by_id).",
    )
    sr: int = Field(
        default=4326,
        description="Koordinatensystem der Ausgabegeometrie (nur feature_by_id).",
    )

    # --- shared ---
    lang: str = Field(
        default="de",
        pattern=LANG_PATTERN,
        description="Sprache: de, fr, it, en (search_layers, layer_info).",
    )
    limit: int = Field(
        default=10, ge=1, le=30, description="Max. Trefferzahl (nur search_layers)."
    )

    @field_validator("sr")
    @classmethod
    def _validate_sr(cls, v: int) -> int:
        return validate_sr(v)

    @model_validator(mode="after")
    def _check_operation(self) -> MapQueryInput:
        required, optional = _OPERATION_FIELDS[self.operation]

        missing = sorted(name for name in required if getattr(self, name) is None)
        if missing:
            raise ValueError(
                f"operation='{self.operation}' benötigt {', '.join(sorted(required))}. "
                f"Fehlend: {', '.join(missing)}."
            )

        # `model_fields_set` rather than a None-check: `tolerance`, `contains`,
        # `lang`, `limit` and `sr` have non-None defaults, so only the set of
        # *explicitly supplied* fields distinguishes "sent by mistake" from
        # "left at its default".
        stray = sorted(self.model_fields_set - {"operation"} - required - optional)
        if stray:
            raise ValueError(
                f"{', '.join(stray)} gehört nicht zu operation='{self.operation}' "
                f"und würde ignoriert. Diese operation akzeptiert: "
                f"{', '.join(sorted(required | optional))}."
            )

        if self.operation == "features_at_point":
            # Delegate rather than restate. SwissPointInput owns the
            # exactly-one-complete-pair rule *and* the messages that tell a
            # caller which mistake they made — degrees in the LV95 fields, half
            # a pair, a point outside Switzerland. Re-implementing that here
            # would give this one tool worse errors than every other
            # point-taking tool in the server.
            SwissPointInput(
                lat=self.lat,
                lon=self.lon,
                easting=self.easting,
                northing=self.northing,
            )
        return self


# ---------------------------------------------------------------------------
# Formatting Helpers
# ---------------------------------------------------------------------------

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def _strip_html(text: str) -> str:
    """Remove HTML tags from a string."""
    return _HTML_TAG_RE.sub("", text) if text else ""


def html_to_text(raw: str) -> str:
    """Reduce an HTML fragment to plain text — the legend endpoint serves HTML."""
    text = _HTML_TAG_RE.sub(" ", raw)
    text = html.unescape(text)
    return _WS_RE.sub(" ", text).strip()


def _as_bfs_number(value: Any) -> int | None:
    """Normalise a BFS commune number to int.

    The layers disagree: `ch.are.bauzonen` serves `bfs_no` as a string, while
    swissBOUNDARIES3D serves `gde_nr` as an int. Callers use this as the join
    key to swiss-statistics-mcp / zurich-opendata-mcp, so it must not depend on
    which tool produced it.
    """
    if value is None:
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def format_zoning(zones: list[dict[str, Any]]) -> str:
    """Format building zones as a Markdown list."""
    if not zones:
        return "Keine Bauzone an dieser Position (ausserhalb Bauzone oder ausserhalb CH)."
    lines = [f"**{len(zones)} Bauzone(n) an dieser Position:**\n"]
    for z in zones:
        lines.append(
            f"- **{z.get('zone_type_de') or '?'}** (Code {z.get('code') or '?'}) — "
            f"{z.get('municipality') or '?'}, {z.get('canton') or '?'}"
        )
    lines.append(f"\n> {ARE_ZONING_CAVEAT}")
    return "\n".join(lines)


def format_municipality(record: dict[str, Any] | None) -> str:
    """Format a municipality lookup result."""
    if not record:
        return "Keine aktuelle Gemeinde an dieser Position (ausserhalb CH oder auf einer Grenze)."
    return (
        f"**{record.get('municipality')}** (BFS-Nr. {record.get('bfs_commune_number')}, "
        f"Kanton {record.get('canton')})"
    )


def format_layer_info(meta: dict[str, Any]) -> str:
    """Format layer metadata as a Markdown table of queryable fields."""
    fields = meta.get("fields", [])
    lines = [
        f"## {meta.get('name') or meta.get('layer_id')}\n",
        f"**Layer-ID:** `{meta.get('layer_id')}`\n",
    ]
    if fields:
        lines.append(f"### Abfragbare Felder ({len(fields)})\n")
        lines.append("| Feld | Typ | Beispielwerte |")
        lines.append("|------|-----|---------------|")
        for f in fields:
            examples = ", ".join(str(v) for v in (f.get("example_values") or [])[:5])
            lines.append(f"| `{f.get('name')}` | {f.get('type') or '?'} | {examples} |")
        lines.append(
            "\nDiese Feldnamen können als `search_field` an operation="
            "'features_by_attribute' übergeben werden."
        )
    else:
        lines.append("Keine abfragbaren Felder gemeldet.")

    legend = meta.get("legend")
    if legend:
        lines.append(f"\n### Legende\n\n{legend}")
    return "\n".join(lines)


def format_layer_results(results: list[dict[str, Any]], query: str) -> str:
    """Format search_layers results as a Markdown table."""
    if not results:
        return f"Keine Layer gefunden für '{query}'."

    lines = [
        f"**{len(results)} Layer gefunden für '{query}':**\n",
        "| Layer-ID | Name | Beschreibung |",
        "|----------|------|--------------|",
    ]
    for r in results:
        layer_id = r.get("id", "?")
        attrs = r.get("attrs", {})
        label = _strip_html(attrs.get("label", ""))
        detail = _strip_html(attrs.get("detail", ""))
        lines.append(f"| {layer_id} | {label} | {detail} |")
    return "\n".join(lines)


def format_identify_results(results: list[dict[str, Any]]) -> str:
    """Format identify results, grouped by layer."""
    if not results:
        return "Keine Features gefunden an dieser Position."

    # Group by layer
    by_layer: dict[str, list[dict]] = {}
    for r in results:
        key = r.get("layerBodId", "unknown")
        by_layer.setdefault(key, []).append(r)

    lines = [f"**{len(results)} Feature(s) gefunden:**\n"]
    for layer_id, features in by_layer.items():
        layer_name = features[0].get("layerName", layer_id)
        lines.append(f"### {layer_name} (`{layer_id}`)\n")
        for feat in features:
            fid = feat.get("featureId", "?")
            lines.append(f"**Feature {fid}**\n")
            attrs = feat.get("attributes", {})
            for k, v in attrs.items():
                lines.append(f"- **{k}**: {v}")
            lines.append("")
    return "\n".join(lines)


def format_find_results(results: list[dict[str, Any]]) -> str:
    """Format find results as a list of features with attributes."""
    if not results:
        return "Keine Features gefunden."

    lines = [f"**{len(results)} Feature(s) gefunden:**\n"]
    for r in results:
        layer_id = r.get("layerBodId", "?")
        layer_name = r.get("layerName", layer_id)
        fid = r.get("featureId", "?")
        lines.append(f"### Feature {fid} ({layer_name})\n")
        attrs = r.get("attributes", {})
        for k, v in attrs.items():
            lines.append(f"- **{k}**: {v}")
        lines.append("")
    return "\n".join(lines)


def format_feature_detail(data: dict[str, Any]) -> str:
    """Format a single feature detail response."""
    feat = data.get("feature", {})
    fid = feat.get("featureId", "?")
    layer_id = feat.get("layerBodId", "?")
    layer_name = feat.get("layerName", layer_id)

    lines = [
        f"## Feature {fid}\n",
        f"**Layer:** {layer_name} (`{layer_id}`)\n",
        "### Attribute\n",
    ]
    attrs = feat.get("attributes", {})
    for k, v in attrs.items():
        lines.append(f"- **{k}**: {v}")

    geometry = feat.get("geometry")
    if geometry:
        geo_type = geometry.get("type", "?")
        lines.append("\n### Geometrie\n")
        lines.append(f"- **Typ**: {geo_type}")
        coords = geometry.get("coordinates")
        if coords and geo_type == "Point":
            lines.append(f"- **Koordinaten**: {coords}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Async Handler Functions
# ---------------------------------------------------------------------------


@log_tool_call("swisstopo_map_query:search_layers")
async def search_layers(params: SearchLayersInput) -> ToolResponse:
    """Search the swisstopo layer catalogue."""
    try:
        data = await geo_admin_request(
            "/rest/services/ech/SearchServer",
            {
                "type": "layers",
                "searchText": params.query,
                "lang": params.lang,
                "limit": params.limit,
            },
        )
        results = data.get("results", [])
        return ToolResponse.ok(
            format_layer_results(results, params.query),
            results,
            match_type="exact" if results else "none",
            note=None
            if results
            else (
                f"Keine Layer für «{params.query}» gefunden. Versuche einen kürzeren "
                "oder allgemeineren Begriff (z.B. «bauzonen» statt «bauzonen zürich»), "
                "oder eine andere Sprache via lang."
            ),
        )
    except Exception as e:
        return ToolResponse.error(handle_api_error(e, "Layer-Suche"))


@log_tool_call("swisstopo_map_query:features_at_point")
async def identify_features(params: IdentifyInput) -> ToolResponse:
    """Identify features at a coordinate."""
    try:
        lat, lon = params.as_wgs84
        data = await geo_admin_request(
            "/rest/services/ech/MapServer/identify",
            {
                "geometry": f"{lon},{lat}",
                "geometryType": "esriGeometryPoint",
                "layers": f"all:{params.layers}",
                "tolerance": params.tolerance,
                "sr": 4326,
                "returnGeometry": "false",
                "mapExtent": f"{lon - 0.01},{lat - 0.01},{lon + 0.01},{lat + 0.01}",
                "imageDisplay": "100,100,96",
            },
        )
        results = data.get("results", [])
        return ToolResponse.ok(
            format_identify_results(results),
            results,
            match_type="exact" if results else "none",
            note=None
            if results
            else (
                f"Keine Features von «{params.layers}» an dieser Position. Der Layer "
                "deckt diesen Punkt womöglich nicht ab — tolerance erhöhen (Suchradius "
                "in Pixeln) oder die Layer-ID via operation='search_layers' prüfen."
            ),
        )
    except Exception as e:
        return ToolResponse.error(handle_api_error(e, "Feature-Identifikation"))


@log_tool_call("swisstopo_map_query:features_by_attribute")
async def find_features(params: FindFeaturesInput) -> ToolResponse:
    """Find features by attribute value."""
    try:
        data = await geo_admin_request(
            "/rest/services/ech/MapServer/find",
            {
                "layer": params.layer,
                "searchText": params.search_text,
                "searchField": params.search_field,
                "contains": str(params.contains).lower(),
            },
        )
        results = data.get("results", [])
        return ToolResponse.ok(
            format_find_results(results),
            results,
            match_type="exact" if results else "none",
            note=None
            if results
            else (
                f"Kein Feature mit {params.search_field}=«{params.search_text}» in "
                f"{params.layer}. Mit operation='layer_info' die zulässigen Feldnamen "
                "und Beispielwerte dieses Layers prüfen, oder contains=True setzen."
            ),
        )
    except Exception as e:
        return ToolResponse.error(handle_api_error(e, "Feature-Suche"))


@log_tool_call("swisstopo_map_query:feature_by_id")
async def get_feature(params: GetFeatureInput) -> ToolResponse:
    """Get full details for a single feature."""
    try:
        data = await geo_admin_request(
            f"/rest/services/ech/MapServer/{params.layer}/{params.feature_id}",
            {"sr": params.sr},
        )
        feature = data.get("feature")
        records = [feature] if isinstance(feature, dict) else []
        return ToolResponse.ok(
            format_feature_detail(data),
            records,
            match_type="exact" if records else "none",
            note=(
                None if records else
                f"Feature '{params.feature_id}' existiert im Layer "
                f"'{params.layer}' nicht. Feature-IDs mit "
                "operation='features_at_point' oder 'features_by_attribute' "
                "ermitteln — sie sind layer-spezifisch."
            ),
        )
    except Exception as e:
        return ToolResponse.error(handle_api_error(e, "Feature-Abruf"))


async def _identify_lv95(layer: str, easting: float, northing: float, limit: int) -> list[dict]:
    """Run a MapServer identify at an LV95 point and return the raw results.

    Shared by the zoning and municipality lookups. Both layers are LV95-native,
    so the point goes upstream in LV95 rather than being converted.
    """
    data = await geo_admin_request(
        "/rest/services/ech/MapServer/identify",
        {
            "geometry": f"{easting},{northing}",
            "geometryType": "esriGeometryPoint",
            "layers": f"all:{layer}",
            "mapExtent": "0,0,100,100",
            "imageDisplay": "100,100,96",
            "tolerance": 0,
            "sr": 2056,
            "lang": "de",
            "returnGeometry": "false",
        },
    )
    results = data.get("results", [])
    return results[:limit] if isinstance(results, list) else []


@log_tool_call("swisstopo_zoning_at")
async def zoning_at(params: ZoningAtInput) -> ToolResponse:
    """Return the harmonised building zone(s) at a point."""
    try:
        easting, northing = params.as_lv95
        results = await _identify_lv95(ZONING_LAYER, easting, northing, limit=10)
        zones = [
            {
                "zone_type_de": a.get("ch_bez_d"),
                "zone_type_fr": a.get("ch_bez_f"),
                "code": a.get("ch_code_hn"),
                "municipality": a.get("name"),
                "bfs_commune_number": _as_bfs_number(a.get("bfs_no")),
                "canton": a.get("kt_kz"),
                # Carried on every record, not just in the summary: a client
                # reading `results` must not lose the legal caveat.
                "legal_note": ARE_ZONING_CAVEAT,
            }
            for a in (r.get("attributes", {}) for r in results)
        ]
        return ToolResponse.ok(
            format_zoning(zones),
            zones,
            match_type="exact" if zones else "none",
            note=(
                None if zones else
                "Keine Bauzone an dieser Position — der Punkt liegt ausserhalb "
                "der Bauzone (Landwirtschafts-/Schutzgebiet) oder ausserhalb der "
                "Schweiz. swisstopo_municipality_at zeigt, ob der Punkt überhaupt "
                "in einer Gemeinde liegt; die rechtsverbindliche Nutzungsplanung "
                "gibt es via swisstopo_query_geodata "
                "(geodienste:nutzungsplanung:<KANTON>)."
            ),
            source=ARE_SOURCE,
            license=ARE_LICENSE,
        )
    except Exception as e:
        return ToolResponse.error(
            handle_api_error(e, "Bauzonen-Abfrage"), source=ARE_SOURCE, license=ARE_LICENSE
        )


@log_tool_call("swisstopo_municipality_at")
async def municipality_at(params: MunicipalityAtInput) -> ToolResponse:
    """Return the municipality, BFS number and canton containing a point."""
    try:
        easting, northing = params.as_lv95
        # The layer carries one polygon per historical year (177 at the time of
        # writing for Zürich), so the current-year record must be selected.
        results = await _identify_lv95(MUNICIPALITY_LAYER, easting, northing, limit=200)
        current = [
            a
            for a in (r.get("attributes", {}) for r in results)
            if a.get("is_current_jahr") is True
        ]
        records = []
        if current:
            a = current[0]
            records.append(
                {
                    "municipality": a.get("gemname"),
                    "bfs_commune_number": _as_bfs_number(a.get("gde_nr")),
                    "canton": a.get("kanton"),
                }
            )
        return ToolResponse.ok(
            format_municipality(records[0] if records else None),
            records,
            match_type="exact" if records else "none",
            note=(
                None if records else
                "Keine Gemeinde an dieser Position — der Punkt liegt ausserhalb "
                "der Schweiz oder auf einem See ohne Gemeindezuordnung. "
                "Koordinaten prüfen (lat/lon, nicht LV95)."
            ),
            source=SWISSBOUNDARIES_SOURCE,
            license=SWISSBOUNDARIES_LICENSE,
        )
    except Exception as e:
        return ToolResponse.error(
            handle_api_error(e, "Gemeinde-Abfrage"),
            source=SWISSBOUNDARIES_SOURCE,
            license=SWISSBOUNDARIES_LICENSE,
        )


@log_tool_call("swisstopo_map_query:layer_info")
async def layer_info(
    params: LayerInfoInput, ctx: Context | None = None
) -> ToolResponse:
    """Return the queryable fields and the legend of a layer."""
    try:
        data = await geo_admin_request(
            f"/rest/services/api/MapServer/{params.layer}", ctx=ctx
        )
        if not isinstance(data, dict):
            return ToolResponse.error(
                f"Fehler bei Layer-Info: Unerwartetes Antwortformat für '{params.layer}'."
            )
        meta: dict[str, Any] = {
            "layer_id": data.get("id", params.layer),
            "name": data.get("name"),
            "fields": [
                {
                    "name": f.get("name"),
                    "type": f.get("type"),
                    "example_values": (f.get("values") or [])[:10],
                }
                for f in data.get("fields", [])
            ],
        }

        # The legend is a separate endpoint and a nice-to-have: a layer without
        # one must still return its fields rather than failing the whole call.
        # But swallowing the failure silently left the caller unable to tell
        # "this layer has no legend" from "the legend fetch broke", which are
        # different facts (audit SDK-003). The distinction now travels in
        # `legend_status`, and — when a context is available — as a warning.
        try:
            response = await geo_admin_request_text(
                f"/rest/services/all/MapServer/{params.layer}/legend",
                {"lang": params.lang},
                ctx=ctx,
            )
            meta["legend"] = html_to_text(response)
            meta["legend_status"] = "ok" if meta["legend"] else "empty"
        except Exception as exc:  # noqa: BLE001 - the legend is optional
            meta["legend"] = None
            meta["legend_status"] = "unavailable"
            _log.warning(
                "legend_fetch_failed", layer=params.layer, error_type=type(exc).__name__
            )
            if ctx is not None:
                try:
                    await ctx.warning(
                        f"Legende für '{params.layer}' konnte nicht geladen werden — "
                        "die Feldliste ist vollständig, die Legende fehlt."
                    )
                except Exception:  # noqa: BLE001 - reporting is best-effort
                    pass

        return ToolResponse.ok(format_layer_info(meta), [meta], match_type="exact")
    except Exception as e:
        return ToolResponse.error(handle_api_error(e, "Layer-Info"))


# ---------------------------------------------------------------------------
# Dispatcher for the merged tool (audit ARCH-006)
#
# Deliberately *not* wrapped in @log_tool_call. Each operation handler above
# keeps its own decorator, relabelled `swisstopo_map_query:<operation>`, so logs
# and traces still carry which of the five ran. Merging five tools into one
# normally costs exactly that granularity — here it does not, and one span per
# call is emitted rather than two nested ones.
# ---------------------------------------------------------------------------


async def map_query(params: MapQueryInput, ctx: Context | None = None) -> ToolResponse:
    """Route one validated MapQueryInput to the handler for its operation.

    The sub-models are rebuilt rather than bypassed. They carry the per-field
    constraints that have accumulated on this surface — the deprecated-`sr`
    check on the point path among them — and validating twice is cheap next to
    an HTTP round trip.
    """
    if params.operation == "search_layers":
        assert params.query is not None  # enforced by _check_operation
        return await search_layers(
            SearchLayersInput(query=params.query, lang=params.lang, limit=params.limit)
        )

    if params.operation == "layer_info":
        assert params.layer is not None
        return await layer_info(
            LayerInfoInput(layer=params.layer, lang=params.lang), ctx
        )

    if params.operation == "features_at_point":
        assert params.layers is not None
        return await identify_features(
            IdentifyInput(
                layers=params.layers,
                tolerance=params.tolerance,
                lat=params.lat,
                lon=params.lon,
                easting=params.easting,
                northing=params.northing,
            )
        )

    if params.operation == "features_by_attribute":
        assert params.layer is not None
        assert params.search_text is not None
        assert params.search_field is not None
        return await find_features(
            FindFeaturesInput(
                layer=params.layer,
                search_text=params.search_text,
                search_field=params.search_field,
                contains=params.contains,
            )
        )

    if params.operation == "feature_by_id":
        assert params.layer is not None
        assert params.feature_id is not None
        return await get_feature(
            GetFeatureInput(
                layer=params.layer, feature_id=params.feature_id, sr=params.sr
            )
        )

    # Spelled out rather than left as a trailing else: adding an operation to
    # MapQueryOperation and _OPERATION_FIELDS without a branch here would
    # otherwise land silently in whichever handler happened to be last.
    raise ValueError(f"Unbehandelte operation: {params.operation!r}")
