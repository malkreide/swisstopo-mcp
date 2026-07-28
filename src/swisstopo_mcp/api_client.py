# src/swisstopo_mcp/api_client.py
from __future__ import annotations

import asyncio
import ipaddress
import os
import socket
from functools import lru_cache
from typing import Any
from urllib.parse import urlparse

import httpx

from swisstopo_mcp import __version__
from swisstopo_mcp.logging_config import get_logger

_log = get_logger("swisstopo_mcp.api_client")

# --- Constants ---

GEO_ADMIN_BASE = "https://api3.geo.admin.ch"
REFRAME_BASE = "https://geodesy.geo.admin.ch/reframe"
STAC_BASE = "https://data.geo.admin.ch/api/stac/v0.9"
WMTS_BASE = "https://wmts.geo.admin.ch/1.0.0"
GEODIENSTE_BASE = "https://geodienste.ch"
OVERPASS_BASE = "https://overpass.osm.ch"
OPENPLZ_BASE = "https://openplzapi.org/ch"

REQUEST_TIMEOUT = 30.0
# Derived from the package version, not hand-maintained: this literal used to
# read "SwisstopoMCP/0.1" while the package was at 0.3.0, so every request to
# geo.admin.ch, REFRAME, STAC, Overpass and OpenPLZ identified itself as a
# version that had not been current since the first release.
USER_AGENT = f"SwisstopoMCP/{__version__} (MCP Server; +https://github.com/malkreide/swisstopo-mcp)"

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
#
# TEXT_PATTERN deliberately admits `;` `&` `/` `%` — they occur in real Swiss
# addresses and place names ("Rue de l'Hôpital 3/5", "Bäckerei & Co."). That is
# a broader charset than a whitelist ideal implies, and it is safe *here* for
# reasons that must stay true: no value reaches a shell or a SQL statement, and
# everything goes through httpx's own parameter encoding rather than string
# concatenation. If a tool ever builds a command or a query by interpolation,
# this pattern stops being sufficient (SEC-018).
#
# Length is bounded separately, per field, via `max_length` — a pattern
# constrains the charset, not the size. `tests/test_input_validation.py` fails
# if a string field ships without a bound.
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
        "geodesy.geo.admin.ch",  # REFRAME — official coordinate transformation
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


# Private / link-local ranges an upstream host must never resolve into. A name
# on ALLOWED_HOSTS that suddenly answers with 127.0.0.1 or 169.254.169.254 is
# DNS rebinding, not a legitimate move (SEC-004).
_BLOCKED_NETS = [
    ipaddress.ip_network(n)
    for n in (
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "127.0.0.0/8",
        "169.254.0.0/16",
        "0.0.0.0/8",
        "::1/128",
        "fe80::/10",
        "fc00::/7",
    )
]


@lru_cache(maxsize=64)
def _resolve(hostname: str) -> tuple[str, ...]:
    """Resolve a hostname to its IPs.

    Cached for the process lifetime: this runs on every outbound request, and
    the allow-list is a fixed frozenset of a handful of federal hosts.
    """
    infos = socket.getaddrinfo(hostname, 443, proto=socket.IPPROTO_TCP)
    return tuple(str(info[4][0]) for info in infos)


def assert_resolved_ip_public(hostname: str) -> None:
    """Raise PermissionError if a host resolves into a private/link-local range.

    **On resolution failure this returns rather than raising, deliberately.**
    The audit (SEC-004) called it out as "a documented weakening rather than a
    closed criterion" and asked for a decision instead of an inherited default,
    so: it stays, and the reasoning is that failing closed here would buy
    nothing.

    A name that does not resolve is a name nothing can connect to. The guard's
    job is to reject a host that resolves *somewhere it should not*, and a
    `gaierror` is the absence of an answer, not a suspicious one — there is no
    address for an attacker to have supplied. Raising would convert every
    transient DNS outage into a `PermissionError` reading "blocked by the
    SSRF/DNS-rebinding guard", which is a false accusation and sends whoever
    reads the log looking for an attack instead of a resolver.

    What makes this safe is that it is not the last line of defence. The host
    still had to be on `ALLOWED_HOSTS`, the scheme still had to be https, and
    when pinning is on (the default since 0.4.0) `PinnedTransport` re-runs this
    check against the addresses it is about to connect to. An unresolvable name
    reaches the connection attempt and fails there, with httpx's message.
    """
    try:
        addresses = _resolve(hostname)
    except socket.gaierror:
        return
    for address in addresses:
        ip = ipaddress.ip_address(address)
        if any(ip in net for net in _BLOCKED_NETS):
            raise PermissionError(
                f"Host {hostname!r} löst auf eine interne Adresse auf ({address}). "
                "Blockiert (SSRF/DNS-Rebinding-Schutz)."
            )


