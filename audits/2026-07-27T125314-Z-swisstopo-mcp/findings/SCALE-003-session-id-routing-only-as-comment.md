## Finding: SCALE-003 — Mcp-Session-Id Routing via Edge-LB (HAProxy Stick-Tables)

**Severity:** high
**Status:** open
**Server:** swisstopo-mcp
**Check-Reference:** SCALE-003
**PDF-Reference:** Sec 5.2

### Observed Behavior

The correct header-based routing pattern is documented in the repo, but only as a comment; the one manifest that can actually be applied routes by cookie instead of by `Mcp-Session-Id`.

- Header-based routing is specified with the right primitives: an HAProxy backend with `stick on req.hdr(Mcp-Session-Id)` over a `stick-table type string len 64 size 100k expire 1h` — `deploy/ingress-sticky-sessions.yaml:11-18`. Capacity (100k sessions) and TTL (1h) both meet the pass criteria.
- **That HAProxy block is a YAML comment, not deployable configuration:** lines `deploy/ingress-sticky-sessions.yaml:11-18` are all `#`-prefixed. No `haproxy.cfg` or `nginx.conf` exists in the repo (searched for `haproxy.cfg` / `nginx.conf` / `ingress*.yaml` — only `deploy/ingress-sticky-sessions.yaml` is present).
- **The only executable manifest in the file is Option B, NGINX Ingress cookie affinity** (`deploy/ingress-sticky-sessions.yaml:28-49`). It does not read `Mcp-Session-Id` at all; the file itself states "NGINX cannot stick on an arbitrary request header, so it pins clients with an affinity cookie instead" (`deploy/ingress-sticky-sessions.yaml:23-25`). It also omits `nginx.ingress.kubernetes.io/upstream-hash-by: "$http_mcp_session_id"`, which the check's own remediation snippet prescribes.
- **Nothing in the repo applies any of it by default:** `deploy/kubernetes.yaml:18` ships `replicas: 1` and `deploy/kubernetes.yaml:76-86` a plain ClusterIP Service with no `sessionAffinity`; the ingress file is explicitly conditional ("Apply ONE of these alongside deploy/kubernetes.yaml after raising replicas", `deploy/ingress-sticky-sessions.yaml:8`).
- No failover behaviour has been tested or documented — Modus 2 was not run, and nothing in `tests/` or `docs/deployment.md` covers it.

### Expected Behavior

Per the check's Pass Criteria:

- The edge load balancer reads the `Mcp-Session-Id` header explicitly
- Stick-table / hash mechanism with sufficient capacity (≥100k sessions)
- TTL set explicitly, correlated with the session TTL
- Failover behaviour tested: on backend failure a session is not routed to a new backend without shared state

### Evidence

- File: `deploy/ingress-sticky-sessions.yaml:11-18` — the correct HAProxy stick-table config, entirely `#`-commented.
- File: `deploy/ingress-sticky-sessions.yaml:23-25` — explicit statement that the NGINX path cannot stick on the header.
- File: `deploy/ingress-sticky-sessions.yaml:28-49` — the only applicable manifest; cookie affinity, no `upstream-hash-by: "$http_mcp_session_id"`.
- File: `deploy/ingress-sticky-sessions.yaml:8` — the whole file is conditional on raising replicas.
- File: `deploy/kubernetes.yaml:18` — `replicas: 1`.
- File: `deploy/kubernetes.yaml:76-86` — ClusterIP Service without `sessionAffinity`.
- Search: no `haproxy.cfg` and no `nginx.conf` anywhere in the repo.

### Risk Description

The exposure is latent while `replicas: 1`, which is why this is not urgent today. It becomes an outage the moment someone scales out — and scaling out is exactly the operation an operator performs under load, without touching the ingress file:

- MCP clients are predominantly non-browser (Claude Desktop, CLI agents, the stdio-to-HTTP bridges). They have no cookie jar, so the cookie affinity in `deploy/ingress-sticky-sessions.yaml:28-49` does not pin them at all. Requests round-robin across pods, each pod rejects the unknown `Mcp-Session-Id`, and every multi-request conversation breaks mid-flight with errors that look like random flakiness rather than a routing bug.
- The Service has no `sessionAffinity: ClientIP` fallback (`deploy/kubernetes.yaml:76-86`), so there is not even the weaker IP-based affinity behind it — and IP affinity would in any case break behind NAT, the caveat the check calls out.
- The operator's most likely reaction — "apply the sticky-sessions manifest" — installs the cookie variant and does not fix it, because the HAProxy variant that would fix it is a comment.
- Failover is untested, so even with correct sticking there is no evidence about what happens to an in-flight session when a pod is drained during a rolling update.

### Remediation

1. Ship deployable header-based routing, not a comment. In `deploy/`, add a real `haproxy.cfg` (or a HAProxy Ingress `ConfigMap` manifest) containing the block currently commented at `deploy/ingress-sticky-sessions.yaml:11-18`, uncommented and complete:

   ```
   backend mcp_backend
       mode http
       balance roundrobin
       stick-table type string len 64 size 100k expire 1h
       stick on req.hdr(Mcp-Session-Id)
       server mcp1 ... check
       server mcp2 ... check
   ```

   Keep the size/TTL values as they are — they already meet the criteria.
2. If NGINX Ingress must remain an option, fix it rather than leaving it as the only applicable path: add `nginx.ingress.kubernetes.io/upstream-hash-by: "$http_mcp_session_id"` to the annotations at `deploy/ingress-sticky-sessions.yaml:28-49`, and state in the surrounding comment that cookie affinity alone is insufficient for non-browser MCP clients.
3. Add a fallback at the Service layer: set `sessionAffinity: ClientIP` with an explicit `sessionAffinityConfig.clientIP.timeoutSeconds` in `deploy/kubernetes.yaml:76-86`, documented as a partial mitigation that does not survive NAT.
4. Gate scale-out on this: in `docs/deployment.md`, state that raising `replicas` above 1 requires the header-based routing manifest, and add the failover procedure — drain a pod while a session is active and record the observed client behaviour — as a documented pre-scale-out test.
5. Re-run the check's Modus 2 probe after step 1: hold one `Mcp-Session-Id` across five requests and assert all five reach the same pod.

### Effort Estimate

M (1-3d) — the config itself is small; the failover test and the deployment documentation are the bulk.
