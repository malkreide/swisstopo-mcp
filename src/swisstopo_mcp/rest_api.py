# src/swisstopo_mcp/rest_api.py
"""REST API tools for api3.geo.admin.ch (SearchServer, MapServer)."""
from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from swisstopo_mcp.api_client import geo_admin_request, handle_api_error


# ---------------------------------------------------------------------------
# Input Models
# ---------------------------------------------------------------------------


class SearchLayersInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    query: str = Field(..., min_length=1, max_length=200, description="Suchbegriff für Layer-Katalog")
    lang: str = Field(default="de", description="Sprache: de, fr, it, en")
    limit: int = Field(default=10, ge=1, le=30)


class IdentifyInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    layers: str = Field(..., min_length=2, description="Layer-IDs, kommagetrennt, z.B. 'ch.bfs.gebaeude_wohnungs_register'")
    lat: float = Field(..., ge=45.8, le=47.9, description="Breitengrad (WGS84)")
    lon: float = Field(..., ge=5.9, le=10.5, description="Längengrad (WGS84)")
    tolerance: int = Field(default=0, ge=0, le=200, description="Suchradius in Pixeln")
    sr: int = Field(default=4326, description="Koordinatensystem")


class FindFeaturesInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    layer: str = Field(..., min_length=2, description="Layer-ID")
    search_text: str = Field(..., min_length=1, description="Suchwert")
    search_field: str = Field(..., min_length=1, description="Attributfeld")
    contains: bool = Field(default=True, description="Teilstring-Suche (True) oder exakt (False)")


class GetFeatureInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    layer: str = Field(..., min_length=2, description="Layer-ID")
    feature_id: str = Field(..., min_length=1, description="Feature-ID")
    sr: int = Field(default=4326, description="Koordinatensystem")


# ---------------------------------------------------------------------------
# Formatting Helpers
# ---------------------------------------------------------------------------

_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    """Remove HTML tags from a string."""
    return _HTML_TAG_RE.sub("", text) if text else ""


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
        lines.append(f"\n### Geometrie\n")
        lines.append(f"- **Typ**: {geo_type}")
        coords = geometry.get("coordinates")
        if coords and geo_type == "Point":
            lines.append(f"- **Koordinaten**: {coords}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Async Handler Functions
# ---------------------------------------------------------------------------


async def search_layers(params: SearchLayersInput) -> str:
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
        return format_layer_results(results, params.query)
    except Exception as e:
        return handle_api_error(e, "Layer-Suche")


async def identify_features(params: IdentifyInput) -> str:
    """Identify features at a coordinate."""
    try:
        lon, lat = params.lon, params.lat
        data = await geo_admin_request(
            "/rest/services/ech/MapServer/identify",
            {
                "geometry": f"{lon},{lat}",
                "geometryType": "esriGeometryPoint",
                "layers": f"all:{params.layers}",
                "tolerance": params.tolerance,
                "sr": params.sr,
                "returnGeometry": "false",
                "mapExtent": f"{lon - 0.01},{lat - 0.01},{lon + 0.01},{lat + 0.01}",
                "imageDisplay": "100,100,96",
            },
        )
        results = data.get("results", [])
        return format_identify_results(results)
    except Exception as e:
        return handle_api_error(e, "Feature-Identifikation")


async def find_features(params: FindFeaturesInput) -> str:
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
        return format_find_results(results)
    except Exception as e:
        return handle_api_error(e, "Feature-Suche")


async def get_feature(params: GetFeatureInput) -> str:
    """Get full details for a single feature."""
    try:
        data = await geo_admin_request(
            f"/rest/services/ech/MapServer/{params.layer}/{params.feature_id}",
            {"sr": params.sr},
        )
        return format_feature_detail(data)
    except Exception as e:
        return handle_api_error(e, "Feature-Abruf")
