"""Structured tool-response envelope (audit findings SDK-002 + CH-004).

Every tool returns a `ToolResponse`: machine-readable structured fields
(`results`, `count`, `match_type`, `source`, `license`, `provenance`) plus a
human-readable Markdown `summary`. MCPServer emits this as structured content
*and* a JSON text block, so clients get both.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Provenance = Literal["live_api", "cached"]
MatchType = Literal["exact", "fuzzy", "none"]

# --- Attribution (CH-004) ---
SWISSTOPO_SOURCE = "swisstopo / geo.admin.ch"
SWISSTOPO_LICENSE = "Swiss Open Government Data (opendata.swiss)"
# REFRAME is the official swisstopo transformation service, served from a
# separate host (geodesy.geo.admin.ch) — named separately so a caller can tell
# an amtliche transformation apart from the local polynomial approximation.
REFRAME_SOURCE = "swisstopo REFRAME (geodesy.geo.admin.ch)"
REFRAME_LICENSE = SWISSTOPO_LICENSE
ARE_SOURCE = "ch.are.bauzonen (ARE) / geo.admin.ch"
# ARE is a different federal office than swisstopo, so its licence is asserted
# rather than inherited from SWISSTOPO_LICENSE by default (audit CH-004).
ARE_LICENSE = "Swiss Open Government Data (opendata.swiss) — Bundesamt für Raumentwicklung ARE"
SWISSBOUNDARIES_SOURCE = "swissBOUNDARIES3D (swisstopo) / geo.admin.ch"
SWISSBOUNDARIES_LICENSE = SWISSTOPO_LICENSE
# The harmonised zoning layer is a federal synthesis for comparability across
# cantons; it is NOT the legally binding plan. This caveat must travel with every
# zoning result, not only in the prose summary.
ARE_ZONING_CAVEAT = (
    "Der harmonisierte Layer ch.are.bauzonen ist eine Synthese des ARE. "
    "Rechtsverbindlich ist allein die kantonale/kommunale Nutzungsplanung."
)
OEREB_SOURCE = "ÖREB-Kataster (Kanton)"
OEREB_LICENSE = "Kantonale ÖREB-Nutzungsbedingungen"
GEODIENSTE_SOURCE = "geodienste.ch (Kantone)"
GEODIENSTE_LICENSE = "Freie Nutzung — Quellenangabe Pflicht (geodienste.ch OGD)"
OSM_SOURCE = "OpenStreetMap — Overpass API (overpass.osm.ch)"
OSM_LICENSE = "ODbL — © OpenStreetMap contributors"
# OpenPLZ is a *separate* source from swisstopo geodata: it serves the amtliche
# administrative address level (PLZ → Gemeinde/BFS-Nr → Bezirk → Kanton). Its
# data are the official BFS municipal directory plus the swisstopo street
# directory, both Swiss OGD with mandatory source attribution. The API server
# code is AGPL-3.0, but that is irrelevant here — we only consume the public
# HTTP API, we do not redistribute the code.
OPENPLZ_SOURCE = (
    "OpenPLZ API (openplzapi.org) — Daten: BFS-Gemeindeverzeichnis "
    "& swisstopo-Strassenverzeichnis"
)
OPENPLZ_LICENSE = "Freie Nutzung — Quellenangabe Pflicht (Swiss OGD / opendata.swiss)"


# --- Source → licence coupling (audit CH-004) ---
#
# The licence used to be a separate parameter defaulting to SWISSTOPO_LICENSE.
# That is a drift machine, and it drifted twice: 14 call sites passed `source=`
# without `license=`, so ODbL OpenStreetMap data and the cantonal ÖREB terms
# were emitted under a Swiss OGD label. Relabelling ODbL is a licence
# misstatement, not a missing field — the share-alike obligation disappears.
#
# Now the licence is *derived* from the source unless a caller overrides it, so
# forgetting it produces the correct answer instead of a wrong one. The mapping
# is exhaustive over the source constants above; `tests/test_responses.py`
# fails if a new `*_SOURCE` is added without an entry here.
LICENSE_BY_SOURCE: dict[str, str] = {
    SWISSTOPO_SOURCE: SWISSTOPO_LICENSE,
    REFRAME_SOURCE: REFRAME_LICENSE,
    ARE_SOURCE: ARE_LICENSE,
    SWISSBOUNDARIES_SOURCE: SWISSBOUNDARIES_LICENSE,
    OEREB_SOURCE: OEREB_LICENSE,
    GEODIENSTE_SOURCE: GEODIENSTE_LICENSE,
    OSM_SOURCE: OSM_LICENSE,
    OPENPLZ_SOURCE: OPENPLZ_LICENSE,
}


def license_for(source: str) -> str:
    """The licence that belongs to a source.

    Unknown sources fall back to the swisstopo licence, which is correct for the
    composite strings the discovery tools build (`list_available_layers` names
    several sources at once and overrides the licence explicitly anyway). Every
    *declared* source constant is in the mapping, and a test enforces that.
    """
    return LICENSE_BY_SOURCE.get(source, SWISSTOPO_LICENSE)


# --- Empty results always carry a next step (audit ARCH-003) ---
#
# A bare negative is where an LLM either gives up or invents. The `note` field
# existed but was populated at 5 of ~25 sites that can report `match_type:
# "none"`, and nothing enforced it — so the coverage that existed could regress
# silently, and did not grow.
#
# This is the floor, not the goal: the validator guarantees *a* next step, and
# `tests/test_empty_results.py` asserts the tools that legitimately return
# nothing often carry a *specific* one instead. A handler that falls back to
# this text is logged, so the gap is visible rather than merely covered.
FALLBACK_NOTE = (
    "Keine Treffer. Suchbegriff weiter fassen oder Schreibweise prüfen; "
    "swisstopo_list_available_layers zeigt die verfügbaren Datensätze."
)


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
    note: str | None = Field(
        default=None,
        description=(
            "Actionable hint when a search returns nothing — what to try next, "
            "rather than a bare negative (audit ARCH-003)."
        ),
    )
    is_error: bool = Field(default=False, description="True if this represents a handled error.")

    @model_validator(mode="after")
    def _empty_results_carry_a_next_step(self) -> ToolResponse:
        """`match_type == "none"` implies a non-empty `note` (ARCH-003).

        Filling a fallback rather than raising is deliberate: an unhandled
        empty path is a missing hint, and turning that into an exception would
        replace a mildly unhelpful answer with a masked internal error — a
        worse outcome for the caller than the defect being fixed.
        """
        if self.match_type == "none" and not self.note:
            self.note = FALLBACK_NOTE
        return self

    @classmethod
    def ok(
        cls,
        summary: str,
        results: list[dict[str, Any]] | None = None,
        *,
        match_type: MatchType | None = None,
        source: str = SWISSTOPO_SOURCE,
        license: str | None = None,
        provenance: Provenance = "live_api",
        note: str | None = None,
    ) -> ToolResponse:
        # `license=None` means "whatever belongs to this source" (CH-004). Pass
        # it explicitly only to say something the mapping does not know, such as
        # the composite licence of a multi-source discovery result.
        records = results or []
        return cls(
            summary=summary,
            results=records,
            count=len(records),
            match_type=match_type,
            source=source,
            license=license if license is not None else license_for(source),
            provenance=provenance,
            note=note,
        )

    @classmethod
    def error(
        cls,
        summary: str,
        *,
        source: str = SWISSTOPO_SOURCE,
        license: str | None = None,
    ) -> ToolResponse:
        # Same derivation as `ok()`, so an error envelope attributes the same
        # source *and* the same licence it would have on success (CH-004). The
        # error path is where the previous split-parameter design failed.
        return cls(
            summary=summary,
            results=[],
            count=0,
            is_error=True,
            source=source,
            license=license if license is not None else license_for(source),
        )
