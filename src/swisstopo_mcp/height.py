# src/swisstopo_mcp/height.py
"""Height and elevation profile tools for api3.geo.admin.ch."""
from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from swisstopo_mcp.api_client import (
    geo_admin_request,
    handle_api_error,
    parse_coordinate_string,
    wgs84_to_lv95,
)

# ---------------------------------------------------------------------------
# Input Models
# ---------------------------------------------------------------------------


class HeightInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    lat: float = Field(..., ge=45.8, le=47.9, description="Breitengrad (WGS84)")
    lon: float = Field(..., ge=5.9, le=10.5, description="Längengrad (WGS84)")
    sr: int = Field(default=4326, description="Koordinatensystem (EPSG-Code)")


class ElevationProfileInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    coordinates: str = Field(
        ...,
        min_length=5,
        description="Koordinaten im Format 'lat1,lon1;lat2,lon2;...'",
    )
    nb_points: int = Field(
        default=200,
        ge=2,
        le=1000,
        description="Anzahl Profilpunkte",
    )
    sr: int = Field(default=4326, description="Koordinatensystem (EPSG-Code)")


# ---------------------------------------------------------------------------
# Formatting Helpers
# ---------------------------------------------------------------------------


def format_height_result(lat: float, lon: float, height: str) -> str:
    """Format a single height result as a human-readable German string."""
    return f"Die Höhe bei ({lat}, {lon}) beträgt {height} m ü. M."


def format_elevation_profile(points: list[dict[str, Any]]) -> str:
    """Format elevation profile points as a compact Markdown table."""
    if not points:
        return "Keine Profilpunkte zurückgegeben."

    lines = [
        "| Distanz (m) | Höhe (m) | Steigung (%) |",
        "|-------------|----------|--------------|",
    ]

    for i, point in enumerate(points):
        dist = point.get("dist", 0.0)
        alts = point.get("alts", {})
        height = alts.get("COMB", alts.get("DTM2", alts.get("DTM25", "?")))

        # Calculate gradient vs previous point
        if i == 0:
            gradient_str = "—"
        else:
            prev = points[i - 1]
            prev_dist = prev.get("dist", 0.0)
            prev_alts = prev.get("alts", {})
            prev_height = prev_alts.get("COMB", prev_alts.get("DTM2", prev_alts.get("DTM25")))
            delta_dist = dist - prev_dist
            if (
                delta_dist > 0
                and isinstance(height, (int, float))
                and isinstance(prev_height, (int, float))
            ):
                gradient = ((height - prev_height) / delta_dist) * 100
                gradient_str = f"{gradient:.1f}"
            else:
                gradient_str = "—"

        if isinstance(height, (int, float)):
            height_str = f"{height:.1f}"
        else:
            height_str = str(height)

        if isinstance(dist, (int, float)):
            dist_str = f"{dist:.0f}"
        else:
            dist_str = str(dist)

        lines.append(f"| {dist_str} | {height_str} | {gradient_str} |")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Async Handler Functions
# ---------------------------------------------------------------------------


async def get_height(params: HeightInput) -> str:
    """Return the elevation above sea level for a WGS84 coordinate."""
    try:
        # Height API only supports LV95 (2056) and LV03 (21781), not WGS84
        if params.sr == 4326:
            easting, northing = wgs84_to_lv95(params.lat, params.lon)
            sr = 2056
        else:
            easting, northing = params.lon, params.lat
            sr = params.sr
        data = await geo_admin_request(
            "/rest/services/height",
            {
                "easting": easting,
                "northing": northing,
                "sr": sr,
            },
        )
        height = data.get("height", "?")
        return format_height_result(params.lat, params.lon, height)
    except Exception as e:
        return handle_api_error(e, "Höhenabfrage")


async def elevation_profile(params: ElevationProfileInput) -> str:
    """Compute an elevation profile along a line defined by coordinate pairs."""
    try:
        coord_pairs = parse_coordinate_string(params.coordinates)

        # Profile API only supports LV95 (2056) and LV03 (21781)
        # GeoJSON coordinates must also be in the target SR
        if params.sr == 4326:
            lv95_coords = [wgs84_to_lv95(lat, lon) for lat, lon in coord_pairs]
            geojson = {
                "type": "LineString",
                "coordinates": [[e, n] for e, n in lv95_coords],
            }
            sr = 2056
        else:
            geojson = {
                "type": "LineString",
                "coordinates": [[lon, lat] for lat, lon in coord_pairs],
            }
            sr = params.sr
        geojson_str = json.dumps(geojson, separators=(",", ":"))

        data = await geo_admin_request(
            "/rest/services/profile.json",
            {
                "geom": geojson_str,
                "nb_points": params.nb_points,
                "sr": sr,
            },
        )
        # data is a list of profile points
        if isinstance(data, list):
            return format_elevation_profile(data)
        return f"Unerwartetes Antwortformat: {type(data).__name__}"
    except ValueError as e:
        return f"Fehler bei Eingabe: {e}"
    except Exception as e:
        return handle_api_error(e, "Höhenprofil")
