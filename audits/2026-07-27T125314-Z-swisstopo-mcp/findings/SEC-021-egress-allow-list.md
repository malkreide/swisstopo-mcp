## Finding: SEC-021 — Egress-Allow-List: Code-Layer und Network-Layer

**Severity:** high
**Status:** open
**Server:** swisstopo-mcp
**Check-Reference:** SEC-021
**PDF-Reference:** Anhang B5 + B12

### Observed Behavior
The code layer is solid. `ALLOWED_HOSTS` is a frozenset with an inline comment stating it is deliberately not env-derived so it cannot be silently widened at runtime (`src/swisstopo_mcp/api_client.py:51-64`), including the new REFRAME host at `api_client.py:56`. `assert_host_allowed` (`api_client.py:67-74`) is called before the first attempt in `request_with_retry` (`api_client.py:162-163`), which covers every request helper, and the two handlers that call the client directly assert first (`src/swisstopo_mcp/oereb.py:98`, `:161`). No call site passes `check_host=False`. The new host is documented (`docs/network-egress.md:13`), recorded in the CHANGELOG (`CHANGELOG.md:50`), covered by two tests (`tests/test_egress_allowlist.py:23-48`, `tests/test_coords.py:190-197`), and a 5-step update procedure exists (`docs/network-egress.md:40-49`).

The network layer is where this falls short, in two ways:

1. **The egress documentation contradicts the shipped manifest.** `docs/network-egress.md:34-38` states that "the server runs locally over stdio today and is not cloud-deployed, so no Kubernetes NetworkPolicy / security-group egress rule is shipped. If/when the server is containerised, add a network-layer egress allow-list". But `deploy/kubernetes.yaml:87-118` ships exactly that policy, `docs/deployment.md:5-6` references it as "the network-layer half of SEC-021", and the audit profile records `is_cloud_deployed=true`. A maintainer following the update procedure at `docs/network-egress.md:48` ("only relevant for cloud deployment") would skip updating a policy that exists.
2. **The network-layer control is a CIDR/port policy, not a host allow-list.** `deploy/kubernetes.yaml:101-108` permits TCP/443 to the entire public internet minus private ranges; it does not restrict egress to the 10 hosts in `ALLOWED_HOSTS`. DNS is correctly permitted (`deploy/kubernetes.yaml:112-118`), so that criterion is met, but the policy does not mirror the code-layer list.

Two further documentation defects: `SECURITY.md:24` describes the allow-list as "restricted to `*.geo.admin.ch` and the cantonal OEREB endpoints", stale since `geodienste.ch`, `overpass.osm.ch` and `openplzapi.org` were added (`api_client.py:60-62`); and `assert_host_allowed` checks only the hostname, never the scheme (`api_client.py:69`) — see SEC-004.

### Expected Behavior
- Code-layer allow-list as a `frozenset` in code, not config-mutable
- Network-layer egress control via NetworkPolicy / security group / equivalent
- Allow-list hosts documented in `docs/network-egress.md` or the README
- A pre-request check (`assert_host_allowed`) called before every outbound request
- A documented update procedure for allow-list extensions
- The DNS resolution path explicitly permitted at the network layer

Both layers must hold for this check to pass.

### Evidence
- Frozenset allow-list with anti-widening rationale: `src/swisstopo_mcp/api_client.py:51-64`; REFRAME host at `api_client.py:56`
- Central pre-request enforcement: `api_client.py:67-74`, called at `api_client.py:162-163`; covers `geo_admin_request` (`:194`), `geo_admin_request_text` (`:206`), `reframe_request` (`:221`), `stac_request` (`:229`), `openplz_request` (`:245`), `geodata.py:113`/`:449`/`:464`, `overpass.py:159`; direct-client sites assert first at `src/swisstopo_mcp/oereb.py:98` and `:161`
- Documentation and changelog for the new host: `docs/network-egress.md:13`, `CHANGELOG.md:50`
- Update procedure: `docs/network-egress.md:40-49`
- NetworkPolicy `swisstopo-mcp-egress`: `deploy/kubernetes.yaml:90-118`, with DNS at `deploy/kubernetes.yaml:112-118`
- Tests: `tests/test_egress_allowlist.py:23-25` (parametrised over ALLOWED_HOSTS), `:27-38` (rejects `evil.example.com`, `169.254.169.254`, `api3.geo.admin.ch.evil.com`, `localhost`), `:41-48` (all OEREB_ENDPOINTS hosts on the list); `tests/test_coords.py:190-197` (REFRAME host allowed, suffix-trick rejected)

