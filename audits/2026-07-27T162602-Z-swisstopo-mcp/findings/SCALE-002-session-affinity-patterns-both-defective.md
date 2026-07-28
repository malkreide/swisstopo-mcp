## Finding: SCALE-002 — Stateful Load Balancing für Streamable HTTP / SSE

**Severity:** high
**Status:** partial
**Server:** swisstopo-mcp
**Check-Reference:** SCALE-002
**PDF-Reference:** Sec 5.2
**Run:** 2026-07-27T162602-Z (re-audit)

### Observed Behavior
The default deployment sidesteps the problem deliberately and with documentation:
`replicas: 1` (`deploy/kubernetes.yaml:18`) with a comment explaining that
Streamable-HTTP sessions are per-pod, repeated in `docs/deployment.md:98-110`. That is
an honest choice and makes the problem moot today.

Neither escape hatch works. The HAProxy option (called "preferred") does not achieve
header affinity — see SCALE-003. The NGINX cookie option
(`deploy/ingress-sticky-sessions.yaml:28`) scopes itself to "browser clients that
carry cookies", and MCP hosts are not cookie-persisting browsers; the file's own
comment concedes NGINX cannot stick on an arbitrary request header. Neither artefact
is wired into the shipped manifests, and the Service sets no `sessionAffinity` at
all.

### Expected Behavior
- At least one affinity or shared-state pattern demonstrably implemented
- Explicit session TTL

### Evidence
- The default deployment sidesteps the problem rather than solving it, deliberately and with documentation: `replicas: 1` at deploy/kubernetes.yaml:18 with a comment at :13-17 explaining that Streamable-HTTP sessions are per-pod and that scaling out requires affinity or a shared store first. docs/deployment.md:98-110 repeats it under 'Scaling out (SCALE-002)'.
- Two opt-in affinity artefacts exist with explicit TTLs: deploy/haproxy.cfg:36-37 (`stick-table type string len 64 size 100k expire 1h` + `stick on req.hdr(Mcp-Session-Id)`) and deploy/ingress-sticky-sessions.yaml:30-52 (NGINX cookie affinity, `affinity-mode: persistent`, `session-cookie-max-age: "3600"`).
- Neither is wired into the shipped deployment: the Service at deploy/kubernetes.yaml:89-98 has no `sessionAffinity`, no Ingress is applied by deploy/kubernetes.yaml, and deploy/haproxy.cfg is a standalone file no manifest references.
- Option A (HAProxy, called 'preferred' at deploy/ingress-sticky-sessions.yaml:14 and docs/deployment.md:104-106) does not actually achieve header affinity — see SCALE-003. `stick on` is shorthand for `stick match` + `stick store-request`; the initialize request carries no Mcp-Session-Id (the server MINTS it in the response, confirmed at runtime: the 200 response carried `mcp-session-id: dc67841a766944d0927c20a291deb6e3` and the request had no such header), so nothing is stored. The first request that does carry the header misses the table and is round-robined to a possibly-wrong replica, then pinned there for the full 1h.
- Option B (NGINX cookie affinity) is inapplicable to the actual client population: deploy/ingress-sticky-sessions.yaml:28 itself scopes it to 'browser clients that carry cookies', while MCP hosts (Claude Desktop, mcp-remote and similar) are not cookie-persisting browsers. The file's own comment at :26-27 concedes NGINX cannot stick on an arbitrary request header.
- No shared-state alternative is implemented: no redis/memcached/SessionStore anywhere in src/, and Option C at deploy/ingress-sticky-sessions.yaml:54-58 is explicitly declared out of scope.

Gaps:
- No failover test and no test of any kind covering session affinity — Modus 3 of the check is not satisfied by tests either.
- Both offered patterns have a correctness or applicability defect, so a reader who follows docs/deployment.md:102-110 and raises `replicas` will get broken sessions in the majority of cases.
- The Service does not even set `sessionAffinity: ClientIP` as a crude fallback for the raise-replicas case.

### Risk Description
The single-replica default is safe. The danger is the documented upgrade path: a
reader who follows `docs/deployment.md:102-110` and raises `replicas` gets broken
sessions in the majority of cases, and gets them intermittently rather than
immediately — the failure looks like flaky clients, not like a misconfiguration.

### Remediation
1. Fix the HAProxy config (SCALE-003) or stop calling it preferred.
2. Set `sessionAffinity: ClientIP` on the Service as a crude fallback, so raising
   replicas degrades rather than breaks.
3. State plainly in `docs/deployment.md` that no verified multi-replica path exists
   yet — the current text implies two working options.

### Effort Estimate
M (1-3d)

### Relation to run `2026-07-27T125314-Z`
Left open by the previous run. The new information is that both offered patterns are defective, not merely unwired.

### Auditor Notes
The check asks for at least one affinity or shared-state pattern to be
demonstrably implemented. Nothing is implemented in the applied path — the
single-replica default makes the problem moot today, which is an honest and
documented choice, so this is not a fail. But the two escape hatches offered for
the moment someone scales out do not hold up under scrutiny: the HAProxy config
never learns the session-to-backend mapping (it only reads the header, never
stores it from the response), and cookie affinity does not apply to non-browser
MCP clients. TTLs are set on both, which satisfies one criterion. Partial.
