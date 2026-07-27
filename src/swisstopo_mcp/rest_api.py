# src/swisstopo_mcp/rest_api.py
"""REST API tools for api3.geo.admin.ch (SearchServer, MapServer)."""
from __future__ import annotations

import html
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from swisstopo_mcp.api_client import (
    ID_PATTERN,
    LANG_PATTERN,
    TEXT_PATTERN,
    geo_admin_request,
    geo_admin_request_text,
    handle_api_error,
    validate_sr,
)
from swisstopo_mcp.coords import SwissPointInput, check_deprecated_sr
from swisstopo_mcp.logging_config import log_tool_call
from swisstopo_mcp.models import (
    ARE_LICENSE,
    ARE_SOURCE,
    ARE_ZONING_CAVEAT,
    SWISSBOUNDARIES_LICENSE,
    SWISSBOUNDARIES_SOURCE,
    ToolResponse,
)

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
            "\nDiese Feldnamen können als `search_field` an swisstopo_find_features "
            "übergeben werden."
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


@log_tool_call("swisstopo_search_layers")
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


@log_tool_call("swisstopo_identify_features")
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
                "in Pixeln) oder die Layer-ID via swisstopo_search_layers prüfen."
            ),
        )
    except Exception as e:
        return ToolResponse.error(handle_api_error(e, "Feature-Identifikation"))


@log_tool_call("swisstopo_find_features")
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
                f"{params.layer}. Mit swisstopo_layer_info die zulässigen Feldnamen "
                "und Beispielwerte dieses Layers prüfen, oder contains=True setzen."
            ),
        )
    except Exception as e:
        return ToolResponse.error(handle_api_error(e, "Feature-Suche"))


@log_tool_call("swisstopo_get_feature")
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
            source=SWISSBOUNDARIES_SOURCE,
            license=SWISSBOUNDARIES_LICENSE,
        )
    except Exception as e:
        return ToolResponse.error(
            handle_api_error(e, "Gemeinde-Abfrage"),
            source=SWISSBOUNDARIES_SOURCE,
            license=SWISSBOUNDARIES_LICENSE,
        )


@log_tool_call("swisstopo_layer_info")
async def layer_info(params: LayerInfoInput) -> ToolResponse:
    """Return the queryable fields and the legend of a layer."""
    try:
        data = await geo_admin_request(f"/rest/services/api/MapServer/{params.layer}")
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
        try:
            response = await geo_admin_request_text(
                f"/rest/services/all/MapServer/{params.layer}/legend",
                {"lang": params.lang},
            )
            meta["legend"] = html_to_text(response)
        except Exception:
            meta["legend"] = None

        return ToolResponse.ok(format_layer_info(meta), [meta], match_type="exact")
    except Exception as e:
        return ToolResponse.error(handle_api_error(e, "Layer-Info"))
