"""
swisstopo-mcp — MCP-Server fuer schweizerische Bundesgeodaten.

19 Tools aus 9 Quellen-Familien: REST, Geocoding, Hoehe, STAC, WMTS, OEREB,
die konsolidierte Geodaten-Fassade (Strassenverzeichnis, geodienste.ch,
OEREB-Verfuegbarkeit), OpenStreetMap-POIs via Overpass, plus die administrative
Adressebene via OpenPLZ (PLZ -> Gemeinde/BFS-Nr -> Bezirk -> Kanton).
Alle Endpunkte sind offen (kein API-Schluessel erforderlich, ausser OEREB-Kanton).
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from mcp.server.fastmcp import Context, FastMCP

from swisstopo_mcp.api_client import create_shared_client, set_shared_client
from swisstopo_mcp.config import settings
from swisstopo_mcp.logging_config import configure_logging, get_logger
from swisstopo_mcp.models import ToolResponse

configure_logging(settings.log_level)
_log = get_logger("swisstopo_mcp.server")


@asynccontextmanager
async def lifespan(server: FastMCP):
    """Create one shared httpx.AsyncClient for the server's lifetime so all
    tool calls reuse connections (pooling) instead of opening a client per call."""
    client = create_shared_client()
    set_shared_client(client)
    _log.info("server_started")
    try:
        yield
    finally:
        await client.aclose()
        set_shared_client(None)
        _log.info("server_stopped")


mcp = FastMCP(
    "swisstopo_mcp",
    lifespan=lifespan,
    instructions=(
        "Swiss federal geodata server with 19 tools. "
        "Use swisstopo_search_layers to discover layer IDs, then use "
        "swisstopo_identify_features or swisstopo_find_features to query them. "
        "swisstopo_geocode converts addresses to coordinates. "
        "swisstopo_get_height returns elevation. "
        "swisstopo_search_geodata finds downloadable datasets (orthophotos, 3D models, etc.). "
        "swisstopo_map_url generates shareable map links. "
        "ÖREB tools (swisstopo_get_egrid, swisstopo_get_oereb_extract) require a canton parameter. "
        "For interkantonale/OSM data use the consolidated façade: "
        "list_available_layers → query_geodata (strassenverzeichnis, "
        "geodienste:<topic>:<canton>, oereb-verfuegbarkeit). "
        "query_osm_features returns OpenStreetMap POIs (schools, playgrounds, …) "
        "around a point via Overpass (ODbL, separate rate-limited source). "
        "For the administrative address level (PLZ → Gemeinde → Bezirk → Kanton) "
        "use lookup_postal_code, find_commune and search_address (OpenPLZ, "
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
    annotations={
        "title": "Adresse geocodieren",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
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
    annotations={
        "title": "Koordinaten zu Adresse",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
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
    SearchLayersInput,
    find_features,
    get_feature,
    identify_features,
    search_layers,
)


@mcp.tool(
    name="swisstopo_search_layers",
    annotations={
        "title": "Swisstopo Layer suchen",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
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
    annotations={
        "title": "Features an Koordinate identifizieren",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def swisstopo_identify_features(params: IdentifyInput) -> ToolResponse:
    """Findet Features an einer bestimmten Koordinate (räumliche Punktabfrage über Layer).

    <use_case>«Was liegt an diesem Punkt?» — z.B. Bauzone, Gemeinde oder Gebäude an
    einer Adresse. Layer-IDs vorher via swisstopo_search_layers ermitteln.</use_case>
    <important_notes>Im Gegensatz zu swisstopo_find_features (Attributsuche) erfolgt
    die Abfrage rein geografisch.</important_notes>
    """
    return await identify_features(params)


@mcp.tool(
    name="swisstopo_find_features",
    annotations={
        "title": "Features nach Attribut suchen",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
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
    annotations={
        "title": "Feature-Details abrufen",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
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
    annotations={
        "title": "Geodaten suchen",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
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
    annotations={
        "title": "Geodaten-Details abrufen",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
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
    annotations={
        "title": "Karten-URL generieren",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
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
    annotations={
        "title": "Höhe abfragen",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def swisstopo_get_height(params: HeightInput) -> ToolResponse:
    """Gibt die Höhe über Meer (m ü. M.) an einer WGS84-Koordinate zurück.

    <use_case>Punkthöhe für eine Adresse/Koordinate; für Linien siehe
    swisstopo_elevation_profile.</use_case>
    """
    return await get_height(params)


@mcp.tool(
    name="swisstopo_elevation_profile",
    annotations={
        "title": "Höhenprofil berechnen",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def swisstopo_elevation_profile(params: ElevationProfileInput, ctx: Context) -> ToolResponse:
    """Berechnet ein Höhenprofil entlang einer Linie aus mehreren Koordinatenpaaren.

    <use_case>Höhenverlauf z.B. für Wander-/Schulweg-Analysen.</use_case>
    <important_notes>Benötigt ≥2 Koordinatenpaare im Format 'lat1,lon1;lat2,lon2;…'.</important_notes>
    """
    return await elevation_profile(params, ctx=ctx)


# --- ÖREB Tools ---
from swisstopo_mcp.oereb import (  # noqa: E402
    GetEgridInput,
    GetOerebExtractInput,
    get_egrid,
    get_oereb_extract,
)


@mcp.tool(
    name="swisstopo_get_egrid",
    annotations={
        "title": "Grundstück-ID (EGRID) ermitteln",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def swisstopo_get_egrid(params: GetEgridInput) -> ToolResponse:
    """Ermittelt die EGRID (Grundstück-ID) aus Koordinaten für einen bestimmten Kanton.

    <use_case>Vorstufe zu swisstopo_get_oereb_extract: Koordinaten → EGRID.</use_case>
    <important_notes>Erfordert einen unterstützten Kanton (z.B. ZH, BE).</important_notes>
    """
    return await get_egrid(params)


@mcp.tool(
    name="swisstopo_get_oereb_extract",
    annotations={
        "title": "ÖREB-Auszug abrufen",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def swisstopo_get_oereb_extract(params: GetOerebExtractInput, ctx: Context) -> ToolResponse:
    """Ruft öffentlich-rechtliche Eigentumsbeschränkungen (ÖREB) für ein Grundstück (EGRID) ab.

    <use_case>Beantwortet «Welche Nutzungsbeschränkungen gelten für diese Parzelle?».
    EGRID via swisstopo_get_egrid ermitteln.</use_case>
    <important_notes>Erfordert einen unterstützten Kanton.</important_notes>
    """
    return await get_oereb_extract(params, ctx=ctx)


# --- Consolidated Geodata Façade (Phase-2 Geodaten-Erweiterung) ---
from swisstopo_mcp.geodata import (  # noqa: E402
    ListLayersInput,
    QueryGeodataInput,
    list_available_layers,
    query_geodata,
)


@mcp.tool(
    name="list_available_layers",
    annotations={
        "title": "Verfügbare Geodaten-Layer auflisten",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def list_available_layers_tool(params: ListLayersInput) -> ToolResponse:
    """Discovery-Tool: listet die Layer-Kennungen, die query_geodata akzeptiert.

    <use_case>Erster Schritt vor query_geodata: herausfinden, welche Datensätze
    (Strassenverzeichnis, ÖREB-Verfügbarkeit, interkantonale geodienste.ch-Topics)
    verfügbar und ohne Vertrag frei nutzbar sind. Für konkrete
    geodienste-Kennungen einen Kanton angeben (z.B. canton='ZH').</use_case>
    """
    return await list_available_layers(params)


@mcp.tool(
    name="query_geodata",
    annotations={
        "title": "Geodaten abfragen (Fassade)",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def query_geodata_tool(params: QueryGeodataInput) -> ToolResponse:
    """Einheitliche Fassade über mehrere Geodaten-Quellen anhand einer Layer-Kennung.

    <use_case>Ein Tool für drei Quellen: 'strassenverzeichnis' (Strassen um einen
    Punkt), 'oereb-verfuegbarkeit' (ÖREB-Status/Zuständigkeit an einem Punkt) und
    'geodienste:&lt;topic&gt;:&lt;KANTON&gt;' (interkantonale Basisgeodaten via OGC API
    Features). Genau eine Ortsangabe (point | bbox | commune) übergeben.</use_case>
    <important_notes>Gültige Layer-Kennungen via list_available_layers.
    geodienste-Layer erfordern bbox oder point (mit radius_m).</important_notes>
    """
    return await query_geodata(params)


# --- OpenStreetMap POIs via Overpass (separate tool, ODbL) ---
from swisstopo_mcp.overpass import QueryOsmFeaturesInput, query_osm_features  # noqa: E402


@mcp.tool(
    name="query_osm_features",
    annotations={
        "title": "OpenStreetMap-POIs abfragen (Overpass)",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
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
    name="lookup_postal_code",
    annotations={
        "title": "PLZ zu Gemeinde/BFS-Nummer auflösen",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
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
    name="find_commune",
    annotations={
        "title": "Gemeinde auflösen (Name ↔ BFS-Nummer, Kanton/Bezirk)",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
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
    name="search_address",
    annotations={
        "title": "Adressen/Orte per Volltext suchen",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def search_address_tool(params: SearchAddressInput) -> ToolResponse:
    """Volltextsuche über Schweizer Strassen und Ortschaften (OpenPLZ FullTextSearch).

    <use_case>Findet Strassen und Orte zu einem freien Suchbegriff und liefert je
    Treffer Gemeinde und BFS-Nummer, wenn vorhanden.</use_case>
    <important_notes>Quelle OpenPLZ (BFS/swisstopo OGD). Ergebnisse sind paginiert
    (max. 50/Abfrage); die Gesamttrefferzahl wird ausgewiesen. Für die exakte
    PLZ→Gemeinde-Auflösung ist lookup_postal_code präziser.</important_notes>
    """
    return await search_address(params)


def build_http_app(allowed_origins: list[str] | None = None):
    """Build the Streamable-HTTP ASGI app with CORS configured (SDK-004).

    `expose_headers=["Mcp-Session-Id"]` is required so browser-based MCP
    clients can read the session id and send it on follow-up requests.
    Origins must be passed explicitly (no wildcard) — by default none are
    allowed, which is the safe choice when credentials are involved.

    A `/healthz` route is added for container/orchestrator liveness probes.
    """
    from starlette.middleware.cors import CORSMiddleware
    from starlette.responses import JSONResponse
    from starlette.routing import Route

    async def _healthz(_request):
        return JSONResponse({"status": "ok"})

    app = mcp.streamable_http_app()
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

    if "--http" in sys.argv:
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
