## Finding: SEC-009 — Session-ID Cryptographic Binding (user_id:session_id)

**Severity:** critical
**Status:** open
**Server:** swisstopo-mcp
**Check-Reference:** SEC-009
**PDF-Reference:** Sec 4.6
**Check-Status:** partial

### Observed Behavior
No custom session handling; HTTP session IDs are delegated entirely to FastMCP. auth_model=none so there is no per-user binding.

### Expected Behavior
For authenticated HTTP servers, session IDs must be crypto-random and bound to a validated user_id.

### Evidence
- No custom/insecure session handling in src/ — HTTP session IDs are fully delegated to FastMCP's streamable-http manager
- auth_model=none and data is public read-only, so there is no per-user session to bind

Gaps:
- Session security relies entirely on FastMCP defaults; not independently verified in-repo
- No user_id:session_id binding (not applicable without auth, but undocumented)

### Risk Description
Low — public, read-only data; session hijacking yields only access already available to anyone.

### Remediation
Document that HTTP mode relies on FastMCP-managed sessions and carries no auth (public data). If auth is ever added, implement user_id:session_id binding.

### Effort Estimate
S (<1d)