def assert_host_allowed(url: str) -> None:
    """Raise PermissionError unless the URL is HTTPS, allow-listed and public."""
    parsed = urlparse(url)
    # Scheme first: an allow-listed host reached over http:// is still a
    # cleartext egress and was previously accepted.
    if parsed.scheme != "https":
        raise PermissionError(
            f"Nicht-HTTPS-Egress blockiert: {parsed.scheme!r}. "
            f"Nur https:// ist erlaubt (Egress-Allow-List)."
        )
    host = parsed.hostname or ""
    if host not in ALLOWED_HOSTS:
        raise PermissionError(
            f"Host nicht auf der Egress-Allow-List: {host!r}. "
            f"Erlaubt: {sorted(ALLOWED_HOSTS)}"
        )
    assert_resolved_ip_public(host)


# --- DNS pinning (SEC-005) ---
#
# `assert_resolved_ip_public` checks the address a host resolves to, but the
# connection then resolves it *again* — a rebinding window between check and
# connect. This transport closes it by connecting to the address that was
# checked, while keeping SNI and the Host header on the original hostname so
# certificate validation is unaffected.
#
# **On by default since 0.4.0** (`SWISSTOPO_PIN_DNS=0` to disable). It was
# off, on the reasoning that a control rewriting every outbound request should
# be verified before being switched on — but that left the window open in the
# configuration almost everyone runs, which is the one the audit judges.
#
# Two limits keep default-on from being a liability, and both are enforced here
# rather than assumed:
#
# 1. **Inert behind a forward proxy.** When HTTPS_PROXY is set the proxy does the
#    resolving, so client-side pinning cannot apply — silently pinning anyway
#    would just break CONNECT.
# 2. **It never turns a resolvable host into an unreachable one.** A name that
#    does not resolve, or resolves to nothing, falls through to the unpinned
#    path; and when a name resolves to several addresses the transport tries
#    them in turn rather than betting the request on the first one.


def _proxy_configured() -> bool:
    return bool(
        os.environ.get("HTTPS_PROXY")
        or os.environ.get("https_proxy")
        or os.environ.get("ALL_PROXY")
        or os.environ.get("all_proxy")
    )


def _body_is_replayable(request: httpx.Request) -> bool:
    """True when the request body is buffered in memory and can be sent again.

    Trying a second address means sending the request a second time, which is
    only correct for a fully-buffered body. A streaming body has already been
    consumed by the first attempt, so a "retry" would put a truncated request on
    the wire — worse than the connection error it is trying to recover from.
    """
    try:
        request.content
    except httpx.RequestNotRead:
        return False
    return True


