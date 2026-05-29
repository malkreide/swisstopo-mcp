## Finding: SDK-004 — CORS Mcp-Session-Id Exposure bei HTTP/SSE

**Severity:** high
**Status:** open
**Server:** swisstopo-mcp
**Check-Reference:** SDK-004
**PDF-Reference:** Sec 3.1
**Check-Status:** partial

### Observed Behavior
No CORS middleware configured, yet README advertises SSE for browser access.

### Expected Behavior
CORS with expose_headers including Mcp-Session-Id and explicit allow_origins.

### Evidence
- Streamable-HTTP transport is supported (server.py:283)

Gaps:
- No CORS middleware / expose_headers configured anywhere in src/
- README advertises 'Cloud Deployment (SSE for browser access)' but without Access-Control-Expose-Headers: Mcp-Session-Id, browser clients would break

### Risk Description
Browser clients cannot read Mcp-Session-Id and break on follow-up requests.

### Remediation
Wrap the streamable-http app in CORSMiddleware with expose_headers=['Mcp-Session-Id'], allow_headers including it, and an env-driven allow_origins list (no wildcard with credentials).

### Effort Estimate
S (<1d)
