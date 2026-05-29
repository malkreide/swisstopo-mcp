## Finding: SEC-009 — Session-ID Cryptographic Binding (user_id:session_id)

**Severity:** critical
**Status:** open
**Server:** swisstopo-mcp
**Check-Reference:** SEC-009
**PDF-Reference:** Sec 4.6
**Check-Status:** partial

### Evidence (already in place)
- No custom session handling; HTTP session IDs delegated to FastMCP
- auth_model=none and data is public read-only → no per-user session to bind; session hijacking has no privilege impact

### Remaining Gaps
- No user_id:session_id binding (not applicable without auth; would be required if auth is added)

### Remediation
Document that HTTP sessions are FastMCP-managed and carry no auth (public data). If auth is added later, bind session id to the validated user_id.

### Effort Estimate
S (<1d)