class PinnedTransport(httpx.AsyncHTTPTransport):
    """Connect to a pre-validated IP, keeping SNI and Host on the hostname."""

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        host = request.url.host
        # Only pin names, never literals, and never when a proxy owns resolution.
        if not host or _proxy_configured() or _is_ip_literal(host):
            return await super().handle_async_request(request)

        try:
            addresses = _resolve(host)
        except socket.gaierror:
            return await super().handle_async_request(request)
        if not addresses:
            return await super().handle_async_request(request)

        # Reuse the addresses the SSRF guard already vetted (SEC-004). It raises
        # if *any* answer is private, so every candidate tried below is covered
        # — not merely the one that happens to be first.
        assert_resolved_ip_public(host)

        request.headers["Host"] = host
        request.extensions = {**dict(request.extensions), "sni_hostname": host}

        # Walk the list rather than committing to addresses[0]. getaddrinfo has
        # no obligation to return a reachable family first: an AAAA-first answer
        # in an IPv4-only network made the request fail outright, and unpinned
        # httpx would have moved on to the next address by itself. Pinning must
        # not be the reason a working host becomes unreachable — that is what
        # made default-on defensible (SEC-005).
        candidates = addresses if _body_is_replayable(request) else addresses[:1]
        original = request.url
        last_error: Exception | None = None
        for address in candidates:
            request.url = original.copy_with(host=address)
            try:
                return await super().handle_async_request(request)
            except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
                # Connect-phase only: nothing reached the peer, so the next
                # address gets a clean attempt. A read error or an HTTP-level
                # failure means the request *was* delivered and must propagate.
                last_error = exc
                _log.debug(
                    "pinned_connect_failed",
                    host=host,
                    address=address,
                    error_type=type(exc).__name__,
                )

        # Report the hostname the caller asked for, not the last IP tried.
        request.url = original
        assert last_error is not None  # the loop runs at least once
        raise last_error


