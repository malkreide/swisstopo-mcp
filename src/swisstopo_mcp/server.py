# src/swisstopo_mcp/server.py
from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "swisstopo_mcp",
    instructions=(
        "Swiss federal geodata server with 13 tools across 6 API families. "
        "Use swisstopo_search_layers to discover layer IDs, then use "
        "swisstopo_identify_features or swisstopo_find_features to query them. "
        "swisstopo_geocode converts addresses to coordinates. "
        "swisstopo_get_height returns elevation. "
        "swisstopo_search_geodata finds downloadable datasets (orthophotos, 3D models, etc.). "
        "swisstopo_map_url generates shareable map links. "
        "ÖREB tools (swisstopo_get_egrid, swisstopo_get_oereb_extract) require a canton parameter."
    ),
)

# --- Geocoding Tools ---
from swisstopo_mcp.geocoding import GeocodeInput, geocode, ReverseGeocodeInput, reverse_geocode


@mcp.tool(
    name="swisstopo_geocode",
    annotations={
        "title": "Adresse geocodieren",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def swisstopo_geocode(params: GeocodeInput) -> str:
    """Wandelt Adressen, Ortsnamen oder PLZ in Koordinaten um (Geocoding)."""
    return await geocode(params)


@mcp.tool(
    name="swisstopo_reverse_geocode",
    annotations={
        "title": "Koordinaten zu Adresse",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def swisstopo_reverse_geocode(params: ReverseGeocodeInput) -> str:
    """Findet die nächstgelegene Adresse zu gegebenen Koordinaten (Reverse Geocoding)."""
    return await reverse_geocode(params)


# --- REST API Tools ---
from swisstopo_mcp.rest_api import (
    SearchLayersInput,
    search_layers,
    IdentifyInput,
    identify_features,
    FindFeaturesInput,
    find_features,
    GetFeatureInput,
    get_feature,
)


@mcp.tool(
    name="swisstopo_search_layers",
    annotations={
        "title": "Swisstopo Layer suchen",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def swisstopo_search_layers(params: SearchLayersInput) -> str:
    """Durchsucht den Swisstopo-Layerkatalog (500+ Layer) nach Geodatensätzen."""
    return await search_layers(params)


@mcp.tool(
    name="swisstopo_identify_features",
    annotations={
        "title": "Features an Koordinate identifizieren",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def swisstopo_identify_features(params: IdentifyInput) -> str:
    """Findet Features an einer bestimmten Koordinate (räumliche Abfrage auf Swisstopo-Layern)."""
    return await identify_features(params)


@mcp.tool(
    name="swisstopo_find_features",
    annotations={
        "title": "Features nach Attribut suchen",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def swisstopo_find_features(params: FindFeaturesInput) -> str:
    """Sucht Features anhand eines Attributwerts in einem Layer (z.B. Gebäude nach EGID)."""
    return await find_features(params)


@mcp.tool(
    name="swisstopo_get_feature",
    annotations={
        "title": "Feature-Details abrufen",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def swisstopo_get_feature(params: GetFeatureInput) -> str:
    """Ruft die vollständigen Attribute und Geometrie eines Features per ID ab."""
    return await get_feature(params)


# --- STAC Tools ---
from swisstopo_mcp.stac import SearchGeodataInput, search_geodata, GetCollectionInput, get_collection


@mcp.tool(
    name="swisstopo_search_geodata",
    annotations={
        "title": "Geodaten suchen",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def swisstopo_search_geodata(params: SearchGeodataInput) -> str:
    """Durchsucht den STAC-Katalog nach Geodaten (Orthophotos, Höhenmodelle, 3D-Gebäude, historische Karten)."""
    return await search_geodata(params)


@mcp.tool(
    name="swisstopo_get_collection",
    annotations={
        "title": "Geodaten-Details abrufen",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def swisstopo_get_collection(params: GetCollectionInput) -> str:
    """Ruft Detailinformationen und Download-Links einer STAC-Collection ab."""
    return await get_collection(params)


# --- WMTS Tools ---
from swisstopo_mcp.wmts import MapUrlInput, build_map_url


@mcp.tool(
    name="swisstopo_map_url",
    annotations={
        "title": "Karten-URL generieren",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def swisstopo_map_url(params: MapUrlInput) -> str:
    """Generiert eine map.geo.admin.ch-URL zum Öffnen im Browser."""
    return await build_map_url(params)


# --- Height Tools ---
from swisstopo_mcp.height import HeightInput, get_height, ElevationProfileInput, elevation_profile


@mcp.tool(
    name="swisstopo_get_height",
    annotations={
        "title": "Höhe abfragen",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def swisstopo_get_height(params: HeightInput) -> str:
    """Gibt die Höhe über Meer (m ü. M.) an einer Koordinate zurück."""
    return await get_height(params)


@mcp.tool(
    name="swisstopo_elevation_profile",
    annotations={
        "title": "Höhenprofil berechnen",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def swisstopo_elevation_profile(params: ElevationProfileInput) -> str:
    """Berechnet ein Höhenprofil entlang einer Linie (z.B. für Schulweg-Analyse)."""
    return await elevation_profile(params)


def main():
    transport = os.environ.get("MCP_TRANSPORT", "stdio").lower()
    if transport in ("sse", "streamable-http"):
        port = int(os.environ.get("MCP_PORT", "8000"))
        mcp.run(transport=transport, port=port)
    else:
        mcp.run()


if __name__ == "__main__":
    main()
