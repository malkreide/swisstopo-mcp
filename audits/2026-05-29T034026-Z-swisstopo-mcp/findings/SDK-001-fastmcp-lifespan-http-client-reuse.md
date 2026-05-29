## Finding: SDK-001 — FastMCP Lifespan via @asynccontextmanager + AsyncExitStack

**Severity:** high
**Status:** open
**Server:** swisstopo-mcp
**Check-Reference:** SDK-001
**PDF-Reference:** Sec 3.1
**Check-Status:** fail

### Observed Behavior
FastMCP is created without a lifespan; api_client._get_client() builds a brand-new httpx.AsyncClient on every tool call (`async with await _get_client()`).

### Expected Behavior
A @asynccontextmanager lifespan should create one shared httpx.AsyncClient on server startup and close it on shutdown; tools reuse it for connection pooling.

### Evidence
- FastMCP is constructed without lifespan (server.py:12-24)

Gaps:
- api_client.py:26-32 _get_client() creates a NEW httpx.AsyncClient per request (used via 'async with await _get_client()' in every handler) — exactly the documented anti-pattern: no connection pooling/reuse
- No @asynccontextmanager lifespan, no shared client on server.state

### Risk Description
A new client per call means no connection pooling (slower, more TCP/TLS handshakes) and risks resource/socket leakage under load or on errors.

### Remediation
Add a lifespan to FastMCP that opens a single httpx.AsyncClient (timeout=30, follow_redirects=False) and stores it on server.state; refactor geo_admin_request/stac_request/oereb handlers to use the shared client. Close it in the finally block.

### Effort Estimate
M (1-3d)
