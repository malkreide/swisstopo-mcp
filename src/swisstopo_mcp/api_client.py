# src/swisstopo_mcp/api_client.py
from __future__ import annotations

import asyncio
from typing import Any
from urllib.parse import urlparse

import httpx

from swisstopo_mcp.logging_config import get_logger

_log = get_logger("swisstopo_mcp.api_client")

# --- Constants ---

GEO_ADMIN_BASE = "https://api3.geo.admin.ch"
STAC_BASE = "https://data.geo.admin.ch/api/stac/v0.9"
WMTS_BASE = "https://wmts.geo.admin.ch/1.0.0"
GEODIENSTE_BASE = "https://geodienste.ch"
OVERPASS_BASE = "https://overpass.osm.ch"
OPENPLZ_BASE = "https://openplzapi.org/ch"

REQUEST_TIMEOUT = 30.0
USER_AGENT = "SwisstopoMCP/0.1 (MCP Server; +https://github.com/malkreide/swisstopo-mcp)"

# Swiss bounding box (WGS84)
CH_LAT_MIN, CH_LAT_MAX = 45.8, 47.9
CH_LON_MIN, CH_LON_MAX = 5.9, 10.5

SUPPORTED_SRS = {4326, 2056, 21781, 3857}

# --- Input-Validation Patterns (SEC-018) ---
#
# Whitelist patterns for free-text tool arguments. They go into upstream HTTP
# query params, so the goal is to reject control characters and obviously
# malicious payloads while still accepting real Swiss addresses, layer IDs and
# search terms (incl. umlauts/accents).
TEXT_PATTERN = r"^[\w\sÀ-ÿ.,;:'’\-/()&+%°]+$"  # addresses, place names, search terms
ID_PATTERN = r"^[\w.,\s\-]+$"  # layer / feature / collection identifiers
COORDS_PATTERN = r"^[\d.,;\s\-]+$"  # 'lat1,lon1;lat2,lon2;...'
LANG_PATTERN = r"^[a-z]{2}$"  # de | fr | it | en
CANTON_PATTERN = r"^[A-Za-z]{2}$"  # ZH, BE, ...

# --- Egress Allow-List (SEC-021) ---
#
# Every outbound request host must appear here. It is a frozenset (not loaded
# from env) so it cannot be silently widened at runtime. Adding a host (e.g. a
# new cantonal OEREB endpoint) is a deliberate code change — keep this in sync
# with OEREB_ENDPOINTS in oereb.py and with docs/network-egress.md.
ALLOWED_HOSTS: frozenset[str] = frozenset(
    {
        "api3.geo.admin.ch",  # REST / SearchServer / MapServer + Geocoding + Height
        "data.geo.admin.ch",  # STAC catalog
        "wmts.geo.admin.ch",  # WMTS tiles
        "map.geo.admin.ch",  # shareable map viewer URLs
        "oereb.geo.zh.ch",  # OEREB cadastre — canton ZH
        "www.oereb2.apps.be.ch",  # OEREB cadastre — canton BE
        "geodienste.ch",  # interkantonale Basisgeodaten (Katalog + WMS/WFS/OGC API)
        "overpass.osm.ch",  # OpenStreetMap Overpass API (Schweizer Instanz)
        "openplzapi.org",  # OpenPLZ API — PLZ/Gemeinde/BFS-Nr (BFS + swisstopo OGD)
    }
)


def assert_host_allowed(url: str) -> None:
    """Raise PermissionError if the URL's host is not on the egress allow-list."""
    host = urlparse(url).hostname or ""
    if host not in ALLOWED_HOSTS:
        raise PermissionError(
            f"Host nicht auf der Egress-Allow-List: {host!r}. "
            f"Erlaubt: {sorted(ALLOWED_HOSTS)}"
        )


# --- HTTP Client ---
#
# A single AsyncClient is created once at server startup (see the FastMCP
# lifespan in server.py) and reused across all tool calls for connection
# pooling. When no shared client is registered (e.g. in unit tests or when a
# handler is called outside the server lifespan) we fall back to a short-lived
# ephemeral client. follow_redirects is disabled to avoid redirect-based SSRF.

_shared_client: httpx.AsyncClient | None = None


def _build_client() -> httpx.AsyncClient:
    """Build a freshly configured AsyncClient."""
    return httpx.AsyncClient(
        timeout=REQUEST_TIMEOUT,
        headers={"User-Agent": USER_AGENT},
        follow_redirects=False,
    )


def create_shared_client() -> httpx.AsyncClient:
    """Create the long-lived client used by the server lifespan."""
    return _build_client()


