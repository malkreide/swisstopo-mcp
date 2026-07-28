# src/swisstopo_mcp/geocoding.py
"""Geocoding tools for api3.geo.admin.ch (SearchServer, location type)."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from swisstopo_mcp.api_client import (
    TEXT_PATTERN,
    geo_admin_request,
    handle_api_error,
    validate_sr,
)
from swisstopo_mcp.logging_config import log_tool_call
from swisstopo_mcp.models import ToolResponse

# The `origins` values SearchServer accepts. Kept as a frozenset rather than a
# Literal because the parameter is a comma-separated list (SEC-018).
ORIGINS = frozenset(
    {"address", "zipcode", "gg25", "district", "kantone", "gazetteer", "parcel"}
)

# ---------------------------------------------------------------------------
# Input Models
# ---------------------------------------------------------------------------


class GeocodeInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid", strict=True)

    search_text: str = Field(
        ...,
        min_length=2,
        max_length=200,
        pattern=TEXT_PATTERN,
        description="Adresse, Ort, PLZ oder Parzelle",
    )
    origins: str | None = Field(
        default=None,
        max_length=128,
        pattern=r"^[a-z0-9,]+$",
        description=(
            "Filter, kommagetrennt: 'address', 'zipcode', 'gg25', 'district', "
            "'kantone', 'gazetteer', 'parcel'"
        ),
    )
    sr: int = Field(default=4326, description="Koordinatensystem (EPSG-Code)")

    @field_validator("sr")
    @classmethod
    def _validate_sr(cls, v: int) -> int:
        # Wires up validate_sr(), which existed but was never called — an
        # arbitrary int used to be forwarded straight upstream (SEC-018).
        return validate_sr(v)

    @field_validator("origins")
    @classmethod
    def _validate_origins(cls, v: str | None) -> str | None:
        """Check each member against the documented set.

        The field is a comma-separated list, so a `Literal` cannot express it.
        The pattern only said "lowercase letters, digits and commas", which
        accepted anything of that shape — the description promised an enum the
        validation did not enforce (SEC-018).
        """
        if v is None:
            return v
        members = [m for m in v.split(",") if m]
        unknown = sorted({m for m in members if m not in ORIGINS})
        if unknown:
            raise ValueError(
                f"Unbekannte origins: {', '.join(unknown)}. "
                f"Erlaubt: {', '.join(sorted(ORIGINS))}."
            )
        return v

    limit: int = Field(default=10, ge=1, le=50, description="Maximale Trefferanzahl")


class ReverseGeocodeInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid", strict=True)

    lat: float = Field(..., ge=45.8, le=47.9, description="Breitengrad (WGS84)")
    lon: float = Field(..., ge=5.9, le=10.5, description="Längengrad (WGS84)")
    limit: int = Field(default=5, ge=1, le=10, description="Maximale Trefferanzahl")
    sr: int = Field(default=4326, description="Koordinatensystem (EPSG-Code)")

    @field_validator("sr")
    @classmethod
    def _validate_sr(cls, v: int) -> int:
        # Wires up validate_sr(), which existed but was never called — an
        # arbitrary int used to be forwarded straight upstream (SEC-018).
        return validate_sr(v)



# ---------------------------------------------------------------------------
# Formatting Helper
# ---------------------------------------------------------------------------


def format_geocode_results(results: list[dict[str, Any]]) -> str:
    """Format geocode results as a Markdown table."""
    if not results:
        return (
            "Keine Ergebnisse gefunden (match_type: none). "
            "Versuche einen kürzeren oder allgemeineren Suchbegriff, prüfe die "
            "Schreibweise, oder grenze mit dem Parameter `origins` ein "
            "(z.B. 'address', 'zipcode', 'gg25')."
        )

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


def _relax_query(search_text: str) -> str | None:
    """A broader form of a failed query, or None if there is nothing to relax.

    Two failures dominate in practice, and both are recoverable by dropping
    tokens from the right: a house number that does not exist in the register
    ("Musterstrasse 999"), and a street spelled differently from the official
    entry, where the municipality alone still resolves.

    Returns None when the query is a single token — re-running the same search
    would waste an upstream call and the retry note would be a lie.
    """
    tokens = [t for t in search_text.replace(",", " ").split() if t]
    if len(tokens) < 2:
        return None
    candidate = " ".join(tokens[:-1]).strip()
    return candidate or None


# ---------------------------------------------------------------------------
# Async Handler Functions
# ---------------------------------------------------------------------------


@log_tool_call("swisstopo_geocode")
async def geocode(params: GeocodeInput) -> ToolResponse:
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
        if results:
            return ToolResponse.ok(
                format_geocode_results(results), results, match_type="exact"
            )

        # Nothing matched: relax the query and try again before reporting a
        # bare negative (ARCH-003). This is what makes `match_type: "fuzzy"` a
        # real value rather than a member of the Literal no code produces.
        relaxed = _relax_query(params.search_text)
        if relaxed is not None:
            data = await geo_admin_request(
                "/rest/services/ech/SearchServer",
                {**query_params, "searchText": relaxed},
            )
            results = data.get("results", [])
            if results:
                return ToolResponse.ok(
                    format_geocode_results(results),
                    results,
                    match_type="fuzzy",
                    note=(
                        f"Keine exakten Treffer für '{params.search_text}'. "
                        f"Gezeigt werden Treffer für die gelockerte Suche "
                        f"'{relaxed}' — bitte vor der Weiterverwendung prüfen."
                    ),
                )

        return ToolResponse.ok(
            format_geocode_results(results),
            results,
            match_type="none",
            note=(
                f"Keine Treffer für '{params.search_text}', auch nicht gelockert. "
                "Ort ohne Strasse suchen, Schreibweise prüfen (Umlaute, "
                "Abkürzungen wie 'str.' ausschreiben), oder mit "
                "swisstopo_search_address bzw. swisstopo_lookup_postal_code die "
                "amtliche Schreibweise ermitteln."
            ),
        )
    except Exception as e:
        return ToolResponse.error(handle_api_error(e, "Geocoding"))


@log_tool_call("swisstopo_reverse_geocode")
async def reverse_geocode(params: ReverseGeocodeInput) -> ToolResponse:
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
        return ToolResponse.ok(
            format_geocode_results(results),
            results,
            match_type="exact" if results else "none",
            note=(
                None
                if results
                else "Keine Adresse im 500-m-Umkreis — der Punkt liegt womöglich "
                "ausserhalb besiedelten Gebiets. swisstopo_municipality_at nennt "
                "die zuständige Gemeinde auch dort, wo es keine Adresse gibt."
            ),
        )
    except Exception as e:
        return ToolResponse.error(handle_api_error(e, "Reverse Geocoding"))
