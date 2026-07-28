## Finding: SEC-005 — DNS-Rebinding-Prevention: DNS-Pinning gegen TOCTOU

**Severity:** high
**Status:** partial
**Server:** swisstopo-mcp
**Check-Reference:** SEC-005
**PDF-Reference:** Sec 4.4
**Run:** 2026-07-27T162602-Z (re-audit)

### Observed Behavior
`PinnedTransport` (`api_client.py:167-190`) is real and wired into `_build_client`
(`api_client.py:224`), the single constructor behind both the shared client and the
ephemeral fallback, so the `oereb.py` direct-client sites inherit it. The ordering is
correct: Host header (`:187`) and `sni_hostname` (`:188`) are set *before* the URL is
rewritten (`:189`), and it re-asserts the SEC-004 IP guard on the pinned address
(`:184`) rather than trusting the resolver twice.

It is off by default, and `SECURITY.md:27` still says "DNS pinning | **Not
implemented** (SEC-005)" — the exact opposite of what the code does.
`docs/network-egress.md` describes it correctly as available and off by default.

### Expected Behavior
- The resolved IP is used for the TCP connection
- Certificate validation unaffected

### Evidence
- PinnedTransport exists and is genuinely wired into the client factory, not orphaned: defined at src/swisstopo_mcp/api_client.py:167-190 and passed as the transport in _build_client at src/swisstopo_mcp/api_client.py:224, which is the single constructor behind both create_shared_client (src/swisstopo_mcp/api_client.py:228-230) and the ephemeral fallback (src/swisstopo_mcp/api_client.py:253-258). The oereb.py direct-client sites use the same _get_client, so they inherit it.
- The claimed SNI/Host preservation is in the code, not just the docstring: src/swisstopo_mcp/api_client.py:187 sets the Host header to the original hostname, src/swisstopo_mcp/api_client.py:188 sets extensions['sni_hostname'], and only then does src/swisstopo_mcp/api_client.py:189 rewrite request.url to the resolved address. Unit tests assert each of the three separately (tests/test_dns_pinning.py:78-101).
- The pin reuses the vetted address rather than trusting the resolver a second time: src/swisstopo_mcp/api_client.py:177 resolves via the shared cached _resolve and src/swisstopo_mcp/api_client.py:184 re-asserts the SEC-004 IP guard before connecting; tests/test_dns_pinning.py:103-107 proves a 127.0.0.1 answer raises PermissionError.
- It is off by default: src/swisstopo_mcp/api_client.py:212-215 requires SWISSTOPO_PIN_DNS in {1,true,yes} AND no proxy env var. tests/test_dns_pinning.py:47-49 asserts the default is False. So the shipped default deployment — including the local stdio path, which has no network-layer compensation — runs without pinning and keeps the rebinding window open.
- The security policy contradicts the code. SECURITY.md:27 still states 'DNS pinning | **Not implemented** (SEC-005) ... a rebinding window exists between the guard's lookup and the connection'. docs/network-egress.md describes it correctly as 'available, off by default'. A reader of SECURITY.md — the document the audit trail points at — would conclude the control does not exist.

Gaps:
- Default-off means the criterion 'Resolved IP wird für die TCP-Connection verwendet' holds only for operators who explicitly opt in and who are not behind a proxy.
- Pinning and the shipped egress proxy are mutually exclusive by design (src/swisstopo_mcp/api_client.py:158-164, deploy/egress-proxy.yaml:51-53), so a Kubernetes deployment following the shipped manifests gets neither pinning nor — given the broken ACL, see SEC-021 — a working per-host proxy.
- SECURITY.md:27 is stale and states the opposite of what the code does.
- End-to-end TLS-with-pinned-IP is only covered by @pytest.mark.live tests (tests/test_dns_pinning.py:138-168), which are deselected in CI (.github/workflows/ci.yml runs `pytest -m "not live"`). The non-live suite proves request rewriting, not that a handshake succeeds.
- Only addresses[0] is used (src/swisstopo_mcp/api_client.py:185); if getaddrinfo returns an IPv6 address first in an IPv4-only environment the request fails rather than falling back.

### Risk Description
The control is inert in the shipped default, so the rebinding window SEC-004 leaves
open stays open. On the cluster path, pinning and the egress proxy are mutually
exclusive by design (`api_client.py:158-164`) — and given the broken ACL (SEC-021), a
deployment following the shipped manifests gets neither. `SECURITY.md` is the document
the audit trail points at; a reader would conclude the control does not exist.

### Remediation
1. Correct `SECURITY.md:27`. This is drift in the safe direction, but it is drift.
2. Reconsider the default (see SEC-004 item 1).
3. Only `addresses[0]` is used (`api_client.py:185`); if `getaddrinfo` returns an IPv6
   address first in an IPv4-only environment the request fails with no fallback. Walk
   the list.
4. The end-to-end TLS proof is `@pytest.mark.live` only, deselected in PR CI. That is
   the right split, but it means the non-live suite proves request rewriting, not that
   a handshake succeeds — worth stating in the test module docstring.

### Effort Estimate
S (<1d)

### Relation to run `2026-07-27T125314-Z`
Recorded as closed on the strength of a live TLS verification. The transport is sound; default-off and the stale SECURITY.md line keep it partial.

### Auditor Notes
The remediation is substantive — the transport is real, correctly ordered
(Host + SNI set before the URL is rewritten), reuses the SEC-004 guard, and
is properly plumbed through the one client factory. That answers the two
things the brief asked me to check.
It is not a pass because the control is inert in the default configuration
and, on the cluster path, is deliberately mutually exclusive with an egress
proxy whose ACL does not work. The doc contradiction at SECURITY.md:27 is
the mirror image of overclaiming, but it is still drift and should be fixed.
