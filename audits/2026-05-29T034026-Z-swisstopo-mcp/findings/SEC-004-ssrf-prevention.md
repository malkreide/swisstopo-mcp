## Finding: SEC-004 — SSRF-Prevention: HTTPS-Enforcement + IP-Blocklisting

**Severity:** critical
**Status:** open
**Server:** swisstopo-mcp
**Check-Reference:** SEC-004
**PDF-Reference:** Sec 4.4
**Check-Status:** partial

### Observed Behavior
follow_redirects=True is set on the shared httpx config (api_client.py:31); no resolved-IP blocklist or explicit https enforcement. No tool takes a user URL, but redirects from upstream are followed.

### Expected Behavior
HTTPS enforced before each request; resolved IP checked against private/link-local/loopback blocklist (incl. 169.254.169.254); redirects either disabled or re-validated.

### Evidence
- No tool accepts a user-supplied URL; all request hosts are fixed constants (api_client.py:10-12, wmts.py:48) or a hardcoded canton registry (oereb.py:15-18)
- All upstream bases are https://

Gaps:
- api_client.py:31 sets follow_redirects=True — an upstream redirect could reach internal/metadata endpoints (redirect-based SSRF)
- No resolved-IP blocklist for private/link-local ranges (169.254.169.254 not blocked)
- No explicit https scheme enforcement before request

### Risk Description
A compromised/misbehaving upstream could 3xx-redirect the client to an internal address or cloud-metadata endpoint, enabling SSRF.

### Remediation
Set follow_redirects=False (or validate each redirect target host against the allow-list). Even with fixed hosts, add an assert on resolved IP not in private ranges. Keep https-only.

### Effort Estimate
S (<1d)
