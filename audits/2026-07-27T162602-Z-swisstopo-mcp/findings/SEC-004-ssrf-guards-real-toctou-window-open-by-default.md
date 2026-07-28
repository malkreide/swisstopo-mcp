## Finding: SEC-004 — SSRF-Prevention: HTTPS-Enforcement + IP-Blocklisting

**Severity:** critical
**Status:** partial
**Server:** swisstopo-mcp
**Check-Reference:** SEC-004
**PDF-Reference:** Sec 4.4
**Run:** 2026-07-27T162602-Z (re-audit)

### Observed Behavior
Both claimed additions are real and fire on every outbound path. HTTPS enforcement
runs first (`api_client.py:126`, covered by `tests/test_egress_allowlist.py:58-71` for
`http://`, `file://`, `ftp://`, `gopher://`). The resolved-IP guard
(`api_client.py:74-87`) blocks every range the check names including
`169.254.169.254`, `::1/128`, `fe80::/10` and `fc00::/7`, and hangs off
`assert_host_allowed` (`api_client.py:137`) so the two direct-client sites in
`oereb.py` inherit it. `check_host=False` is never passed anywhere in `src/`. The
strongest real case is covered: `geodata.py:426` takes `ogc_base` from the *remote*
geodienste.ch catalogue and still cannot escape the frozenset.

TOCTOU is not closed by default. `assert_resolved_ip_public` resolves
(`api_client.py:109`) and httpx resolves again at connect time; the pinning transport
that closes the window is off unless `SWISSTOPO_PIN_DNS` is set. The `lru_cache` on
`_resolve` does not help — httpx never consults it. The guard also fails open on
`socket.gaierror` (`api_client.py:110-111`).

### Expected Behavior
- HTTPS enforced, resolved IP checked, DNS resolved once and that IP used
- Egress proxy as defence in depth

### Evidence
- HTTPS scheme enforcement is real and runs first: src/swisstopo_mcp/api_client.py:126 rejects any scheme != 'https' before the host is even looked at; tests/test_egress_allowlist.py:58-71 cover http://, file://, ftp://, gopher://.
- Resolved-IP guard exists and covers every range the check names: src/swisstopo_mcp/api_client.py:74-87 blocks 10/8, 172.16/12, 192.168/16, 127/8, 169.254/16 (incl. 169.254.169.254), 0.0.0.0/8, ::1/128, fe80::/10, fc00::/7; enforced at src/swisstopo_mcp/api_client.py:101-118 and invoked from assert_host_allowed at src/swisstopo_mcp/api_client.py:137.
- Both guards do run on every outbound path. The single retry wrapper calls assert_host_allowed unconditionally (src/swisstopo_mcp/api_client.py:293-294), and grep confirms `check_host=False` is never passed anywhere in src/ — the parameter exists only at its definition (src/swisstopo_mcp/api_client.py:285). The two direct-client sites in oereb.py both call it first: src/swisstopo_mcp/oereb.py:91 before src/swisstopo_mcp/oereb.py:92, and src/swisstopo_mcp/oereb.py:183 before src/swisstopo_mcp/oereb.py:184.
- The strongest real-world case is covered: src/swisstopo_mcp/geodata.py:426 takes `ogc_base` out of the *remote* geodienste.ch catalogue and interpolates it into request URLs at src/swisstopo_mcp/geodata.py:449 and :464 — a remotely-controlled base URL that is nonetheless forced through assert_host_allowed by request_with_retry. Redirect-based bypass is closed by follow_redirects=False at src/swisstopo_mcp/api_client.py:223.
- TOCTOU is NOT closed on the default path. assert_resolved_ip_public resolves the name (src/swisstopo_mcp/api_client.py:109) and then httpx resolves it again at connect time; the pinning transport that would close the window is off unless SWISSTOPO_PIN_DNS is set (src/swisstopo_mcp/api_client.py:214-215, wired at src/swisstopo_mcp/api_client.py:224). The lru_cache on _resolve (src/swisstopo_mcp/api_client.py:90) does not help — httpx never consults it. The check's pass criterion 'DNS-Resolution erfolgt einmal, resolved IP wird für den eigentlichen Request verwendet' is therefore unmet by default.
- The guard fails open on resolution error: src/swisstopo_mcp/api_client.py:110-111 swallows socket.gaierror and returns without raising, so a host that cannot be resolved is treated as vetted. Deliberate and documented, and low-impact given the frozenset host list, but it is a documented weakening rather than a closed criterion.

Gaps:
- DNS pinning is opt-in and off by default, so the shipped default configuration retains the rebinding window between the IP check and the connection (SEC-005 detail).
- The Defense-in-Depth egress proxy exists on paper (deploy/egress-proxy.yaml) but the ACL it consumes is structurally broken — see SEC-021. So the 'Egress-Proxy als Defense-in-Depth' criterion is not actually satisfied by the shipped artefacts.
- assert_resolved_ip_public fails open on socket.gaierror (src/swisstopo_mcp/api_client.py:110-111).
- No runtime SSRF probe was executed against a running HTTP server; verification was code-level plus the unit suite (570 tests pass).

### Risk Description
Between the guard's lookup and httpx's, a resolver that answers differently on the
second query places an arbitrary address behind an allow-listed name. The exposure is
bounded — a fixed frozenset of ten federal and cantonal hosts, no credentials, no
secrets, public data only — so the realistic attacker is a hostile or compromised
resolver rather than a remote input. The defence-in-depth layer that would compensate
is nominally shipped but non-functional: see SEC-021.

### Remediation
1. Consider defaulting `SWISSTOPO_PIN_DNS` to on for the stdio path, which has no
   network-layer compensation at all. It is inert behind a proxy anyway, so the
   cluster path is unaffected.
2. Decide deliberately about the fail-open on `gaierror`. It is documented and
   low-impact, but it is a weakening, not a closed criterion.
3. Fix the egress ACL (SEC-021) so the defence-in-depth criterion is satisfied by an
   artefact that works.

### Effort Estimate
S (<1d) for 1 and 2

### Relation to run `2026-07-27T125314-Z`
Recorded as closed. The two additions are genuine; the no-TOCTOU criterion is explicit in the check and is unmet in the default configuration.

### Auditor Notes
The two claimed additions are real, not cosmetic: the scheme check and the
resolved-IP guard are both in assert_host_allowed and both fire on every
outbound path, including the two direct-client call sites in oereb.py that
the brief flagged. I verified there is no bypass — check_host=False is never
used, and the one place a URL base comes from remote data (geodata.py
ogc_base) still goes through the retry wrapper.
Not a pass, because the check lists no-TOCTOU as an explicit pass criterion
and the default configuration still does two independent lookups. The
mitigations are genuine (fixed frozenset of ten federal/cantonal hosts, no
auth, no secrets, public data only), which is why this is partial rather
than fail.
