## Finding: SEC-005 — DNS-Rebinding-Prevention: DNS-Pinning gegen TOCTOU

**Severity:** high
**Status:** in-remediation
**Server:** swisstopo-mcp
**Check-Reference:** SEC-005
**PDF-Reference:** Sec 4.4

### Observed Behavior
No DNS pinning of any kind exists. A grep for `getaddrinfo|gethostbyname|dns\.resolve|sni_hostname|SSLContext` over `src/` returns zero hits. Requests are issued with the hostname URL (`src/swisstopo_mcp/api_client.py:171-175`), so httpx performs its own resolution at connect time; there is no resolve-once-then-pin path, no custom transport and no egress proxy — the shared client is built with only `timeout`, `User-Agent` and `follow_redirects` (`src/swisstopo_mcp/api_client.py:88-94`).

`SECURITY.md:25` claims `follow_redirects=False ... (SEC-005)`. That attribution is wrong: redirect suppression (`src/swisstopo_mcp/api_client.py:93`) prevents redirect-based host switching, which is a SEC-004 concern. It gives no protection against a TOCTOU rebind of an already-allow-listed hostname, so a future reviewer reading SECURITY.md will conclude this check is handled when it is not.

Two real compensating controls do exist. The reachable hostname set is a fixed frozenset of federal and cantonal domains (`src/swisstopo_mcp/api_client.py:51-64`), so rebinding requires DNS control over `geo.admin.ch` or a cantonal OEREB domain. And in the Kubernetes deployment a rebind to a private or link-local address is dropped at the network layer (`deploy/kubernetes.yaml:100-111`). TLS certificate verification is left at the httpx default — no `verify=False` anywhere in `src/` — so a rebound connection would additionally fail hostname validation for an attacker without a valid certificate.

### Expected Behavior
- DNS resolution happens once, before the HTTP request
- The resolved IP is used for the TCP connection (pinned URL or custom resolver)
- The original hostname is preserved via the `Host` header and SNI for the TLS handshake
- Certificate validation runs against the original hostname, not the IP
- Tests verify exactly one DNS lookup per request

### Evidence
- No pinning primitives anywhere: grep for `getaddrinfo|gethostbyname|dns\.resolve|sni_hostname|SSLContext` over `src/` returns zero hits
- Requests issued against the hostname URL: `src/swisstopo_mcp/api_client.py:171-175`
- Client construction with no custom transport and no `proxy=`: `src/swisstopo_mcp/api_client.py:88-94`; no Smokescreen sidecar in `Dockerfile` or `deploy/kubernetes.yaml`
- No resolver is mocked in `tests/`; network tests use respx transport mocking (`tests/test_coords.py:116`, `tests/test_lv95_input.py`), which never exercises resolution
- Mislabelled control: `SECURITY.md:25` attributes SEC-005 to `follow_redirects=False` (`src/swisstopo_mcp/api_client.py:93`)
- Compensating controls: fixed host frozenset `src/swisstopo_mcp/api_client.py:51-64`; egress NetworkPolicy `deploy/kubernetes.yaml:100-111`; httpx default certificate verification retained

Gaps:
- DNS resolution is not performed once and pinned; the connect-time lookup is httpx's own
- Original hostname is not carried via explicit `Host` header / SNI, because no pinning exists to require it
- No regression test proving one resolution per request
- The compensating network-layer control is absent for local-stdio and plain `docker run` modes

### Risk Description
The exploit path is narrow but real. An attacker who controls DNS answers for an allow-listed domain — a hostile or compromised resolver on the host, a poisoned upstream cache, or a developer machine on an untrusted network — can answer the allow-list check with a public address and the connect-time lookup with `127.0.0.1`, `169.254.169.254` or an RFC1918 address. `assert_host_allowed` validated a hostname, not the address the socket actually reaches, so the check passes and the connection targets an internal service.

TLS verification limits what an attacker gains from this: without a valid certificate for `geo.admin.ch`, the handshake fails and the request errors rather than returning attacker-controlled content. So the realistic outcome is a connection attempt to an internal address (a port-probe primitive from a trusted process), not silent data injection. In Kubernetes even that is dropped by the egress policy. In local-stdio and plain-Docker runs — the default modes for this server — nothing stops the connection attempt.

