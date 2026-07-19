"""Structured tool-response envelope (audit findings SDK-002 + CH-004).

Every tool returns a `ToolResponse`: machine-readable structured fields
(`results`, `count`, `match_type`, `source`, `license`, `provenance`) plus a
human-readable Markdown `summary`. FastMCP emits this as structured content
*and* a JSON text block, so clients get both.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Provenance = Literal["live_api", "cached"]
MatchType = Literal["exact", "fuzzy", "none"]

# --- Attribution (CH-004) ---
SWISSTOPO_SOURCE = "swisstopo / geo.admin.ch"
SWISSTOPO_LICENSE = "Swiss Open Government Data (opendata.swiss)"
OEREB_SOURCE = "ÖREB-Kataster (Kanton)"
OEREB_LICENSE = "Kantonale ÖREB-Nutzungsbedingungen"
GEODIENSTE_SOURCE = "geodienste.ch (Kantone)"
GEODIENSTE_LICENSE = "Freie Nutzung — Quellenangabe Pflicht (geodienste.ch OGD)"
OSM_SOURCE = "OpenStreetMap — Overpass API (overpass.osm.ch)"
OSM_LICENSE = "ODbL — © OpenStreetMap contributors"


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


class ToolResponse(BaseModel):
    """Consistent envelope for all swisstopo-mcp tool results."""

    model_config = ConfigDict(extra="forbid")

    summary: str = Field(description="Human-readable Markdown summary of the result.")
    results: list[dict[str, Any]] = Field(
        default_factory=list, description="Structured result records (machine-readable)."
    )
    count: int = Field(default=0, description="Number of structured results.")
    match_type: MatchType | None = Field(
        default=None, description="exact | fuzzy | none (for search-style tools)."
    )
    source: str = Field(default=SWISSTOPO_SOURCE, description="Data source attribution.")
    license: str = Field(default=SWISSTOPO_LICENSE, description="Data licence.")
    provenance: Provenance = Field(default="live_api", description="How the data was obtained.")
    retrieved_at: str = Field(default_factory=_now_iso, description="ISO-8601 retrieval timestamp.")
    is_error: bool = Field(default=False, description="True if this represents a handled error.")

    @classmethod
    def ok(
        cls,
        summary: str,
        results: list[dict[str, Any]] | None = None,
        *,
        match_type: MatchType | None = None,
        source: str = SWISSTOPO_SOURCE,
        license: str = SWISSTOPO_LICENSE,
        provenance: Provenance = "live_api",
    ) -> ToolResponse:
        records = results or []
        return cls(
            summary=summary,
            results=records,
            count=len(records),
            match_type=match_type,
            source=source,
            license=license,
            provenance=provenance,
        )

    @classmethod
    def error(cls, summary: str, *, source: str = SWISSTOPO_SOURCE) -> ToolResponse:
        return cls(summary=summary, results=[], count=0, is_error=True, source=source)
