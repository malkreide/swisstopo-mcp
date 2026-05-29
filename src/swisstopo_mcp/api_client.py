# src/swisstopo_mcp/api_client.py
from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import httpx

# --- Constants ---

GEO_ADMIN_BASE = "https://api3.geo.admin.ch"
STAC_BASE = "https://data.geo.admin.ch/api/stac/v0.9"
WMTS_BASE = "https://wmts.geo.admin.ch/1.0.0"

REQUEST_TIMEOUT = 30.0
USER_AGENT = "SwisstopoMCP/0.1 (MCP Server; +https://github.com/malkreide/swisstopo-mcp)"

# Swiss bounding box (WGS84)
CH_LAT_MIN, CH_LAT_MAX = 45.8, 47.9
CH_LON_MIN, CH_LON_MAX = 5.9, 10.5

SUPPORTED_SRS = {4326, 2056, 21781, 3857}

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


async def geo_admin_request(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """GET request on api3.geo.admin.ch, returns parsed JSON."""
    async with await _get_client() as client:
        url = f"{GEO_ADMIN_BASE}{path}"
        assert_host_allowed(url)
        response = await client.get(url, params=params or {})
        response.raise_for_status()
        return response.json()


async def stac_request(path: str, params: dict[str, Any] | None = None) -> Any:
    """GET request on data.geo.admin.ch STAC API, returns parsed JSON."""
    async with await _get_client() as client:
        url = f"{STAC_BASE}{path}"
        assert_host_allowed(url)
        response = await client.get(url, params=params or {})
        response.raise_for_status()
        return response.json()


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

    return f"{prefix}{type(e).__name__}: {e}"


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
