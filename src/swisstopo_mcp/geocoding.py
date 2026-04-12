# src/swisstopo_mcp/geocoding.py
"""Geocoding tools for api3.geo.admin.ch (SearchServer, location type)."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from swisstopo_mcp.api_client import geo_admin_request, handle_api_error

# ---------------------------------------------------------------------------
# Input Models
# ---------------------------------------------------------------------------


class GeocodeInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    search_text: str = Field(
        ...,
        min_length=2,
        max_length=200,
        description="Adresse, Ort, PLZ oder Parzelle",
    )
    origins: str | None = Field(
        default=None,
        description=(
            "Filter: 'address', 'zipcode', 'gg25', 'district', "
            "'kantone', 'gazetteer', 'parcel'"
        ),
    )
    sr: int = Field(default=4326, description="Koordinatensystem (EPSG-Code)")
    limit: int = Field(default=10, ge=1, le=50, description="Maximale Trefferanzahl")


class ReverseGeocodeInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    lat: float = Field(..., ge=45.8, le=47.9, description="Breitengrad (WGS84)")
    lon: float = Field(..., ge=5.9, le=10.5, description="Längengrad (WGS84)")
    limit: int = Field(default=5, ge=1, le=10, description="Maximale Trefferanzahl")
    sr: int = Field(default=4326, description="Koordinatensystem (EPSG-Code)")


# ---------------------------------------------------------------------------
# Formatting Helper
# ---------------------------------------------------------------------------


def format_geocode_results(results: list[dict[str, Any]]) -> str:
    """Format geocode results as a Markdown table."""
    if not results:
        return "Keine Ergebnisse gefunden."

    lines = [
        "| Adresse | Lat | Lon | Typ |",
        "|---------|-----|-----|-----|",
    ]
    for r in results:
        attrs = r.get("attrs", {})
        label = attrs.get("label", "?")
        lat = attrs.get("lat", "?")
        lon = attrs.get("lon", "?")
        origin = attrs.get("origin", "?")
        # Format coordinates to 6 decimal places if numeric
        if isinstance(lat, (int, float)):
            lat = f"{lat:.6f}"
        if isinstance(lon, (int, float)):
            lon = f"{lon:.6f}"
        lines.append(f"| {label} | {lat} | {lon} | {origin} |")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Async Handler Functions
# ---------------------------------------------------------------------------


async def geocode(params: GeocodeInput) -> str:
    """Convert an address, place name or postcode to coordinates."""
    try:
        query_params: dict[str, Any] = {
            "type": "locations",
            "searchText": params.search_text,
            "sr": params.sr,
            "limit": params.limit,
            "returnGeometry": "true",
        }
        if params.origins is not None:
            query_params["origins"] = params.origins

        data = await geo_admin_request(
            "/rest/services/ech/SearchServer",
            query_params,
        )
        results = data.get("results", [])
        return format_geocode_results(results)
    except Exception as e:
        return handle_api_error(e, "Geocoding")


async def reverse_geocode(params: ReverseGeocodeInput) -> str:
    """Find the nearest addresses to given coordinates."""
    try:
        # Build a ~500 m bounding box (approx. 0.005 degrees)
        bbox = (
            f"{params.lon - 0.005},{params.lat - 0.005},"
            f"{params.lon + 0.005},{params.lat + 0.005}"
        )
        data = await geo_admin_request(
            "/rest/services/ech/SearchServer",
            {
                "type": "locations",
                "origins": "address",
                "bbox": bbox,
                "limit": params.limit,
                "sr": params.sr,
                "returnGeometry": "true",
            },
        )
        results = data.get("results", [])
        return format_geocode_results(results)
    except Exception as e:
        return handle_api_error(e, "Reverse Geocoding")
