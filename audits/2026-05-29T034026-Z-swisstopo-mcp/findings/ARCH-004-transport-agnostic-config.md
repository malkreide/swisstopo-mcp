## Finding: ARCH-004 — Inversion of Control: Transport-agnostische Server-Logik

**Severity:** high
**Status:** open
**Server:** swisstopo-mcp
**Check-Reference:** ARCH-004
**PDF-Reference:** Sec 2.1
**Check-Status:** partial

### Observed Behavior
Handlers are transport-agnostic, but transport is chosen via ad-hoc sys.argv parsing rather than a settings object.

### Expected Behavior
Configuration via a pydantic-settings Settings object; transport selectable by env var.

### Evidence
- Tool handlers take only typed Pydantic params, no request/transport object (server.py:45-274)
- Server supports both stdio (default) and streamable-http (server.py:277-285)
- Tool logic is identical across transports (registration is transport-independent)

Gaps:
- Transport is selected by ad-hoc sys.argv parsing (server.py:280-283), not a pydantic-settings Settings object
- No ctx: Context used for client info

### Risk Description
Ad-hoc argv parsing is harder to test and to extend for cloud config.

### Remediation
Introduce a pydantic-settings Settings (transport, host, port, log_level) and drive mcp.run from it.

### Effort Estimate
S (<1d)