def _is_ip_literal(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return False
    return True


# --- HTTP Client ---
#
# A single AsyncClient is created once per process (see `server_resources()` in
# server.py, which is reference-counted precisely because the FastMCP lifespan
# runs per session on the HTTP transport — SDK-001) and reused across all tool
# calls for connection pooling. When no shared client is registered (e.g. in
# unit tests or when a handler is called outside the server lifespan) we fall
# back to a short-lived ephemeral client. follow_redirects is disabled to avoid
# redirect-based SSRF.

_shared_client: httpx.AsyncClient | None = None


def _pinning_enabled() -> bool:
    """True when DNS pinning is switched on and actually applicable.

    Reads Settings rather than os.environ: config.py is the single source for
    every SWISSTOPO_ variable, and a direct env read would silently ignore a
    typo instead of surfacing it (ARCH-004).
    """
    from swisstopo_mcp.config import settings

    return settings.pin_dns and not _proxy_configured()


def _build_client() -> httpx.AsyncClient:
    """Build a freshly configured AsyncClient."""
    return httpx.AsyncClient(
        timeout=REQUEST_TIMEOUT,
        headers={"User-Agent": USER_AGENT},
        follow_redirects=False,
        transport=PinnedTransport() if _pinning_enabled() else None,
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


async def _notify_retry(ctx: Any, host: str, attempt: int, delay: float) -> None:
    """Tell the client a retry is coming. Never let reporting break the request.

    A context whose session has already gone away raises on `warning()`; that
    must not turn a recoverable upstream blip into a failed tool call.
    """
    try:
        await ctx.warning(
            f"{host} antwortet nicht — Versuch {attempt} von "
            f"{len(RETRY_BACKOFFS)} in {delay:.0f} s."
        )
    except Exception:  # noqa: BLE001 - progress reporting is best-effort
        _log.debug("retry_notify_failed", host=host, attempt=attempt)


async def request_with_retry(
    method: str,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    content: bytes | str | None = None,
    headers: dict[str, str] | None = None,
    timeout: float | None = None,
    check_host: bool = True,
    ctx: Any | None = None,
) -> httpx.Response:
    """Perform an HTTP request with exponential-backoff retry.

    Retries on 429/5xx and network/timeout errors (2s, 4s, 8s). 4xx other than
    429 raise immediately. The host is checked against the egress allow-list
    before the first attempt.

    `ctx` is an optional MCP `Context`. A full retry chain adds 2+4+8 seconds of
    otherwise *silent* waiting, which from the client's side is indistinguishable
    from a hang — and the usual response to a hang is to cancel and retry,
    multiplying load on an upstream that is already struggling. When a context is
    supplied, each retry emits a warning naming the host and the wait, so the
    single longest source of unexplained latency in this server is visible
    (audit SDK-003).
    """
    if check_host:
        assert_host_allowed(url)
    host = urlparse(url).hostname or ""
    last_exc: Exception | None = None
    for attempt in range(len(RETRY_BACKOFFS) + 1):
        if attempt:
            delay = RETRY_BACKOFFS[attempt - 1]
            if ctx is not None:
                await _notify_retry(ctx, host, attempt, delay)
            await _sleep(delay)
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


async def geo_admin_request(
    path: str, params: dict[str, Any] | None = None, ctx: Any | None = None
) -> dict[str, Any]:
    """GET request on api3.geo.admin.ch, returns parsed JSON."""
    url = f"{GEO_ADMIN_BASE}{path}"
    _log.debug("upstream_request", host="api3.geo.admin.ch", path=path)
    response = await request_with_retry("GET", url, params=params or {}, ctx=ctx)
    payload: dict[str, Any] = response.json()
    return payload


async def geo_admin_request_text(
    path: str, params: dict[str, Any] | None = None, ctx: Any | None = None
) -> str:
    """GET request on api3.geo.admin.ch returning the raw body as text.

    The legend endpoints serve HTML rather than JSON, so they cannot go through
    `geo_admin_request`.
    """
    url = f"{GEO_ADMIN_BASE}{path}"
    _log.debug("upstream_request", host="api3.geo.admin.ch", path=path)
    response = await request_with_retry("GET", url, params=params or {}, ctx=ctx)
    return response.text


async def reframe_request(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """GET request on the swisstopo REFRAME service, returns parsed JSON.

    REFRAME is the *official* LV95<->WGS84 transformation. The local polynomial
    helpers (`wgs84_to_lv95` / `lv95_to_wgs84`) stay the internal fast path for
    every height/profile/identify call — their deviation from REFRAME measures
    0.05-0.20 m, well below those tools' own tolerance — so this endpoint is
    reached only by the explicit conversion tool, where precision is the point.
    """
    url = f"{REFRAME_BASE}{path}"
    _log.debug("upstream_request", host="geodesy.geo.admin.ch", path=path)
    response = await request_with_retry("GET", url, params=params or {})
    payload: dict[str, Any] = response.json()
    return payload


async def stac_request(
    path: str, params: dict[str, Any] | None = None, ctx: Any | None = None
) -> Any:
    """GET request on data.geo.admin.ch STAC API, returns parsed JSON."""
    url = f"{STAC_BASE}{path}"
    _log.debug("upstream_request", host="data.geo.admin.ch", path=path)
    response = await request_with_retry("GET", url, params=params or {}, ctx=ctx)
    payload: dict[str, Any] = response.json()
    return payload


async def openplz_request(
    path: str, params: dict[str, Any] | None = None, ctx: Any | None = None
) -> httpx.Response:
    """GET request on the OpenPLZ API (openplzapi.org/ch).

    Returns the raw ``httpx.Response`` — unlike ``geo_admin_request`` — because
    OpenPLZ paginates list endpoints and exposes the totals only in the
    ``x-total-count`` / ``x-total-pages`` response headers, which callers need to
    decide whether to fetch further pages.
    """
    url = f"{OPENPLZ_BASE}{path}"
    _log.debug("upstream_request", host="openplzapi.org", path=path)
    return await request_with_retry("GET", url, params=params or {}, ctx=ctx)


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

    # Egress refusals carry internal configuration — the ten-host allow-list, or
    # the internal address a name resolved to. The model needs to know the
    # request was refused, not what the boundary looks like, so the detail stays
    # in the log and a fixed message goes back (OBS-002).
    if isinstance(e, PermissionError):
        _log.warning("egress_blocked", context=context, detail=str(e))
        return (
            f"{prefix}Ziel nicht erlaubt (Egress-Richtlinie). "
            "Dieser Server spricht nur mit einer festen Liste schweizerischer "
            "Geodaten-Endpunkte."
        )

    # Intentional, user-facing validation errors carry helpful guidance — keep them.
    if isinstance(e, ValueError):
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
