"""
swisstopo-mcp — MCP-Server fuer schweizerische Bundesgeodaten.

24 Tools aus 10 Quellen-Familien: REST, Geocoding, Hoehe, REFRAME
(Koordinatenumrechnung), STAC, WMTS, OEREB, die konsolidierte Geodaten-Fassade
(Strassenverzeichnis, geodienste.ch, OEREB-Verfuegbarkeit), OpenStreetMap-POIs
via Overpass, plus die administrative Adressebene via OpenPLZ
(PLZ -> Gemeinde/BFS-Nr -> Bezirk -> Kanton).
Alle Endpunkte sind offen (kein API-Schluessel erforderlich, ausser OEREB-Kanton).
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from mcp import types
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations

from swisstopo_mcp.api_client import create_shared_client, set_shared_client
from swisstopo_mcp.config import settings
from swisstopo_mcp.logging_config import configure_logging, get_logger
from swisstopo_mcp.models import ToolResponse
from swisstopo_mcp.observability import setup_tracing, shutdown_tracing

configure_logging(settings.log_level)
_log = get_logger("swisstopo_mcp.server")


# Process-wide resources (shared httpx client + tracing), reference-counted.
#
# The FastMCP lifespan is *not* a per-process hook: under streamable-http the
# SDK runs it once per MCP **session** (measured — three `initialize` POSTs
# produced three startups, and a `DELETE /mcp` on one of three open sessions
# produced one shutdown). Owning the client directly in that lifespan meant each
# new session clobbered the previous session's client, and the first session to
# disconnect closed the client and tore down tracing for everyone still
# connected — leaving them on a fresh client per tool call (audit SDK-001).
#
# A refcount makes the lifespan safe to enter any number of times: the resources
# are built on the first entry and released on the last exit. `build_http_app`
# additionally holds one reference for the whole ASGI app lifetime, so on the
# HTTP transport the count never reaches zero while the process is serving.
#
# No lock: the refcount is read and written with no `await` in between, so
# within one event loop the sequence is atomic. The single await (`aclose`)
# happens after the globals are already cleared.
_resource_refs = 0
_resource_client = None


@asynccontextmanager
async def server_resources():
    """Acquire the shared httpx client and tracing for the caller's lifetime.

    Idempotent and reference-counted — see the note above. Safe to nest.
    """
    global _resource_refs, _resource_client

    if _resource_refs == 0:
        # Before create_shared_client(): the httpx auto-instrumentation patches
        # the client class, so a client built earlier would never be traced
        # (OBS-006).
        setup_tracing()
        _resource_client = create_shared_client()
        set_shared_client(_resource_client)
        _log.info("server_started")
    _resource_refs += 1

    try:
        yield
    finally:
        _resource_refs -= 1
        if _resource_refs == 0:
            client, _resource_client = _resource_client, None
            set_shared_client(None)
            if client is not None:
                await client.aclose()
            shutdown_tracing()
            _log.info("server_stopped")


@asynccontextmanager
async def lifespan(server: FastMCP):
    """MCP session lifespan.

    On stdio this runs once, because the process serves one session. On
    streamable-http the SDK runs it per session, which is why the resources it
    needs live behind `server_resources()` rather than in here (SDK-001).
    """
    async with server_resources():
        yield


class _SwisstopoMCP(FastMCP):
    """FastMCP that maps the envelope's `is_error` onto the protocol flag.

    Handled execution errors are returned as a `ToolResponse` with
    `is_error: true` rather than raised, which is what keeps them out of the
    JSON-RPC error channel — the separation OBS-001 asks for. But the SDK builds
    a `CallToolResult` with `isError=False` for any tool that returns normally,
    so the payload field was the *only* signal: a spec-conformant client reading
    `CallToolResult.isError` saw success for every handled error and would pass
    a German error string downstream as though it were geodata (audit OBS-001).

    The lowlevel `call_tool` handler returns a `CallToolResult` unchanged when
    the registered handler produces one, so building it here is the supported
    seam. Note this bypasses the SDK's output-schema validation on the error
    path only; the payload is a `ToolResponse` this server constructed, so it
    conforms by construction, and `tests/test_protocol_errors.py` asserts the
    structured content still validates.
    """

    async def call_tool(  # type: ignore[override]
        self, name: str, arguments: dict[str, Any]
    ) -> Any:
        result = await super().call_tool(name, arguments)
        if isinstance(result, tuple) and len(result) == 2:
            content, structured = result
            if isinstance(structured, dict) and structured.get("is_error") is True:
                return types.CallToolResult(
                    content=list(content),
                    structuredContent=structured,
                    isError=True,
                )
        return result


mcp = _SwisstopoMCP(
    "swisstopo_mcp",
    lifespan=lifespan,
    # Without this the SDK keeps its localhost-only default list and rejects
    # every MCP request behind an ingress: 403 on a configured Origin, 421 on
    # the forwarded Host, while /healthz stays 200 so the readiness probe hides
    # it (audit SDK-004 / SCALE-001). DNS-rebinding protection stays ON — the
    # fix is to feed it the deployment's real hosts and origins, never to
    # disable it (SEC-005 depends on it).
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=settings.allowed_hosts_list,
        allowed_origins=settings.transport_origins_list,
    ),
    instructions=(
        "Swiss federal geodata server with 24 tools. "
        "Use swisstopo_search_layers to discover layer IDs, swisstopo_layer_info to see "
        "a layer's queryable fields, then swisstopo_identify_features or "
        "swisstopo_find_features to query them. "
        "PRECEDENCE for point questions — prefer the direct tool over the generic one: "
        "Bauzone → swisstopo_zoning_at (use swisstopo_identify_features on "
        "ch.are.bauzonen only when raw layer attributes are needed; "
        "swisstopo_query_geodata with geodienste:nutzungsplanung:<kanton> only for "
        "cantonal Nutzungsplanung beyond the harmonised ARE layer). "
        "Gemeinde/BFS-Nummer → swisstopo_municipality_at. "
        "ÖREB-Beschränkungen → swisstopo_oereb_at (swisstopo_get_egrid only when the "
        "parcel ID itself is wanted). "
        "swisstopo_geocode converts addresses to coordinates. "
        "swisstopo_get_height returns elevation. "
        "Point-based tools (swisstopo_get_height, swisstopo_identify_features, "
        "swisstopo_get_egrid) take EITHER lat/lon (WGS84) OR easting/northing "
        "(LV95, EPSG:2056) — pass one pair, not both. swisstopo_elevation_profile "
        "takes coordinate_system='lv95' for LV95 support points. "
        "swisstopo_convert_coordinates converts explicitly via the official "
        "REFRAME service when a caller needs the numbers themselves "
        "(note its axis order: easting=lon, northing=lat). "
        "swisstopo_search_geodata finds downloadable datasets (orthophotos, 3D models, etc.). "
        "swisstopo_map_url generates shareable map links. "
        "ÖREB tools (swisstopo_get_egrid, swisstopo_get_oereb_extract) require a canton parameter. "
        "For interkantonale/OSM data use the consolidated façade: "
        "swisstopo_list_available_layers → swisstopo_query_geodata (strassenverzeichnis, "
        "geodienste:<topic>:<canton>, oereb-verfuegbarkeit). "
        "swisstopo_query_osm_features returns OpenStreetMap POIs (schools, playgrounds, …) "
        "around a point via Overpass (ODbL, separate rate-limited source). "
        "For the administrative address level (PLZ → Gemeinde → Bezirk → Kanton) "
        "use swisstopo_lookup_postal_code, swisstopo_find_commune and swisstopo_search_address (OpenPLZ, "
        "separate BFS/swisstopo OGD source). These return the amtliche "
        "BFS-Gemeindenummer (bfs_commune_number) — the join key to BFS statistics "
        "(swiss-statistics-mcp) and zurich-opendata-mcp."
    ),
)

# --- Geocoding Tools ---
from swisstopo_mcp.geocoding import (  # noqa: E402
    GeocodeInput,
    ReverseGeocodeInput,
    geocode,
    reverse_geocode,
)


@mcp.tool(
    name="swisstopo_geocode",
    annotations=ToolAnnotations(
        title="Adresse geocodieren",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    ),
)
async def swisstopo_geocode(params: GeocodeInput) -> ToolResponse:
    """Wandelt eine Adresse, einen Ortsnamen oder eine PLZ in Koordinaten um (Geocoding).

    <use_case>Startpunkt für ortsbezogene Abfragen: Adresse → Koordinaten, die danach
    an swisstopo_get_height, swisstopo_identify_features oder swisstopo_get_egrid
    übergeben werden.</use_case>
    """
    return await geocode(params)


@mcp.tool(
    name="swisstopo_reverse_geocode",
    annotations=ToolAnnotations(
        title="Koordinaten zu Adresse",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    ),
)
async def swisstopo_reverse_geocode(params: ReverseGeocodeInput) -> ToolResponse:
    """Findet die nächstgelegene Adresse zu gegebenen WGS84-Koordinaten (Reverse Geocoding).

    <use_case>Koordinaten aus Karte oder GPS in eine lesbare Adresse auflösen.</use_case>
    """
    return await reverse_geocode(params)


# --- REST API Tools ---
from swisstopo_mcp.rest_api import (  # noqa: E402
    FindFeaturesInput,
    GetFeatureInput,
    IdentifyInput,
    LayerInfoInput,
    MunicipalityAtInput,
    SearchLayersInput,
    ZoningAtInput,
    find_features,
    get_feature,
    identify_features,
    layer_info,
    municipality_at,
    search_layers,
    zoning_at,
)


@mcp.tool(
    name="swisstopo_search_layers",
    annotations=ToolAnnotations(
        title="Swisstopo Layer suchen",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    ),
)
async def swisstopo_search_layers(params: SearchLayersInput) -> ToolResponse:
    """Durchsucht den Swisstopo-Layerkatalog (500+ Layer) nach Geodatensätzen.

    <use_case>Erster Schritt der Feature-Recherche: Layer-IDs finden, die danach an
    swisstopo_identify_features / swisstopo_find_features übergeben werden.</use_case>
    <important_notes>Liefert Layer-IDs, keine Feature-Daten.</important_notes>
    """
    return await search_layers(params)


@mcp.tool(
    name="swisstopo_identify_features",
    annotations=ToolAnnotations(
        title="Features an Koordinate identifizieren",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    ),
)
async def swisstopo_identify_features(params: IdentifyInput) -> ToolResponse:
    """Findet Features an einer bestimmten Koordinate (räumliche Punktabfrage über Layer).

    <use_case>«Was liegt an diesem Punkt?» — generische Punktabfrage über beliebige
    Layer. Layer-IDs vorher via swisstopo_search_layers ermitteln.</use_case>
    <important_notes>Für Bauzone bzw. Gemeinde gibt es direkte Tools
    (swisstopo_zoning_at, swisstopo_municipality_at) — dieses Tool nur nutzen, wenn
    zusätzliche Rohattribute gebraucht werden oder ein anderer Layer gefragt ist.</important_notes>
    <important_notes>Im Gegensatz zu swisstopo_find_features (Attributsuche) erfolgt
    die Abfrage rein geografisch.</important_notes>
    """
    return await identify_features(params)


@mcp.tool(
    name="swisstopo_find_features",
    annotations=ToolAnnotations(
        title="Features nach Attribut suchen",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    ),
)
async def swisstopo_find_features(params: FindFeaturesInput) -> ToolResponse:
    """Sucht Features anhand eines Attributwerts in einem Layer (Attributsuche, z.B. Gebäude nach EGID).

    <use_case>«Finde den Datensatz mit Attribut X» — nicht-geografische Suche nach
    einem bekannten Wert.</use_case>
    <important_notes>Im Gegensatz zu swisstopo_identify_features (Punktabfrage) wird
    hier nach einem Attribut gesucht.</important_notes>
    """
    return await find_features(params)


@mcp.tool(
    name="swisstopo_get_feature",
    annotations=ToolAnnotations(
        title="Feature-Details abrufen",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    ),
)
async def swisstopo_get_feature(params: GetFeatureInput) -> ToolResponse:
    """Ruft die vollständigen Attribute und die Geometrie eines Features per Layer- und Feature-ID ab.

    <use_case>Detailabruf, nachdem swisstopo_identify_features / swisstopo_find_features
    eine Feature-ID geliefert haben.</use_case>
    """
    return await get_feature(params)


# --- STAC Tools ---
from swisstopo_mcp.stac import (  # noqa: E402
    GetCollectionInput,
    SearchGeodataInput,
    get_collection,
    search_geodata,
)


@mcp.tool(
    name="swisstopo_search_geodata",
    annotations=ToolAnnotations(
        title="Geodaten suchen",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    ),
)
async def swisstopo_search_geodata(params: SearchGeodataInput) -> ToolResponse:
    """Durchsucht den STAC-Katalog nach herunterladbaren Geodaten.

    <use_case>Findet Orthophotos, Höhenmodelle (swissALTI3D), 3D-Gebäude und
    historische Karten zum Download.</use_case>
    <important_notes>Liefert Collections/Metadaten; Download-Links via
    swisstopo_get_collection.</important_notes>
    """
    return await search_geodata(params)


@mcp.tool(
    name="swisstopo_get_collection",
    annotations=ToolAnnotations(
        title="Geodaten-Details abrufen",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    ),
)
async def swisstopo_get_collection(params: GetCollectionInput) -> ToolResponse:
    """Ruft Detailinformationen und Download-Links einer STAC-Collection ab.

    <use_case>Zweiter Schritt nach swisstopo_search_geodata, um Assets/Download-URLs
    einer Collection zu erhalten.</use_case>
    """
    return await get_collection(params)


# --- WMTS Tools ---
from swisstopo_mcp.wmts import MapUrlInput, build_map_url  # noqa: E402


@mcp.tool(
    name="swisstopo_map_url",
    annotations=ToolAnnotations(
        title="Karten-URL generieren",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    ),
)
async def swisstopo_map_url(params: MapUrlInput) -> ToolResponse:
    """Generiert eine teilbare map.geo.admin.ch-URL zum Öffnen im Browser.

    <use_case>Einen Kartenausschnitt mit optionalen Layern als Link bereitstellen
    (kein Datenabruf).</use_case>
    """
    return await build_map_url(params)


# --- Height Tools ---
from swisstopo_mcp.height import (  # noqa: E402
    ElevationProfileInput,
    HeightInput,
    elevation_profile,
    get_height,
)


@mcp.tool(
    name="swisstopo_get_height",
    annotations=ToolAnnotations(
        title="Höhe abfragen",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    ),
)
async def swisstopo_get_height(params: HeightInput) -> ToolResponse:
    """Gibt die Höhe über Meer (m ü. M.) an einer Koordinate zurück.

    <use_case>Punkthöhe für eine Adresse/Koordinate; für Linien siehe
    swisstopo_elevation_profile.</use_case>
    <important_notes>Koordinaten entweder als lat/lon (WGS84) ODER als
    easting/northing (LV95) angeben — nicht beides.</important_notes>
    """
    return await get_height(params)


@mcp.tool(
    name="swisstopo_elevation_profile",
    annotations=ToolAnnotations(
        title="Höhenprofil berechnen",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    ),
)
async def swisstopo_elevation_profile(params: ElevationProfileInput, ctx: Context) -> ToolResponse:
    """Berechnet ein Höhenprofil entlang einer Linie aus mehreren Koordinatenpaaren.

    <use_case>Höhenverlauf z.B. für Wander-/Schulweg-Analysen.</use_case>
    <important_notes>Benötigt ≥2 Koordinatenpaare. Standard ist WGS84
    ('lat1,lon1;lat2,lon2;…'); für LV95 coordinate_system='lv95' setzen und die
    Paare als 'easting,northing' übergeben.</important_notes>
    """
    return await elevation_profile(params, ctx=ctx)


@mcp.tool(
    name="swisstopo_zoning_at",
    annotations=ToolAnnotations(
        title="Bauzone an Koordinate",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    ),
)
async def swisstopo_zoning_at(params: ZoningAtInput) -> ToolResponse:
    """Gibt die harmonisierte Bauzone an einer Koordinate zurück (ch.are.bauzonen, ARE).

    <use_case>«Welche Bauzone gilt hier?» in einem Aufruf — ohne vorher die
    Layer-ID via swisstopo_search_layers suchen zu müssen.</use_case>
    <important_notes>Der harmonisierte ARE-Layer ist eine Synthese für die
    schweizweite Vergleichbarkeit und NICHT rechtsverbindlich — verbindlich ist
    allein die kantonale/kommunale Nutzungsplanung. Der Hinweis steht in jedem
    Resultat. Koordinaten als lat/lon (WGS84) oder easting/northing (LV95).</important_notes>
    """
    return await zoning_at(params)


@mcp.tool(
    name="swisstopo_municipality_at",
    annotations=ToolAnnotations(
        title="Gemeinde an Koordinate",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    ),
)
async def swisstopo_municipality_at(params: MunicipalityAtInput) -> ToolResponse:
    """Gibt Gemeinde, BFS-Nummer und Kanton an einer Koordinate zurück (swissBOUNDARIES3D).

    <use_case>Koordinate → amtliche BFS-Gemeindenummer, der Join-Key zu
    swiss-statistics-mcp und zurich-opendata-mcp.</use_case>
    <important_notes>Der Layer führt eine Fläche pro historischem Jahrgang; es
    wird der aktuelle Stand zurückgegeben. Auf einer Gemeindegrenze oder
    ausserhalb der Schweiz bleibt das Resultat leer.</important_notes>
    """
    return await municipality_at(params)


@mcp.tool(
    name="swisstopo_layer_info",
    annotations=ToolAnnotations(
        title="Layer-Felder und Legende",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    ),
)
async def swisstopo_layer_info(params: LayerInfoInput) -> ToolResponse:
    """Listet die abfragbaren Felder und die Legende eines Layers auf.

    <use_case>Bindeglied zwischen swisstopo_search_layers und
    swisstopo_find_features: zeigt, welche Feldnamen als search_field zulässig
    sind, statt sie raten zu müssen.</use_case>
    <important_notes>Fehlt die Legende, werden die Felder trotzdem
    zurückgegeben (legend = null).</important_notes>
    """
    return await layer_info(params)


# --- Coordinate Tools ---
from swisstopo_mcp.coords import (  # noqa: E402
    ConvertCoordinatesInput,
    convert_coordinates,
)


@mcp.tool(
    name="swisstopo_convert_coordinates",
    annotations=ToolAnnotations(
        title="Koordinaten umrechnen (REFRAME)",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    ),
)
async def swisstopo_convert_coordinates(params: ConvertCoordinatesInput) -> ToolResponse:
    """Rechnet Koordinaten amtlich zwischen WGS84 und LV95 um (swisstopo REFRAME).

    <use_case>Wenn Koordinaten in LV95 (EPSG:2056) vorliegen und für die übrigen
    Tools nach WGS84 gebracht werden müssen — oder umgekehrt für den
    Katasterbezug, wo Zentimeter zählen.</use_case>
    <important_notes>Achsenreihenfolge beachten: REFRAME benennt beide Eingaben
    easting/northing. Bei wgs84_to_lv95 ist easting der LÄNGENgrad und northing
    der BREITENgrad — umgekehrt zur lat/lon-Reihenfolge der übrigen Tools.
    Vertauschte Achsen werden abgewiesen, nicht stillschweigend umgerechnet.</important_notes>
    """
    return await convert_coordinates(params)


# --- ÖREB Tools ---
from swisstopo_mcp.oereb import (  # noqa: E402
    GetEgridInput,
    GetOerebExtractInput,
    OerebAtInput,
    get_egrid,
    get_oereb_extract,
    oereb_at,
)


@mcp.tool(
    name="swisstopo_get_egrid",
    annotations=ToolAnnotations(
        title="Grundstück-ID (EGRID) ermitteln",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    ),
)
async def swisstopo_get_egrid(params: GetEgridInput) -> ToolResponse:
    """Ermittelt die EGRID (Grundstück-ID) aus Koordinaten für einen bestimmten Kanton.

    <use_case>Grundstück-ID (EGRID) zu einer Koordinate, wenn die ID selbst
    gebraucht wird. Für die Beschränkungen direkt swisstopo_oereb_at nutzen — das
    löst den EGRID intern auf.</use_case>
    <important_notes>Erfordert einen unterstützten Kanton (z.B. ZH, BE).</important_notes>
    """
    return await get_egrid(params)


@mcp.tool(
    name="swisstopo_get_oereb_extract",
    annotations=ToolAnnotations(
        title="ÖREB-Auszug abrufen",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    ),
)
async def swisstopo_get_oereb_extract(params: GetOerebExtractInput, ctx: Context) -> ToolResponse:
    """Ruft öffentlich-rechtliche Eigentumsbeschränkungen (ÖREB) für ein Grundstück (EGRID) ab.

    <use_case>ÖREB-Auszug zu einem bereits bekannten EGRID. Wer von einer
    Koordinate ausgeht, nimmt swisstopo_oereb_at — das erledigt beide Schritte
    in einem Aufruf.</use_case>
    <important_notes>Erfordert einen unterstützten Kanton.</important_notes>
    """
    return await get_oereb_extract(params, ctx=ctx)


@mcp.tool(
    name="swisstopo_oereb_at",
    annotations=ToolAnnotations(
        title="ÖREB-Auszug an Koordinate",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    ),
)
async def swisstopo_oereb_at(params: OerebAtInput, ctx: Context) -> ToolResponse:
    """Gibt die ÖREB-Eigentumsbeschränkungen an einer Koordinate zurück (ein Aufruf).

    <use_case>«Welche Beschränkungen gelten auf diesem Grundstück?» — löst den
    EGRID intern auf. Das ist der normale Weg; swisstopo_get_egrid braucht es
    nur, wer die Parzellen-ID selbst benötigt.</use_case>
    <important_notes>Nur für Kantone mit angebundenem ÖREB-Dienst (siehe
    SWISSTOPO_OEREB_CANTONS). Koordinaten als lat/lon (WGS84) oder
    easting/northing (LV95).</important_notes>
    """
    return await oereb_at(params, ctx=ctx)


# --- Consolidated Geodata Façade (Phase-2 Geodaten-Erweiterung) ---
from swisstopo_mcp.geodata import (  # noqa: E402
    ListLayersInput,
    QueryGeodataInput,
    list_available_layers,
    query_geodata,
)


@mcp.tool(
    name="swisstopo_list_available_layers",
    annotations=ToolAnnotations(
        title="Verfügbare Geodaten-Layer auflisten",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    ),
)
async def list_available_layers_tool(params: ListLayersInput) -> ToolResponse:
    """Discovery-Tool: listet die Layer-Kennungen, die swisstopo_query_geodata akzeptiert.

    <use_case>Erster Schritt vor swisstopo_query_geodata: herausfinden, welche Datensätze
    (Strassenverzeichnis, ÖREB-Verfügbarkeit, interkantonale geodienste.ch-Topics)
    verfügbar und ohne Vertrag frei nutzbar sind. Für konkrete
    geodienste-Kennungen einen Kanton angeben (z.B. canton='ZH').</use_case>
    """
    return await list_available_layers(params)


@mcp.tool(
    name="swisstopo_query_geodata",
    annotations=ToolAnnotations(
        title="Geodaten abfragen (Fassade)",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    ),
)
async def query_geodata_tool(params: QueryGeodataInput) -> ToolResponse:
    """Einheitliche Fassade über mehrere Geodaten-Quellen anhand einer Layer-Kennung.

    <use_case>Ein Tool für drei Quellen: 'strassenverzeichnis' (Strassen um einen
    Punkt), 'oereb-verfuegbarkeit' (ÖREB-Status/Zuständigkeit an einem Punkt) und
    'geodienste:&lt;topic&gt;:&lt;KANTON&gt;' (interkantonale Basisgeodaten via OGC API
    Features). Genau eine Ortsangabe (point | bbox | commune) übergeben.</use_case>
    <important_notes>Gültige Layer-Kennungen via swisstopo_list_available_layers.
    geodienste-Layer erfordern bbox oder point (mit radius_m).</important_notes>
    """
    return await query_geodata(params)


# --- OpenStreetMap POIs via Overpass (separate tool, ODbL) ---
from swisstopo_mcp.overpass import QueryOsmFeaturesInput, query_osm_features  # noqa: E402


@mcp.tool(
    name="swisstopo_query_osm_features",
    annotations=ToolAnnotations(
        title="OpenStreetMap-POIs abfragen (Overpass)",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    ),
)
async def query_osm_features_tool(params: QueryOsmFeaturesInput) -> ToolResponse:
    """Findet OpenStreetMap-POIs (Schulen, Spielplätze, Apotheken …) im Umkreis.

    <use_case>Beantwortet «Welche Schulhäuser/Spielplätze liegen im Umkreis von R
    Metern um diesen Punkt/diese Adresse?». Ergänzt die amtlichen swisstopo-Daten
    um Points-of-Interest aus OpenStreetMap.</use_case>
    <important_notes>Quelle OpenStreetMap (ODbL, © OpenStreetMap contributors),
    nicht swisstopo. Overpass hat Rate-Limits/Timeouts — kleiner Radius bevorzugt;
    bei Überlastung kommt eine sprechende Fehlermeldung statt Daten.</important_notes>
    """
    return await query_osm_features(params)


# --- OpenPLZ: administrative address level (PLZ → Gemeinde/BFS → Bezirk → Kanton) ---
from swisstopo_mcp.openplz import (  # noqa: E402
    FindCommuneInput,
    LookupPostalCodeInput,
    SearchAddressInput,
    find_commune,
    lookup_postal_code,
    search_address,
)


@mcp.tool(
    name="swisstopo_lookup_postal_code",
    annotations=ToolAnnotations(
        title="PLZ zu Gemeinde/BFS-Nummer auflösen",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    ),
)
async def lookup_postal_code_tool(params: LookupPostalCodeInput) -> ToolResponse:
    """Löst eine Schweizer PLZ in Ort, Gemeinde, Bezirk und Kanton auf (OpenPLZ, amtlich).

    <use_case>Beantwortet «Zu welcher Gemeinde/welchem Kanton gehört PLZ 8001?» und
    liefert die BFS-Gemeindenummer (`bfs_commune_number`).</use_case>
    <important_notes>`bfs_commune_number` ist der amtliche Join-Schlüssel zu
    BFS-Statistikdaten (swiss-statistics-mcp) und zu zurich-opendata-mcp. Quelle
    OpenPLZ (BFS/swisstopo OGD), nicht die swisstopo-Geodaten. Eine unbekannte PLZ
    liefert eine leere Trefferliste mit erklärendem Hinweis.</important_notes>
    """
    return await lookup_postal_code(params)


@mcp.tool(
    name="swisstopo_find_commune",
    annotations=ToolAnnotations(
        title="Gemeinde auflösen (Name ↔ BFS-Nummer, Kanton/Bezirk)",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    ),
)
async def find_commune_tool(params: FindCommuneInput) -> ToolResponse:
    """Löst Gemeinden auf: Name→BFS-Nummer, BFS-Nummer→Name, oder alle Gemeinden eines Kantons/Bezirks.

    <use_case>Vier Modi (genau einen Parameter angeben): `name` (Name →
    BFS-Nummer), `bfs_number` (BFS-Nummer → Gemeinde), `canton` (alle Gemeinden
    eines Kantons) oder `district` (alle Gemeinden eines Bezirks). Beantwortet
    z.B. «Welche Gemeinden liegen im Bezirk Uster und wie lauten ihre
    BFS-Nummern?».</use_case>
    <important_notes>`bfs_commune_number` ist der amtliche Join-Schlüssel zu
    BFS-Statistikdaten (swiss-statistics-mcp). `canton` akzeptiert Kürzel ('ZH')
    oder BFS-Nummer ('1') — die Kürzel→Schlüssel-Auflösung erfolgt serverseitig,
    weil der Pfad sonst still eine leere Liste liefert. Gemeindelisten sind
    vollständig (interne Pagination), nicht auf 10 Einträge gekürzt.</important_notes>
    """
    return await find_commune(params)


@mcp.tool(
    name="swisstopo_search_address",
    annotations=ToolAnnotations(
        title="Adressen/Orte per Volltext suchen",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    ),
)
async def search_address_tool(params: SearchAddressInput) -> ToolResponse:
    """Volltextsuche über Schweizer Strassen und Ortschaften (OpenPLZ FullTextSearch).

    <use_case>Findet Strassen und Orte zu einem freien Suchbegriff und liefert je
    Treffer Gemeinde und BFS-Nummer, wenn vorhanden.</use_case>
    <important_notes>Quelle OpenPLZ (BFS/swisstopo OGD). Ergebnisse sind paginiert
    (max. 50/Abfrage); die Gesamttrefferzahl wird ausgewiesen. Für die exakte
    PLZ→Gemeinde-Auflösung ist swisstopo_lookup_postal_code präziser.</important_notes>
    """
    return await search_address(params)


def _install_session_manager() -> None:
    """Give the Streamable-HTTP session manager an explicit idle timeout.

    The SDK's default is `session_idle_timeout=None`: a session lives until the
    process restarts. Every client that disconnects without sending
    `DELETE /mcp` — a crash, a closed laptop, a killed container — therefore
    leaks one for the lifetime of the pod. Nothing about that is a
    confidentiality problem here (all 24 tools are stateless reads over public
    data), but unbounded growth is still unbounded (audit SEC-009).

    FastMCP exposes no setting for it and builds the manager lazily —
    `streamable_http_app()` only constructs one `if self._session_manager is
    None` — so pre-populating it is how the timeout gets in. Measured against a
    running server: with the timeout set, an idle session is reaped and returns
    404, while activity pushes the deadline back.

    `SWISSTOPO_SESSION_IDLE_TIMEOUT=0` restores the SDK's unbounded behaviour.
    """
    from mcp.server.streamable_http_manager import StreamableHTTPSessionManager

    if mcp._session_manager is not None:  # pragma: no cover - built once
        return

    timeout = settings.session_idle_timeout
    mcp._session_manager = StreamableHTTPSessionManager(
        app=mcp._mcp_server,
        json_response=mcp.settings.json_response,
        stateless=mcp.settings.stateless_http,
        security_settings=mcp.settings.transport_security,
        session_idle_timeout=timeout if timeout > 0 else None,
    )


def build_http_app(allowed_origins: list[str] | None = None):
    """Build the Streamable-HTTP ASGI app with CORS configured (SDK-004).

    `expose_headers=["Mcp-Session-Id"]` is required so browser-based MCP
    clients can read the session id and send it on follow-up requests.
    Origins must be passed explicitly (no wildcard) — by default none are
    allowed, which is the safe choice when credentials are involved.

    A `/healthz` route is added for container/orchestrator liveness probes.

    The app's lifespan is wrapped so the process holds one reference to the
    shared client and tracing for as long as it is serving. Without it those
    resources would be owned by whichever MCP session happened to open first,
    and released when it disconnected (SDK-001).
    """
    from starlette.middleware.cors import CORSMiddleware
    from starlette.responses import JSONResponse
    from starlette.routing import Route

    async def _healthz(_request):
        return JSONResponse({"status": "ok"})

    _install_session_manager()
    app = mcp.streamable_http_app()

    sdk_lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def _process_lifespan(scoped_app):
        async with server_resources():
            async with sdk_lifespan(scoped_app):
                yield

    app.router.lifespan_context = _process_lifespan
    app.router.routes.append(Route("/healthz", _healthz, methods=["GET"]))
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins or [],
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "Mcp-Session-Id"],
        expose_headers=["Mcp-Session-Id"],
    )
    return app


if __name__ == "__main__":
    import sys

    # The CLI flag still wins so existing invocations keep working; the
    # setting is the deployment path (ARCH-004).
    use_http = "--http" in sys.argv or settings.transport == "streamable-http"
    if use_http:
        import uvicorn

        # An explicit --port overrides the configured default.
        port_idx = sys.argv.index("--port") + 1 if "--port" in sys.argv else None
        port = int(sys.argv[port_idx]) if port_idx else settings.http_port
        uvicorn.run(
            build_http_app(settings.origins_list),
            host=settings.http_host,
            port=port,
        )
    else:
        mcp.run()
