# src/swisstopo_mcp/stac.py
"""STAC Catalog tools for data.geo.admin.ch (search + collection details)."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from swisstopo_mcp.api_client import handle_api_error, stac_request

# ---------------------------------------------------------------------------
# Input Models
# ---------------------------------------------------------------------------


class SearchGeodataInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    query: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Suchbegriff (z.B. 'swissALTI3D', 'Orthofoto', 'Gebäude 3D')",
    )
    limit: int = Field(default=10, ge=1, le=50, description="Maximale Trefferanzahl")


class GetCollectionInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    collection_id: str = Field(
        ...,
        min_length=2,
        description="Collection-ID (z.B. 'ch.swisstopo.swissalti3d')",
    )


# ---------------------------------------------------------------------------
# Formatting Helpers
# ---------------------------------------------------------------------------


def format_collection_card(collection: dict[str, Any]) -> str:
    """Format a collection as a compact Markdown card."""
    cid = collection.get("id", "unbekannt")
    title = collection.get("title") or cid
    description = collection.get("description") or "Keine Beschreibung verfügbar."
    # Truncate long descriptions to keep cards compact
    if len(description) > 300:
        description = description[:297] + "..."
    return f"### {title}\n**ID:** {cid}\n**Beschreibung:** {description}\n---"


def format_collection_detail(collection: dict[str, Any]) -> str:
    """Format a collection as detailed Markdown with extent and asset links."""
    cid = collection.get("id", "unbekannt")
    title = collection.get("title") or cid
    description = collection.get("description") or "Keine Beschreibung verfügbar."
    license_info = collection.get("license", "nicht angegeben")

    lines: list[str] = [
        f"# {title}",
        "",
        f"**ID:** {cid}",
        f"**Lizenz:** {license_info}",
        "",
        "## Beschreibung",
        description,
    ]

    # Spatial extent
    extent = collection.get("extent", {})
    spatial = extent.get("spatial", {})
    bbox_list = spatial.get("bbox", [])
    if bbox_list:
        bbox = bbox_list[0]
        if len(bbox) >= 4:
            lines += [
                "",
                "## Räumliche Ausdehnung",
                f"- West: {bbox[0]}, Süd: {bbox[1]}, Ost: {bbox[2]}, Nord: {bbox[3]}",
            ]

    # Temporal extent
    temporal = extent.get("temporal", {})
    intervals = temporal.get("interval", [])
    if intervals:
        interval = intervals[0]
        start = interval[0] if len(interval) > 0 and interval[0] else "unbekannt"
        end = interval[1] if len(interval) > 1 and interval[1] else "aktuell"
        lines += [
            "",
            "## Zeitliche Ausdehnung",
            f"- Von: {start} bis {end}",
        ]

    # Links (assets / downloads)
    links = collection.get("links", [])
    download_links = [
        lnk for lnk in links if lnk.get("rel") in ("enclosure", "item", "items", "download")
    ]
    if not download_links:
        # Fall back to all non-self links
        download_links = [
            lnk for lnk in links if lnk.get("rel") not in ("self", "root", "parent", "collection")
        ]

    if download_links:
        lines += ["", "## Links & Downloads"]
        for lnk in download_links[:10]:
            href = lnk.get("href", "")
            rel = lnk.get("rel", "link")
            link_title = lnk.get("title") or rel
            lines.append(f"- [{link_title}]({href})")

    return "\n".join(lines)


def format_search_results(collections: list[dict[str, Any]]) -> str:
    """Format a list of collections as Markdown cards."""
    if not collections:
        return ""
    return "\n\n".join(format_collection_card(c) for c in collections)


# ---------------------------------------------------------------------------
# Async Handler Functions
# ---------------------------------------------------------------------------


async def search_geodata(params: SearchGeodataInput) -> str:
    """Search the STAC catalog for geodata matching a query string."""
    try:
        data = await stac_request("/collections")
        all_collections: list[dict[str, Any]] = data.get("collections", [])

        query_lower = params.query.lower()
        matched: list[dict[str, Any]] = []
        for col in all_collections:
            cid = (col.get("id") or "").lower()
            title = (col.get("title") or "").lower()
            desc = (col.get("description") or "").lower()
            if query_lower in cid or query_lower in title or query_lower in desc:
                matched.append(col)
            if len(matched) >= params.limit:
                break

        if not matched:
            return f"Keine Geodaten gefunden für '{params.query}'."

        return format_search_results(matched)
    except Exception as e:
        return handle_api_error(e, "STAC-Suche")


async def get_collection(params: GetCollectionInput) -> str:
    """Retrieve detailed information about a specific STAC collection."""
    try:
        collection = await stac_request(f"/collections/{params.collection_id}")
        return format_collection_detail(collection)
    except Exception as e:
        return handle_api_error(e, f"Collection '{params.collection_id}'")
