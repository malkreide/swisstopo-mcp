## Finding: SEC-021 — Egress-Allow-List: Code-Layer und Network-Layer

**Severity:** high
**Status:** open
**Server:** swisstopo-mcp
**Check-Reference:** SEC-021
**PDF-Reference:** Anhang B5 + B12
**Check-Status:** partial

### Observed Behavior
Outbound hosts are constrained only implicitly via hardcoded base constants and the canton registry; no explicit enforcement, follow_redirects=True can bypass, no network policy.

### Expected Behavior
A frozenset code-layer allow-list checked before each request, plus network-layer egress control and docs.

### Evidence
- Outbound hosts are effectively constrained by hardcoded base constants and a fixed canton registry dict (api_client.py:10-12, oereb.py:15-18)

Gaps:
- No explicit assert_host_allowed()/frozenset egress allow-list enforced before requests
- follow_redirects=True can bypass the implicit allow-list to an arbitrary host
- No network-layer egress policy and no docs/network-egress.md

### Risk Description
Without enforcement, a future code change or a redirect could reach an unintended host.

### Remediation
Introduce ALLOWED_HOSTS = frozenset({...}) and assert_host_allowed(url) called in _get_client callers; set follow_redirects=False; document in docs/network-egress.md.

### Effort Estimate
M (1-3d)
