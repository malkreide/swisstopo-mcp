# src/swisstopo_mcp/wmts.py
"""WMTS map URL builder for map.geo.admin.ch."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from swisstopo_mcp.api_client import wgs84_to_lv95


# ---------------------------------------------------------------------------
# Notable layers reference
# ---------------------------------------------------------------------------

NOTABLE_LAYERS: dict[str, str] = {
    "ch.swisstopo.pixelkarte-farbe": "Landeskarte (Farbe)",
    "ch.swisstopo.swissimage": "Luftbilder (SWISSIMAGE)",
    "ch.are.bauzonen": "Bauzonen",
    "ch.bfs.gebaeude_wohnungs_register": "Gebäude- und Wohnungsregister",
}


# ---------------------------------------------------------------------------
# Input Model
# ---------------------------------------------------------------------------


class MapUrlInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    lat: float = Field(..., ge=45.8, le=47.9, description="Breitengrad (WGS84)")
    lon: float = Field(..., ge=5.9, le=10.5, description="Längengrad (WGS84)")
    zoom: int = Field(default=8, ge=1, le=13, description="Zoomstufe 1-13")
    layers: str | None = Field(
        default=None,
        description="Layer-IDs kommagetrennt (z.B. 'ch.are.bauzonen')",
    )
    lang: str = Field(default="de", description="Sprache (de, fr, it, en)")


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------


async def build_map_url(params: MapUrlInput) -> str:
    """Build a map.geo.admin.ch URL for the given coordinates and optional layers."""
    e, n = wgs84_to_lv95(params.lat, params.lon)

    url = f"https://map.geo.admin.ch/?lang={params.lang}&E={e:.0f}&N={n:.0f}&zoom={params.zoom}"
    if params.layers:
        url += f"&layers={params.layers}"

    lines: list[str] = [
        "## Karten-URL",
        "",
        f"[Karte öffnen]({url})",
        "",
        f"`{url}`",
        "",
        f"**Koordinaten:** {params.lat:.6f}°N, {params.lon:.6f}°E "
        f"(LV95: E {e:.0f} / N {n:.0f})",
        f"**Zoomstufe:** {params.zoom}",
    ]

    if params.layers:
        lines += ["", "**Aktive Layer:**"]
        for layer_id in params.layers.split(","):
            layer_id = layer_id.strip()
            label = NOTABLE_LAYERS.get(layer_id, layer_id)
            lines.append(f"- `{layer_id}` — {label}")

    lines += [
        "",
        "## Verfügbare Layer (Beispiele)",
        "",
    ]
    for lid, label in NOTABLE_LAYERS.items():
        lines.append(f"- `{lid}` — {label}")

    return "\n".join(lines)