def set_shared_client(client: httpx.AsyncClient | None) -> None:
    """Register (or clear) the process-wide shared client."""
    global _shared_client
    _shared_client = client


class _NonClosingClient:
    """Adapts the shared client to the `async with await _get_client()`
    calling convention without closing it on context exit."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def __aenter__(self) -> httpx.AsyncClient:
        return self._client

    async def __aexit__(self, *exc: object) -> bool:
        return False


async def _get_client() -> httpx.AsyncClient | _NonClosingClient:
    """Return the shared client (not closed on exit) if one is registered,
    otherwise a short-lived ephemeral client (closed on exit)."""
    if _shared_client is not None:
        return _NonClosingClient(_shared_client)
    return _build_client()


# --- Retry with exponential backoff (resilience default) ---
#
# Every upstream call goes through request_with_retry: transient failures (5xx,
# 429, timeouts, connection errors) are retried with 2s/4s/8s backoff; genuine
# client errors (4xx except 429) fail fast without retry. This protects against
# the first-blip-kills-the-server failure mode — weekly dumps and community
# instances (Overpass) routinely return transient 503s during regeneration.
RETRY_BACKOFFS: tuple[float, ...] = (2.0, 4.0, 8.0)
RETRYABLE_STATUS: frozenset[int] = frozenset({429, 500, 502, 503, 504})


async def _sleep(seconds: float) -> None:
    """Indirection so tests can patch out the real backoff delay."""
    await asyncio.sleep(seconds)


async def request_with_retry(
    method: str,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    content: bytes | str | None = None,
    headers: dict[str, str] | None = None,
    timeout: float | None = None,
    check_host: bool = True,
) -> httpx.Response:
    """Perform an HTTP request with exponential-backoff retry.

    Retries on 429/5xx and network/timeout errors (2s, 4s, 8s). 4xx other than
    429 raise immediately. The host is checked against the egress allow-list
    before the first attempt.
    """
    if check_host:
        assert_host_allowed(url)
    host = urlparse(url).hostname or ""
    last_exc: Exception | None = None
    for attempt in range(len(RETRY_BACKOFFS) + 1):
        if attempt:
            await _sleep(RETRY_BACKOFFS[attempt - 1])
            _log.debug("upstream_retry", host=host, attempt=attempt)
        try:
            async with await _get_client() as client:
                response = await client.request(
                    method, url, params=params, content=content,
                    headers=headers, timeout=timeout,
                )
        except httpx.RequestError as exc:  # timeout / connect / read errors
            last_exc = exc
            continue
        if response.status_code in RETRYABLE_STATUS:
            last_exc = httpx.HTTPStatusError(
                f"HTTP {response.status_code}", request=response.request, response=response
            )
            continue
        response.raise_for_status()  # non-retryable 4xx -> raise immediately
        return response
    assert last_exc is not None
    raise last_exc


async def geo_admin_request(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """GET request on api3.geo.admin.ch, returns parsed JSON."""
    url = f"{GEO_ADMIN_BASE}{path}"
    _log.debug("upstream_request", host="api3.geo.admin.ch", path=path)
    response = await request_with_retry("GET", url, params=params or {})
    return response.json()


async def stac_request(path: str, params: dict[str, Any] | None = None) -> Any:
    """GET request on data.geo.admin.ch STAC API, returns parsed JSON."""
    url = f"{STAC_BASE}{path}"
    _log.debug("upstream_request", host="data.geo.admin.ch", path=path)
    response = await request_with_retry("GET", url, params=params or {})
    return response.json()


async def openplz_request(
    path: str, params: dict[str, Any] | None = None
) -> httpx.Response:
    """GET request on the OpenPLZ API (openplzapi.org/ch).

    Returns the raw ``httpx.Response`` — unlike ``geo_admin_request`` — because
    OpenPLZ paginates list endpoints and exposes the totals only in the
    ``x-total-count`` / ``x-total-pages`` response headers, which callers need to
    decide whether to fetch further pages.
    """
    url = f"{OPENPLZ_BASE}{path}"
    _log.debug("upstream_request", host="openplzapi.org", path=path)
    return await request_with_retry("GET", url, params=params or {})


# --- Error Handling ---

def handle_api_error(e: Exception, context: str = "") -> str:
    """Translate exceptions into German user-friendly error messages."""
    prefix = f"Fehler bei {context}: " if context else "Fehler: "

    if isinstance(e, httpx.HTTPStatusError):
        status = e.response.status_code
        if status == 404:
            return f"{prefix}Ressource nicht gefunden (404)."
        if status == 403:
            return f"{prefix}Zugriff verweigert (403)."
        if status == 429:
            return f"{prefix}Zu viele Anfragen (429). Bitte warte kurz."
        if status == 500:
            return f"{prefix}Serverfehler bei Swisstopo (500). Bitte später erneut versuchen."
        return f"{prefix}HTTP-Fehler {status}."

    if isinstance(e, httpx.TimeoutException):
        return f"{prefix}Zeitüberschreitung. Der Server hat nicht rechtzeitig geantwortet."

    if isinstance(e, httpx.ConnectError):
        return f"{prefix}Verbindungsfehler. Prüfe die Netzwerkverbindung."

    # Intentional, user-facing validation errors carry helpful guidance — keep them.
    if isinstance(e, (ValueError, PermissionError)):
        _log.warning("handled_error", context=context, error_type=type(e).__name__, detail=str(e))
        return f"{prefix}{e}"

    # Unexpected errors: do NOT leak the raw exception text/internals to the LLM
    # (OBS-002). The original error is logged to stderr for diagnosis instead.
    _log.error("unexpected_error", context=context, error_type=type(e).__name__, detail=str(e))
    return f"{prefix}Unerwarteter interner Fehler. Bitte später erneut versuchen."


# --- Coordinate Helpers ---

def wgs84_to_lv95(lat: float, lon: float) -> tuple[float, float]:
    """Convert WGS84 (lat, lon) to LV95 (E, N).

    Uses the Swisstopo approximate polynomial formulas (~1m accuracy).
    Reference: Swisstopo 'Formeln und Konstanten', section 4.1.
    """
    lat_aux = (lat * 3600 - 169028.66) / 10000
    lon_aux = (lon * 3600 - 26782.5) / 10000

    e = (
        2600072.37
        + 211455.93 * lon_aux
        - 10938.51 * lon_aux * lat_aux
        - 0.36 * lon_aux * lat_aux**2
        - 44.54 * lon_aux**3
    )

    n = (
        1200147.07
        + 308807.95 * lat_aux
        + 3745.25 * lon_aux**2
        + 76.63 * lat_aux**2
        - 194.56 * lon_aux**2 * lat_aux
        + 119.79 * lat_aux**3
    )

    return e, n


def lv95_to_wgs84(e: float, n: float) -> tuple[float, float]:
    """Convert LV95 (E, N) to WGS84 (lat, lon).

    Uses the Swisstopo approximate polynomial formulas (~1m accuracy).
    """
    y_aux = (e - 2600000) / 1000000
    x_aux = (n - 1200000) / 1000000

    lat_aux = (
        16.9023892
        + 3.238272 * x_aux
        - 0.270978 * y_aux**2
        - 0.002528 * x_aux**2
        - 0.0447 * y_aux**2 * x_aux
        - 0.0140 * x_aux**3
    )

    lon_aux = (
        2.6779094
        + 4.728982 * y_aux
        + 0.791484 * y_aux * x_aux
        + 0.1306 * y_aux * x_aux**2
        - 0.0436 * y_aux**3
    )

    lat = lat_aux * 100 / 36
    lon = lon_aux * 100 / 36

    return lat, lon


def validate_sr(sr: int) -> int:
    """Validate spatial reference code. Returns sr if valid, raises ValueError otherwise."""
    if sr not in SUPPORTED_SRS:
        raise ValueError(
            f"Nicht unterstütztes Koordinatensystem: {sr}. "
            f"Unterstützt: {sorted(SUPPORTED_SRS)}"
        )
    return sr


def format_coordinates(x: float, y: float, sr: int) -> str:
    """Format coordinates with spatial reference label."""
    sr_names = {4326: "WGS84", 2056: "LV95", 21781: "LV03", 3857: "Web Mercator"}
    name = sr_names.get(sr, str(sr))
    if sr == 4326:
        return f"{x:.6f}, {y:.6f} ({name})"
    return f"{x:.1f}, {y:.1f} ({name})"


def parse_coordinate_string(coords_str: str) -> list[tuple[float, float]]:
    """Parse 'lat1,lon1;lat2,lon2;...' into list of (lat, lon) tuples."""
    pairs = []
    for pair in coords_str.strip().split(";"):
        parts = pair.strip().split(",")
        if len(parts) != 2:
            raise ValueError(f"Ungültiges Koordinatenpaar: '{pair}'. Erwartet: 'lat,lon'.")
        lat, lon = float(parts[0].strip()), float(parts[1].strip())
        pairs.append((lat, lon))
    if len(pairs) < 2:
        raise ValueError("Mindestens 2 Koordinatenpaare erforderlich.")
    return pairs
