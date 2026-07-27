## Finding: SEC-004 — SSRF-Prevention: HTTPS-Enforcement + IP-Blocklisting

**Severity:** critical
**Status:** closed
**Server:** swisstopo-mcp
**Check-Reference:** SEC-004
**PDF-Reference:** Sec 4.4

### Observed Behavior
The structural SSRF surface is closed: no tool accepts a user-supplied URL, every upstream base is a module constant (`src/swisstopo_mcp/api_client.py:16-22`) or a fixed cantonal registry entry (`src/swisstopo_mcp/oereb.py:25-28`), the host allow-list is a frozenset of 10 hosts checked before every request (`src/swisstopo_mcp/api_client.py:51-64`, `api_client.py:67-74`, called at `api_client.py:162-163`), and redirects are disabled (`src/swisstopo_mcp/api_client.py:90-94`).

Three explicit Pass-Criteria remain unmet at the code layer:

1. **No HTTPS scheme enforcement.** `assert_host_allowed` inspects only `urlparse(url).hostname` (`src/swisstopo_mcp/api_client.py:69`); an `http://` URL to an allow-listed host passes. This is reachable: `src/swisstopo_mcp/geodata.py:447` builds `coll_url` from `ogc_base`, a value read out of the upstream geodienste.ch catalogue response (`src/swisstopo_mcp/geodata.py:96-104`, `:113`), and `src/swisstopo_mcp/geodata.py:464` does the same for `items_url`. The scheme of those two URLs is upstream-influenced, not fixed by this repo.
2. **No resolved-IP blocklist anywhere in the code layer.** A grep for `getaddrinfo|ipaddress|socket\.|proxy` over `src/` returns zero hits — no DNS resolution plus `ip_network` membership check, no egress proxy.
3. **IPv6 is uncovered.** The NetworkPolicy `except` list at `deploy/kubernetes.yaml:104-108` contains IPv4 CIDRs only; `::1/128` and `fe80::/10` are not excluded and there is no IPv6 `ipBlock` rule.

The `169.254.169.254` defence therefore exists only in the Kubernetes NetworkPolicy (`deploy/kubernetes.yaml:100-111`, TCP/443 only, RFC1918 plus `169.254.0.0/16` excluded) and does not apply to local-stdio or plain `docker run` deployments.

### Expected Behavior
- HTTPS scheme validated before every outbound request
- Resolved IP checked against a private / link-local / loopback blocklist
- DNS resolved once and the resolved IP used for the request (no TOCTOU)
- `169.254.169.254` explicitly blocked
- IPv6 loopback (`::1`) and link-local (`fe80::/10`) blocked
- In production: an egress proxy (Smokescreen or equivalent) as defence-in-depth

### Evidence
- Allow-list and pre-request check: `src/swisstopo_mcp/api_client.py:51-64` (ALLOWED_HOSTS), `api_client.py:67-74` (assert_host_allowed), `api_client.py:162-163` (call site in `request_with_retry`)
- Direct client calls that bypass `request_with_retry` still assert first: `src/swisstopo_mcp/oereb.py:98`, `src/swisstopo_mcp/oereb.py:161`
- Redirects disabled: `src/swisstopo_mcp/api_client.py:90-94`
- Network-layer blocklist (containerised deployment only): `deploy/kubernetes.yaml:100-111`
- Regression test asserts rejection of `169.254.169.254`, `localhost` and a suffix-trick host: `tests/test_egress_allowlist.py:27-38`

Gaps:
- HTTPS scheme is never validated before an outbound request (`src/swisstopo_mcp/api_client.py:67-74`)
- Attacker-influenced scheme reaches the request builder at `src/swisstopo_mcp/geodata.py:447` and `:464`, sourced from the upstream catalogue at `src/swisstopo_mcp/geodata.py:96-104`
- No resolved-IP range check at the code layer; `169.254.169.254` is blocked only by `deploy/kubernetes.yaml:104-108`
- IPv6 loopback and link-local are blocked at no layer
- No egress proxy

### Risk Description
A compromised or spoofed geodienste.ch catalogue response can downgrade two live request URLs to `http://`, because `geodata.py` takes both scheme and path from that payload and `assert_host_allowed` only inspects the hostname. Plaintext HTTP on the wire removes certificate validation, so an on-path attacker between the server and an allow-listed host can inject arbitrary geodata content that the LLM will present as authoritative Swiss federal data.

Separately, for the two deployment modes that are actually the default here — local stdio and plain `docker run` — there is no metadata-IP defence at all. The NetworkPolicy that carries the whole IP-blocklisting criterion applies only to the Kubernetes deployment. If any allow-listed hostname ever resolves into a private or link-local range (DNS compromise, a poisoned `/etc/hosts` on a developer machine, a hostile split-horizon resolver), the request goes through unchallenged. This server holds no credentials of its own, so the immediate loss is not token theft but internal reachability from a process that is generally trusted to only talk to public geodata endpoints.

### Remediation
1. In `src/swisstopo_mcp/api_client.py`, extend `assert_host_allowed` to validate the scheme in the same place the hostname is validated:

```python
def assert_host_allowed(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise PermissionError(f"Non-HTTPS egress blocked: {parsed.scheme}://{parsed.hostname}")
    if parsed.hostname not in ALLOWED_HOSTS:
        raise PermissionError(f"Host not on egress allow-list: {parsed.hostname}")
```

2. Add a resolved-IP guard in the same module, called from `assert_host_allowed`, so it covers every call path including the two direct-client sites in `oereb.py`:

```python
import ipaddress, socket

_BLOCKED_NETS = [
    ipaddress.ip_network(n) for n in (
        "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16",
        "127.0.0.0/8", "169.254.0.0/16",
        "::1/128", "fe80::/10", "fc00::/7",
    )
]

def assert_resolved_ip_public(hostname: str) -> None:
    for family, _, _, _, sockaddr in socket.getaddrinfo(hostname, 443, proto=socket.IPPROTO_TCP):
        ip = ipaddress.ip_address(sockaddr[0])
        if any(ip in net for net in _BLOCKED_NETS):
            raise PermissionError(f"Host {hostname} resolves to blocked address {ip}")
```

3. Add the IPv6 exclusions to `deploy/kubernetes.yaml:104-108` — an `ipBlock` for `::/0` with `except: ["::1/128", "fe80::/10", "fc00::/7"]` alongside the existing IPv4 rule.
4. Extend `tests/test_egress_allowlist.py` with two cases: `http://api3.geo.admin.ch/...` must raise `PermissionError`, and a monkeypatched `getaddrinfo` returning `169.254.169.254` for an allow-listed host must raise.
5. Optional defence-in-depth: document an egress-proxy deployment option in `docs/network-egress.md` for operators who run this outside Kubernetes.

Note that step 2 alone does not close the TOCTOU window — that is tracked separately as SEC-005. Steps 1 and 3 are unconditional wins and should not wait for it.

### Effort Estimate
S (<1d)

---

### Remediation Status (2026-07-27, follow-up PR)

**Closed.** `assert_host_allowed` now validates the scheme before the host, so an
allow-listed host reached over cleartext `http://` is rejected. A resolved-IP
guard (`assert_resolved_ip_public`) blocks any allow-listed name that answers
with a private or link-local address, covering the two direct-client call sites
in `oereb.py` because it hangs off the same function. Resolution is cached per
host; a resolution *failure* is deliberately non-fatal, so httpx surfaces the
real connection error instead of a masked PermissionError. 12 tests added.