The more immediate operational risk is the mislabelled control. `SECURITY.md:25` states SEC-005 is addressed, which means the gap will not be re-examined by anyone who trusts that file.

### Remediation
1. Correct `SECURITY.md:25` first — this is a five-minute fix and it is the item most likely to cause the gap to persist. Move `follow_redirects=False` under SEC-004 and add an honest SEC-005 row stating that DNS pinning is not implemented, that the reachable host set is a fixed frozenset, and that the network-layer compensation applies to the Kubernetes deployment only.
2. Implement pinning in `src/swisstopo_mcp/api_client.py` as a custom httpx transport that resolves once and reuses the address, keeping SNI and the `Host` header on the original hostname:

```python
class PinnedTransport(httpx.AsyncHTTPTransport):
    async def handle_async_request(self, request):
        host = request.url.host
        ip = await _resolve_once(host)          # single getaddrinfo, blocklist-checked (SEC-004)
        request.extensions["sni_hostname"] = host
        request.headers["Host"] = host
        request.url = request.url.copy_with(host=ip)
        return await super().handle_async_request(request)
```

Wire it in at the client construction site (`src/swisstopo_mcp/api_client.py:88-94`) via `transport=PinnedTransport()`. Certificate validation stays at the httpx default and now validates against `sni_hostname`, i.e. the original hostname.

3. Share the resolver with the SEC-004 blocklist so the single lookup serves both purposes — resolve, range-check, then connect to that exact address. Doing SEC-004 step 2 and this item as one change avoids resolving twice.
4. Add `tests/test_dns_pinning.py`: monkeypatch the resolver with a counter, issue one mocked request through the real transport, and assert the counter is exactly 1. Add a second case where the resolver returns a private address and assert `PermissionError`.
5. Extend `docs/network-egress.md` with a note that DNS pinning is a code-layer control that applies in all deployment modes, unlike the NetworkPolicy.

### Effort Estimate
M (1-3d)

---

### Remediation Status (2026-07-27, batch 2)

**Partially closed.** `SECURITY.md` no longer miscredits `follow_redirects=False`
to this finding — that control belongs to SEC-004 and is listed there. An honest
SEC-005 row now states that DNS pinning is *not* implemented, names the residual
rebinding window, and notes that the network-layer compensation applies to the
Kubernetes deployment only.

**Still open:** the pinned transport itself. A custom `httpx` transport that
resolves once and reuses the address while preserving SNI and the `Host` header
touches every outbound request; it deserves its own change and its own
verification against real TLS, not a corner of a documentation batch.

---

### Remediation Status (2026-07-27, batch 5)

**Implemented, opt-in, not yet verified end-to-end.**

`PinnedTransport` in `api_client.py` connects to the address the SEC-004 guard
already vetted, keeping SNI and the `Host` header on the hostname so
certificate validation is unaffected. 20 tests cover the mechanics: URL host
rewritten to the IP, `Host` and `sni_hostname` preserved, path and query
intact, private addresses refused, IP literals left alone.

Two deliberate limits:
- **Off by default** (`SWISSTOPO_PIN_DNS`). It rewrites the target of every
  outbound request; a default-on control that breaks egress would be worse
  than the narrow window it closes.
- **Automatically inert behind a forward proxy**, since the proxy resolves the
  name itself and pinning would only break CONNECT.

**Why this stays in-remediation:** the development sandbox forces all HTTPS
through a forward proxy (`HTTPS_PROXY`), which refuses CONNECT to a bare IP.
A direct-connection probe was attempted and failed for that reason, so the TLS
handshake against a real endpoint with a pinned IP is **untested**. The
mechanics are verified; the handshake is not. Before enabling this in a
deployment, run one request against `api3.geo.admin.ch` with
`SWISSTOPO_PIN_DNS=true` from a host with direct egress and confirm a 200.
Claiming closure on unit tests alone would misrepresent what was checked.
