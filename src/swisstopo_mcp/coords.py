# src/swisstopo_mcp/coords.py
"""Official coordinate transformation via the swisstopo REFRAME service.

This module exposes REFRAME (``geodesy.geo.admin.ch``) as a tool. It is
deliberately *not* wired into the internal conversion path: `api_client`'s
`wgs84_to_lv95` / `lv95_to_wgs84` polynomials remain the fast path used by the
height, profile and identify tools. Measured against REFRAME at four points
across Switzerland the polynomials deviate by 0.05-0.20 m — below the tolerance
those tools operate at — so routing them through the network would buy
irrelevant precision at the cost of a roundtrip per call.

Where centimetres do matter (cadastral work, parcel boundaries), callers reach
for this tool explicitly.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from swisstopo_mcp.api_client import handle_api_error, reframe_request
from swisstopo_mcp.logging_config import log_tool_call
from swisstopo_mcp.models import REFRAME_SOURCE, ToolResponse

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

Direction = Literal["wgs84_to_lv95", "lv95_to_wgs84"]

# REFRAME endpoint per direction.
_ENDPOINTS: dict[str, str] = {
    "wgs84_to_lv95": "/wgs84tolv95",
    "lv95_to_wgs84": "/lv95towgs84",
}

# LV95 (EPSG:2056) extent of Switzerland, matching the WGS84 bbox already
# enforced elsewhere in the server (CH_LAT/LON bounds in api_client).
LV95_E_MIN, LV95_E_MAX = 2_480_000.0, 2_840_000.0
LV95_N_MIN, LV95_N_MAX = 1_070_000.0, 1_300_000.0


# ---------------------------------------------------------------------------
# Input Model
# ---------------------------------------------------------------------------


class ConvertCoordinatesInput(BaseModel):
    """Input for `swisstopo_convert_coordinates`.

    Note the axis order: REFRAME labels both inputs `easting`/`northing`
    regardless of direction. For `wgs84_to_lv95` that means **easting carries
    the longitude and northing the latitude** — the reverse of the `lat`/`lon`
    argument order used by the rest of this server. The validator below rejects
    swapped values rather than silently returning a point in the wrong place.
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid", strict=True)

    easting: float = Field(
        ...,
        description=(
            "X axis. For wgs84_to_lv95: the LONGITUDE in degrees (e.g. 8.5417). "
            "For lv95_to_wgs84: the LV95 easting in metres (e.g. 2683531)."
        ),
    )
    northing: float = Field(
        ...,
        description=(
            "Y axis. For wgs84_to_lv95: the LATITUDE in degrees (e.g. 47.3769). "
            "For lv95_to_wgs84: the LV95 northing in metres (e.g. 1247914)."
        ),
    )
    direction: Direction = Field(
        default="wgs84_to_lv95",
        description="Conversion direction: wgs84_to_lv95 | lv95_to_wgs84.",
    )

    @model_validator(mode="after")
    def _check_ranges(self) -> ConvertCoordinatesInput:
        """Range-check against the expected system, and catch swapped axes.

        Without this, passing latitude as `easting` produces a plausible-looking
        but wrong result far outside Switzerland.
        """
        if self.direction == "wgs84_to_lv95":
            if not (5.9 <= self.easting <= 10.5) or not (45.8 <= self.northing <= 47.9):
                raise ValueError(
                    "Für wgs84_to_lv95 erwartet: easting = Längengrad (5.9–10.5), "
                    f"northing = Breitengrad (45.8–47.9). Erhalten: easting={self.easting}, "
                    f"northing={self.northing}. Sind die Achsen vertauscht?"
                )
        else:
            if not (LV95_E_MIN <= self.easting <= LV95_E_MAX) or not (
                LV95_N_MIN <= self.northing <= LV95_N_MAX
            ):
                raise ValueError(
                    "Für lv95_to_wgs84 erwartet: easting in "
                    f"{LV95_E_MIN:.0f}–{LV95_E_MAX:.0f}, northing in "
                    f"{LV95_N_MIN:.0f}–{LV95_N_MAX:.0f} (Meter). Erhalten: "
                    f"easting={self.easting}, northing={self.northing}. "
                    "WGS84-Grad hier bitte mit direction='wgs84_to_lv95' umrechnen."
                )
        return self


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_float(value: Any) -> float:
    """Coerce a REFRAME value to float — the service returns numbers as JSON strings."""
    if isinstance(value, str):
        value = value.strip()
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Erwartet wurde ein numerischer Wert, erhalten: {value!r}") from exc


def format_conversion(
    easting: float, northing: float, direction: str
) -> str:
    """Format a conversion result as a human-readable German string."""
    if direction == "wgs84_to_lv95":
        return (
            f"LV95 (EPSG:2056): E {easting:.3f}, N {northing:.3f} "
            "— amtliche Umrechnung via swisstopo REFRAME."
        )
    return (
        f"WGS84 (EPSG:4326): {northing:.6f}, {easting:.6f} (lat, lon) "
        "— amtliche Umrechnung via swisstopo REFRAME."
    )


# ---------------------------------------------------------------------------
# Async Handler
# ---------------------------------------------------------------------------


@log_tool_call("swisstopo_convert_coordinates")
async def convert_coordinates(params: ConvertCoordinatesInput) -> ToolResponse:
    """Convert between WGS84 and LV95 using the official REFRAME service."""
    try:
        data = await reframe_request(
            _ENDPOINTS[params.direction],
            {
                "easting": params.easting,
                "northing": params.northing,
                "format": "json",
            },
        )
        if not isinstance(data, dict) or "easting" not in data or "northing" not in data:
            return ToolResponse.error(
                "Fehler bei Koordinatenumrechnung: REFRAME lieferte keine Koordinaten zurück.",
                source=REFRAME_SOURCE,
            )

        easting = _to_float(data["easting"])
        northing = _to_float(data["northing"])

        record: dict[str, Any] = {
            "easting": easting,
            "northing": northing,
            "direction": params.direction,
            "target_srid": 2056 if params.direction == "wgs84_to_lv95" else 4326,
        }
        # For the WGS84 target also surface the server's usual lat/lon naming, so
        # the result can be handed straight to the other tools without the caller
        # having to remember REFRAME's axis labels.
        if params.direction == "lv95_to_wgs84":
            record["lat"] = northing
            record["lon"] = easting

        return ToolResponse.ok(
            format_conversion(easting, northing, params.direction),
            [record],
            match_type="exact",
            source=REFRAME_SOURCE,
        )
    except ValueError as e:
        return ToolResponse.error(f"Fehler bei Eingabe: {e}", source=REFRAME_SOURCE)
    except Exception as e:
        return ToolResponse.error(
            handle_api_error(e, "Koordinatenumrechnung"), source=REFRAME_SOURCE
        )
