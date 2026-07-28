# src/swisstopo_mcp/height.py
"""Height and elevation profile tools for api3.geo.admin.ch."""
from __future__ import annotations

import json
from typing import Any, Literal

from mcp.server.fastmcp import Context
from pydantic import BaseModel, ConfigDict, Field, model_validator

from swisstopo_mcp.api_client import (
    COORDS_PATTERN,
    geo_admin_request,
    handle_api_error,
    parse_coordinate_string,
    wgs84_to_lv95,
)
from swisstopo_mcp.coords import SwissPointInput, check_deprecated_sr
from swisstopo_mcp.logging_config import log_tool_call
from swisstopo_mcp.models import ToolResponse

# ---------------------------------------------------------------------------
# Input Models
# ---------------------------------------------------------------------------


class HeightInput(SwissPointInput):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid", strict=True)

    sr: int = Field(
        default=4326,
        description="Veraltet — nur noch 4326. Für LV95 easting/northing verwenden.",
    )

    @model_validator(mode="after")
    def _check_sr(self) -> HeightInput:
        check_deprecated_sr(self.sr)
        return self


class ElevationProfileInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid", strict=True)

    coordinates: str = Field(
        ...,
        min_length=5,
        max_length=2000,
        pattern=COORDS_PATTERN,
        description=(
            "Stützpunkte als 'x1,y1;x2,y2;…'. Bei coordinate_system='wgs84' "
            "(Standard) ist das 'lat,lon'; bei 'lv95' ist es 'easting,northing'."
        ),
    )
    coordinate_system: Literal["wgs84", "lv95"] = Field(
        default="wgs84",
        description="Koordinatensystem der Stützpunkte: wgs84 (lat,lon) oder lv95 (E,N).",
    )
    nb_points: int = Field(
        default=200,
        ge=2,
        le=1000,
        description="Anzahl Profilpunkte",
    )
    sr: int = Field(
        default=4326,
        description="Veraltet — nur noch 4326. Für LV95 coordinate_system='lv95' setzen.",
    )

    @model_validator(mode="after")
    def _check_sr(self) -> ElevationProfileInput:
        check_deprecated_sr(self.sr, alternative="coordinate_system='lv95'")
        return self


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


@log_tool_call("swisstopo_get_height")
async def get_height(params: HeightInput) -> ToolResponse:
    """Return the elevation above sea level for a WGS84 coordinate."""
    try:
        # The height API speaks LV95 only, so both input flavours resolve to it.
        easting, northing = params.as_lv95
        lat, lon = params.as_wgs84
        data = await geo_admin_request(
            "/rest/services/height",
            {
                "easting": easting,
                "northing": northing,
                "sr": 2056,
            },
        )
        height = data.get("height", "?")
        return ToolResponse.ok(
            format_height_result(lat, lon, height),
            [
                {
                    "lat": lat,
                    "lon": lon,
                    "easting": easting,
                    "northing": northing,
                    "height": height,
                }
            ],
        )
    except Exception as e:
        return ToolResponse.error(handle_api_error(e, "Höhenabfrage"))


@log_tool_call("swisstopo_elevation_profile")
async def elevation_profile(
    params: ElevationProfileInput, ctx: Context | None = None
) -> ToolResponse:
    """Compute an elevation profile along a line defined by coordinate pairs."""
    try:
        coord_pairs = parse_coordinate_string(params.coordinates)
        if ctx is not None:
            await ctx.info(f"Berechne Höhenprofil über {len(coord_pairs)} Stützpunkte …")

        # The profile API speaks LV95 only, so WGS84 input is converted first.
        # LV95 input arrives as (easting, northing) pairs and passes through.
        if params.coordinate_system == "lv95":
            lv95_coords = list(coord_pairs)
        else:
            lv95_coords = [wgs84_to_lv95(lat, lon) for lat, lon in coord_pairs]
        geojson = {
            "type": "LineString",
            "coordinates": [[e, n] for e, n in lv95_coords],
        }
        geojson_str = json.dumps(geojson, separators=(",", ":"))

        # Report *before* the await, not after it. The previous call fired
        # progress=1/total=1 once `geo_admin_request` had already returned — a
        # completion marker, not a cadence, so the actual wait was unreported
        # (audit SDK-003). The upstream call is a single request with no
        # intermediate signal, so the honest thing is to announce it, then
        # confirm on return.
        if ctx is not None:
            await ctx.report_progress(
                progress=0,
                total=params.nb_points,
                message=f"Fordere {params.nb_points} Profilpunkte an …",
            )
        data = await geo_admin_request(
            "/rest/services/profile.json",
            {
                "geom": geojson_str,
                "nb_points": params.nb_points,
                "sr": 2056,
            },
            ctx=ctx,
        )
        # data is a list of profile points
        if isinstance(data, list):
            if ctx is not None:
                await ctx.report_progress(
                    progress=len(data), total=params.nb_points,
                    message=f"{len(data)} Punkte",
                )
            return ToolResponse.ok(
                format_elevation_profile(data),
                data,
                match_type="exact" if data else "none",
                note=(
                    None
                    if data
                    else "Kein Höhenprofil — die Linie liegt vermutlich ausserhalb "
                    "der Schweiz oder ganz im Bereich ohne Höhenmodell. Einzelpunkte "
                    "mit swisstopo_get_height prüfen."
                ),
            )
        return ToolResponse.error(f"Fehler bei Höhenprofil: Unerwartetes Antwortformat: {type(data).__name__}")
    except ValueError as e:
        return ToolResponse.error(f"Fehler bei Eingabe: {e}")
    except Exception as e:
        return ToolResponse.error(handle_api_error(e, "Höhenprofil"))