Gaps:
- `docs/network-egress.md:34-38` claims no NetworkPolicy is shipped while `deploy/kubernetes.yaml:90-118` ships one — stale text contradicting the manifest and the `is_cloud_deployed=true` profile
- The network-layer control is CIDR-based, not host-based; it does not mirror `ALLOWED_HOSTS`
- `SECURITY.md:24` describes the allow-list as `*.geo.admin.ch` plus cantonal OEREB endpoints — stale since `api_client.py:60-62`
- `assert_host_allowed` checks only the hostname, never the scheme (`api_client.py:69`) — relevant because `geodata.py:447` and `:464` build URLs from an upstream catalogue value (`geodata.py:96-104`)

### Risk Description
The two-layer requirement exists for one specific failure mode: a compromised code image where the code-layer check no longer runs. That is precisely what today's network layer does not cover. `deploy/kubernetes.yaml:101-108` permits TCP/443 to `0.0.0.0/0` minus private ranges, so a modified or malicious image could reach any public HTTPS endpoint — an exfiltration channel for anything the process can read, and a command-and-control path. Since the data this server handles is public Swiss OGD, the exfiltration value is low; the realistic concern is the outbound channel itself and the loss of the defence-in-depth guarantee the check is written to provide.

The documentation contradiction is the more urgent of the two, because it is self-perpetuating. `docs/network-egress.md:34-38` tells a maintainer that the network layer is out of scope for this server. Anyone adding a host to `ALLOWED_HOSTS` and following the documented 5-step procedure will therefore skip step 4, and the shipped NetworkPolicy will drift further from the code-layer list with each addition. The stale `SECURITY.md:24` description compounds this: a reviewer checking which hosts this server may reach gets an answer three hosts short of the truth.

### Remediation
1. **Fix `docs/network-egress.md:34-38` first.** Replace the "not cloud-deployed, no NetworkPolicy shipped" paragraph with a pointer to `deploy/kubernetes.yaml:90-118` and a statement of what that policy does and does not cover (port/CIDR restriction, not per-host). Remove the "only relevant for cloud deployment" qualifier from the update procedure at `docs/network-egress.md:48` and make step 4 unconditional.
2. **Refresh `SECURITY.md:24`** to list all 10 hosts, or better, to reference `docs/network-egress.md:13` as the single source of truth so it cannot go stale again.
3. **Narrow the network layer toward the code-layer list.** A Kubernetes NetworkPolicy cannot match on hostname, so choose one of:
   - Add an egress-proxy sidecar (Smokescreen or equivalent) configured with the same 10 hosts, and restrict the NetworkPolicy to permit egress only to the proxy. This gives a true host allow-list at the network layer and reuses the documented list.
   - Or, if the proxy is too heavy, resolve the 10 hosts to their current address ranges and narrow the `ipBlock` in `deploy/kubernetes.yaml:101-108` accordingly, with a documented refresh cadence. This is weaker and brittle against upstream IP changes — note that trade-off in `docs/network-egress.md` if chosen.
4. **Add a consistency test.** A test that reads `ALLOWED_HOSTS` and asserts every member appears in the `docs/network-egress.md` table (and, once step 3 lands, in the proxy config) turns the drift this finding describes into a CI failure rather than a documentation review item.
5. Add the scheme check to `assert_host_allowed` per SEC-004 remediation step 1 — the same one-line change closes the last gap listed here.

### Effort Estimate
M (1-3d)
