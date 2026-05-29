## Finding: SEC-005 — DNS-Rebinding-Prevention: DNS-Pinning gegen TOCTOU

**Severity:** high
**Status:** open
**Server:** swisstopo-mcp
**Check-Reference:** SEC-005
**PDF-Reference:** Sec 4.4
**Check-Status:** partial

### Observed Behavior
No DNS pinning; httpx resolves per request. Combined with follow_redirects=True this leaves a TOCTOU/rebinding path, though hosts are fixed trusted federal domains.

### Expected Behavior
Resolve once, pin the IP for the TCP connection, keep the original hostname for TLS SNI/cert validation.

### Evidence
- Request hosts are fixed, trusted federal domains; no user-controlled hostname, so DNS-rebinding surface is minimal

Gaps:
- No DNS pinning (resolve-once + pinned IP); httpx default resolution
- follow_redirects=True (api_client.py:31) reintroduces a rebinding/redirect risk path

### Risk Description
Low in practice (fixed trusted hosts), but redirect-following weakens the guarantee.

### Remediation
Primary mitigation is disabling redirect-following (see SEC-004). DNS pinning is optional defense-in-depth given the fixed host set.

### Effort Estimate
S (<1d)
